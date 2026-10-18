import json

import pytest

from contracts.models import Observation
from ghostbuild_pi.camera import FakeCamera, CameraOpenError
from ghostbuild_pi.runner import initial_seq

from helpers import make_station, run


def valid(o):
    Observation.model_validate(o)  # the real contract (extra=forbid)
    json.dumps(o)


def test_blocked_is_dark_flat_and_contract_valid():
    st, clock, _ = make_station("blocked")
    obs = run(st, clock, 2)
    for o in obs:
        valid(o)
        assert o["source"] == "simulated" and o["error"] is None
        c = o["camera"]
        assert c["mean_luma"] < 15 and c["luma_std"] < 5 and c["detail"] < 30 and c["marker_found"] is None


def test_clear_is_bright_textured_and_quiet():
    st, clock, _ = make_station("clear")
    obs = run(st, clock, 2)
    c = obs[-1]["camera"]
    assert c["mean_luma"] > 80 and c["luma_std"] > 25 and c["detail"] > 100 and c["motion"] < 0.02
    assert all(o["led"]["commanded_on"] is False and o["led"]["cmd_seq"] == 0 for o in obs)


def test_frame_seq_increments_per_new_frame():
    st, clock, _ = make_station("clear")
    seqs = [o["camera"]["frame_seq"] for o in run(st, clock, 2)]
    assert seqs == list(range(1, len(seqs) + 1))


def test_flicker_is_blocked_for_one_second_then_clear():
    st, clock, _ = make_station("flicker")
    obs = run(st, clock, 3)
    t = lambda i: i * 0.2
    blocked = [o for i, o in enumerate(obs) if t(i) < 1.0]
    clear = [o for i, o in enumerate(obs) if t(i) >= 1.2]
    assert all(o["camera"]["mean_luma"] < 15 for o in blocked)
    assert all(o["camera"]["mean_luma"] > 80 for o in clear)
    assert all(o["camera"] is not None for o in obs)


def test_frozen_keeps_frame_seq_stuck_and_age_grows():
    st, clock, _ = make_station("frozen")
    obs = run(st, clock, 3)
    assert {o["camera"]["frame_seq"] for o in obs} == {1}
    ages = [o["camera"]["frame_age_ms"] for o in obs]
    assert ages[0] == 0 and ages == sorted(ages) and ages[-1] >= 2500
    assert all(o["camera"]["motion"] == 0.0 for o in obs[1:])
    assert all(o["error"] is None for o in obs)  # the core, not the Pi, judges stale frames


def test_disconnect_goes_null_with_error_and_never_fabricates():
    st, clock, _ = make_station("disconnect", disconnect_after_ms=1000)
    obs = run(st, clock, 4)
    live = [o for o in obs if o["camera"] is not None]
    dead = [o for o in obs if o["camera"] is None]
    assert live and dead and obs.index(dead[0]) == len(live)
    for o in dead:
        valid(o)
        assert o["error"] == "camera_read_failed"
    assert all(o["error"] is None for o in live)
    # no recovery by repeating the last frame: seq/features of live obs are not reused
    assert max(o["camera"]["frame_seq"] for o in live) == len(live)


class _Broken:
    name = "broken"
    is_fake = False

    def open(self):
        raise CameraOpenError("no camera")

    def read(self):
        raise AssertionError("must not read a camera that failed to open")

    def close(self):
        pass

    def info(self):
        return {}


def test_open_failure_emits_camera_null_and_error():
    from ghostbuild_pi.clock import FakeClock
    from ghostbuild_pi.features import FeatureExtractor
    from ghostbuild_pi.runner import Station

    clock = FakeClock()
    st = Station(_Broken(), FeatureExtractor(), "pi_live", clock=clock, seq_start=0)
    for _ in range(3):
        o = st.step()
        valid(o)
        assert o["camera"] is None and o["error"] == "camera_open_failed" and o["led"] is None
        clock.advance(200)


def test_read_exception_is_camera_read_failed():
    from ghostbuild_pi.clock import FakeClock
    from ghostbuild_pi.features import FeatureExtractor
    from ghostbuild_pi.runner import Station

    class Raises(_Broken):
        def open(self):
            pass

        def read(self):
            raise RuntimeError("boom")

    st = Station(Raises(), FeatureExtractor(), "pi_live", clock=FakeClock(), seq_start=0)
    o = st.step()
    assert o["camera"] is None and o["error"] == "camera_read_failed"


def test_reopen_recovers_after_failure():
    from ghostbuild_pi.clock import FakeClock
    from ghostbuild_pi.features import FeatureExtractor
    from ghostbuild_pi.runner import Station

    class Flaky(_Broken):
        n = 0
        ok = False

        def open(self):
            if not self.ok:
                raise CameraOpenError("not yet")

        def read(self):
            import numpy as np
            return (np.full((60, 80), 100, np.uint8), 5000.0)

    clock, cam = FakeClock(), Flaky()
    st = Station(cam, FeatureExtractor(), "pi_live", clock=clock, seq_start=0)
    assert st.step()["error"] == "camera_open_failed"
    cam.ok = True
    clock.advance(2100)
    o = st.step()
    assert o["camera"] is not None and o["error"] is None


def test_obs_seq_strictly_monotonic_and_ms_nondecreasing():
    st, clock, _ = make_station("disconnect", disconnect_after_ms=800)
    obs = run(st, clock, 3)
    seqs = [o["seq"] for o in obs]
    assert seqs == sorted(set(seqs)) and seqs[0] == 1
    ms = [o["ms"] for o in obs]
    assert ms == sorted(ms)


def test_initial_seq_never_goes_backwards_across_restarts():
    t0 = 1_792_283_000_000
    a_end = initial_seq(t0) + 10 * 60 * 5  # 10 minutes at 5 Hz
    assert initial_seq(t0 + 600_000) > a_end
    # even at the 10 Hz ceiling
    assert initial_seq(t0 + 600_000) > initial_seq(t0) + 10 * 600


def test_led_is_null_when_not_configured():
    st, clock, _ = make_station("clear", with_led=False)
    assert run(st, clock, 1)[0]["led"] is None


def test_wave_commands_led_once_then_off_after_two_seconds():
    st, clock, _ = make_station("wave")
    obs = run(st, clock, 4)
    led = [o["led"] for o in obs]
    first_on = next(i for i, l in enumerate(led) if l["commanded_on"])
    assert led[first_on]["reason"] == "motion_in_roi" and led[first_on]["cmd_seq"] == 1
    assert obs[first_on]["camera"]["motion"] > 0.15
    off = next(i for i, l in enumerate(led) if i > first_on and not l["commanded_on"])
    assert led[off]["cmd_seq"] == 2
    assert 1.8 <= (off - first_on) * 0.2 <= 2.4


def test_uncovering_the_lens_does_not_trigger_the_motion_led():
    st, clock, _ = make_station("flicker")
    obs = run(st, clock, 3)
    assert all(not o["led"]["commanded_on"] for o in obs)
    assert max(o["camera"]["motion"] for o in obs) > 0.15  # the jump IS visible as motion; the rule just ignores it


def test_led_off_when_camera_dies_after_hold():
    st, clock, _ = make_station("wave", with_led=True)
    run(st, clock, 1.0)
    assert st.led.commanded_on
    st.camera.disconnect_after_ms = 0  # unusual, but wave has no disconnect; simulate by breaking reads
    st.camera.read = lambda: None
    obs = run(st, clock, 3)
    assert obs[0]["camera"] is None
    assert not st.led.commanded_on


def test_station_close_drives_led_off_even_mid_hold():
    st, clock, _ = make_station("wave")
    run(st, clock, 1.0)
    assert st.led.commanded_on
    st.close()
    assert st.led.driver.__class__.__name__ == "DryRunDriver" and not st.led.commanded_on


def test_led_off_on_exit_when_loop_is_interrupted():
    from ghostbuild_pi.runner import run_loop

    st, clock, _ = make_station("wave")
    n = {"i": 0}

    def sink(o):
        n["i"] += 1
        if n["i"] == 8:
            raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        try:
            run_loop(st.step, sink, clock, 5, lambda: False)
        finally:
            st.close()
    assert not st.led.commanded_on
