import importlib.util
import json
import os

import numpy as np
import pytest

from ghostbuild_pi.camera import CameraOpenError, FakeCamera
from ghostbuild_pi.clock import FakeClock

SPEC = importlib.util.spec_from_file_location("spike", os.path.join(os.path.dirname(__file__), "..", "tools", "spike.py"))
spike = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(spike)


class PhasedCamera:
    """Fake whose scene follows the phase the (fake) human was last asked to set up."""
    name = "fake:phased"

    def __init__(self, clock, state):
        self.clock, self.state, self.n = clock, state, 0
        self.cam = {k: FakeCamera(k, clock) for k in ("blocked", "clear", "wave")}
        for c in self.cam.values():
            c.open()

    def open(self):
        pass

    def close(self):
        pass

    def info(self):
        return {"backend": self.name}

    def read(self):
        self.clock.advance(5)
        return self.cam[self.state["scene"]].read()


def make_env(tmp_path, answers, scenes, core=None, led_ok=True):
    env = spike.Env()
    clock = FakeClock()
    env.clock = clock
    state = {"scene": "clear"}
    answers = list(answers)
    scenes = list(scenes)
    lines = []

    def ask(prompt):
        lines.append(prompt)
        if prompt.startswith("Press Enter"):
            state["scene"] = scenes.pop(0)
            return ""
        return answers.pop(0)

    env.ask = ask
    env.out = lines.append
    env.read_text = lambda p: {"/proc/device-tree/model": "Raspberry Pi TEST", "/etc/os-release": 'PRETTY_NAME="TestOS 1"'}.get(p)
    env.run_cmd = lambda c: "Available cameras\n0 : testsensor [640x480]"
    env.which = lambda e: "/usr/bin/" + e if e.startswith("rpicam") else None
    env.can_import = lambda m: m in ("numpy", "gpiozero")
    env.make_camera = lambda backend: PhasedCamera(clock, state)
    env.hostname = "testpi"
    env.today = lambda: "2026-10-17"
    leds = []

    class D:
        real = True
        name = "d"

        def write(self, on):
            leds.append(on)

        def close(self):
            pass

    env.open_driver = lambda pin, dry_run=False, active_high=True: D()
    env.leds = leds
    env.http_get = lambda url, t: (200, '{"ok":true}')
    posts = []
    env.http_post = lambda url, body, t: posts.append((url, json.loads(body))) or 202
    env.posts = posts
    return env, lines


ARGS = ["--frames", "5", "--phase-seconds", "1", "--settle", "0", "--out"]


def test_spike_pass_path(tmp_path):
    env, lines = make_env(tmp_path, ["y"], ["clear", "blocked", "clear"])
    rc = spike.main(ARGS + [str(tmp_path), "--led-pin", "17", "--core", "http://core:8787"], env)
    text = "\n".join(lines)
    assert rc == 0, text
    assert "OVERALL (camera opens + captures + covered/uncovered separable): PASS" in text
    assert "HUMAN CONFIRMED" in text and "SEPARABLE" in text and "midpoint" in text
    assert env.leds[:2] == [False, True] and env.leds[-1] is False and env.leds.count(True) == 3
    url, obs = env.posts[0]
    assert url == "http://core:8787/observation" and obs["source"] == "simulated"
    rep = json.load(open(tmp_path / "spike_report.json"))
    assert rep["overall"] is True
    assert (tmp_path / "wiring_block.md").read_text().count("TODO") >= 2  # never invents what it did not measure
    assert "| LED pin (BCM) | 17 | HUMAN CONFIRMED |" in text
    assert any(f.startswith("frame_") for f in os.listdir(tmp_path))


def test_spike_fails_when_phases_do_not_differ(tmp_path):
    env, lines = make_env(tmp_path, [], ["clear", "clear", "clear"])
    rc = spike.main(ARGS + [str(tmp_path)], env)
    text = "\n".join(lines)
    assert rc == 1 and "[FAIL] covered vs uncovered separable" in text
    assert "[SKIP] LED blink" in text and "[SKIP] core reachable" in text  # skipped is not passed


def test_led_not_confirmed_is_a_fail_and_never_says_human_confirmed(tmp_path):
    env, lines = make_env(tmp_path, ["n"], ["clear", "blocked", "clear"])
    spike.main(ARGS + [str(tmp_path), "--led-pin", "17"], env)
    text = "\n".join(lines)
    assert "[FAIL] LED blink" in text and "BCM 17 NOT confirmed" in text
    assert "| LED pin (BCM) | 17 | TODO (not confirmed by a human) |" in text


def test_camera_open_failure_is_reported_and_exits_nonzero(tmp_path):
    env, lines = make_env(tmp_path, [], [])

    class Bad:
        def open(self):
            raise CameraOpenError("no cameras")

    env.make_camera = lambda b: Bad()
    rc = spike.main(ARGS + [str(tmp_path)], env)
    assert rc == 1 and any("[FAIL] camera opens" in l and "no cameras" in l for l in lines)


def test_core_down_is_reported_not_raised(tmp_path):
    env, lines = make_env(tmp_path, ["y"], ["clear", "blocked", "clear"])

    def boom(url, t):
        raise ConnectionError("refused")

    env.http_get = boom
    spike.main(ARGS + [str(tmp_path), "--core", "http://x:1", "--led-pin", "17"], env)
    assert any("[FAIL] core GET /health" in l for l in lines)


def test_wave_phase_checks_rule_against_idle(tmp_path):
    env, lines = make_env(tmp_path, ["y"], ["clear", "blocked", "clear", "wave"])
    spike.main(ARGS + [str(tmp_path), "--with-wave", "--led-pin", "17"], env)
    text = "\n".join(lines)
    assert "[PASS] wave triggers the LED rule" in text and "[PASS] idle phases do not trigger" in text


def test_analyze_separation_directions():
    r = spike.analyze_separation([100, 120, 130], [5, 6, 7])
    assert r["separable"] and r["direction"].startswith("covered below") and r["midpoint"] == pytest.approx(53.5)
    r = spike.analyze_separation([1, 2, 3], [10, 11])
    assert r["separable"] and r["direction"].startswith("covered above") and r["midpoint"] == pytest.approx(6.5)
    assert not spike.analyze_separation([1, 5], [3, 4])["separable"]


def test_would_trigger_ignores_scene_change():
    assert spike.would_trigger([0.5, 0.5], [100, 100])
    assert not spike.would_trigger([0.9, 0.9], [5, 120])  # lens uncovered
    assert not spike.would_trigger([0.9, 0.0, 0.9], [100, 100, 100])
