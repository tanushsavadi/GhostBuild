"""3. Backend reliability (WebSocket input, duplicates, rate limit, restarts) and mode labels:
GUIDED = 'DONE (YOU CONFIRMED)', VERIFIED = '● VERIFIED' only after a jig measurement."""

from __future__ import annotations

import json
import threading
import time

import pytest

from tests.e2e.harness.core_proc import FrameRecorder

CUP, LED = "origami-cup-v1", "led-button-v1"
CONFIRMED, VERIFIED = "DONE (YOU CONFIRMED)", "● VERIFIED"


def recv_until(ws, pred, timeout: float = 3.0) -> dict:
    end = time.time() + timeout
    while time.time() < end:
        d = json.loads(ws.recv(timeout=max(0.05, end - time.time())))
        if pred(d):
            return d
    raise AssertionError("no matching ws message")


def g2(kind: str, text: str | None = None, seq_seen: int | None = None) -> str:
    return json.dumps({"type": "g2_input", "kind": kind, "text": text, "seq_seen": seq_seen})


def without_mode_header(text: str) -> str:
    return text.replace("VERIFIED MODE", "")


class JigFeeder:
    """Plays the jig adapter over ws role=jig at 10 Hz (labelled live by core)."""

    def __init__(self, core) -> None:
        self.ws = core.ws("jig")
        self.fields: dict = {"led": "no_resistor", "button": "released"}
        self.running = True
        self.seq = 0
        self.t = threading.Thread(target=self._run, daemon=True)
        self.t.start()

    def _run(self) -> None:
        while self.running:
            self.seq += 1
            self.ws.send(json.dumps({"type": "jig", "v": 1, "dev": "e2e-feeder", "seq": self.seq,
                                     "ms": self.seq * 100, "fields": self.fields}))
            time.sleep(0.1)

    def stop(self) -> None:
        self.running = False
        self.t.join(1)
        self.ws.close()


# --- websocket input -------------------------------------------------------------------------------------------


def test_g2_socket_gets_current_frame_on_connect(core):
    core.load(CUP)
    with core.ws() as ws:
        first = json.loads(ws.recv(timeout=3))
    assert first == core.hud()


@pytest.mark.parametrize("raw", ["not json", '{"type":"g2_input","kind":"teleport"}', '{"kind":"tap","x":1}', "[]"],
                         ids=["not-json", "bad-kind", "extra-field", "array"])
def test_malformed_ws_input_is_rejected_and_socket_survives(core, raw):
    core.load(CUP)
    with core.ws() as ws:
        ws.send(raw)
        err = recv_until(ws, lambda d: d.get("type") == "error")
        assert err["error"]
        ws.send(g2("tap"))
        recv_until(ws, lambda d: d.get("kind") == "confirmed")
    assert core.completed() == {"c1": "confirmed"}


def test_duplicate_tap_pair_is_harmless(core):
    core.load(CUP)
    seq = core.hud()["seq"]
    with core.ws() as ws:
        ws.send(g2("tap", seq_seen=seq))
        ws.send(g2("tap", seq_seen=seq))
        time.sleep(0.5)
    assert core.completed() == {"c1": "confirmed"} and core.step_index() == 1


@pytest.mark.xfail(strict=True, reason="F-15: core ignores G2Input.seq_seen. Three deliveries of one tap (all "
                   "seq_seen=S) confirm step 1, skip its ack, then confirm step 2 the user never saw.")
def test_duplicate_inputs_for_one_frame_complete_at_most_one_step(core):
    core.load(CUP)
    seq = core.hud()["seq"]
    with core.ws() as ws:
        for _ in range(3):
            ws.send(g2("tap", seq_seen=seq))
        time.sleep(0.5)
    assert core.completed() == {"c1": "confirmed"}, core.completed()


def test_hud_rate_limit_holds_under_input_burst(core):
    core.load(LED)
    rec = FrameRecorder(core)
    try:
        qs = ["which leg is longer", "why", "what does the resistor look like", "which one is the led"] * 6
        with core.ws() as ws:
            for q in qs:
                ws.send(g2("voice", q))
                time.sleep(0.02)
        time.sleep(1.0)
        times = [t for t, _ in rec.frames]
        gaps = [b - a for a, b in zip(times, times[1:])]
        assert len(times) >= 2 and min(gaps) >= 0.2, gaps  # 250 ms in hud.py, minus delivery jitter
        assert len(times) <= 4 * (times[-1] - times[0]) + 2
        assert core.lines()[2] == "CLEAR RED BULB, TWO LEGS"  # coalesced to the latest answer
    finally:
        rec.close()


def test_restart_loses_the_session(core):
    core.load(CUP)
    core.tap()
    core.wait_hud(lambda h: core.completed() == {"c1": "confirmed"})
    core.stop()
    core.start()
    s = core.state()
    assert s["engine"] == "IDLE" and s["completed"] == [] and s["procedure_id"] is None


def test_restart_with_procedure_flag_starts_from_step_one(make_core):
    core = make_core("--procedure", CUP)
    assert core.state()["step_index"] == 0


# --- labels ----------------------------------------------------------------------------------------------------


def test_guided_run_never_says_verified(core):
    core.load(CUP)
    rec = FrameRecorder(core)
    try:
        for i in range(6):
            core.tap()
            core.wait_hud(lambda h: h["kind"] == "confirmed" and CONFIRMED in h["lines"])
            core.wait_hud(lambda h, i=i: h["step_index"] == i + 1 or h["kind"] == "complete", timeout=3)
        done = core.wait_hud(lambda h: h["kind"] == "complete")
        assert done["lines"][:2] == ["BUILD COMPLETE", "6/6 DONE"]
        time.sleep(0.3)
        assert not any("VERIFIED" in t for t in rec.texts()), rec.texts()
        assert {f["mode"] for _, f in rec.frames} <= {"GUIDED", None}
        assert set(core.completed().values()) == {"confirmed"}
    finally:
        rec.close()


def test_no_jig_mode_runs_jig_steps_guided_and_never_verified(make_core):
    core = make_core("--no-jig")
    core.load(LED)
    rec = FrameRecorder(core)
    try:
        core.tap()
        core.tap()
        h = core.wait_hud(lambda h: h["step_index"] == 1)
        assert h["mode"] == "GUIDED" and h["lines"][0] == "STEP 2/6 · GUIDED MODE"
        for _ in range(5):
            core.tap()
            core.tap()
            time.sleep(0.3)
        core.wait_hud(lambda h: h["kind"] == "complete")
        assert core.lines()[:2] == ["BUILD COMPLETE", "6/6 DONE"]
        assert not any("VERIFIED" in t for t in rec.texts()), rec.texts()
    finally:
        rec.close()


def test_mixed_run_labels_each_step_by_how_it_completed(core):
    core.load(LED)
    rec = FrameRecorder(core)
    try:
        core.tap()  # s1 guided
        core.wait_hud(lambda h: h["step_index"] == 1, timeout=4)
        core.sim_jig(led="missing")  # s2 resistor measured
        core.wait_hud(lambda h: h["step_index"] == 2, timeout=4)
        core.sim_jig(led="correct")  # s3 LED measured
        core.wait_hud(lambda h: h["step_index"] == 3, timeout=4)
        core.tap()  # s4 guided (button released: no fault)
        core.wait_hud(lambda h: h["step_index"] == 4, timeout=4)
        time.sleep(0.3)
        core.sim_jig(button="pressed")  # s5 edge check: released seen first, now pressed
        core.wait_hud(lambda h: h["step_index"] == 5, timeout=4)
        core.sim_jig(button="released")  # s6 circuit complete
        done = core.wait_hud(lambda h: h["kind"] == "complete", timeout=4)
        assert done["lines"][:2] == ["BUILD COMPLETE", "6/6 DONE · 4 VERIFIED"]
        assert core.completed() == {"s1": "confirmed", "s2": "verified", "s3": "verified", "s4": "confirmed",
                                    "s5": "verified", "s6": "verified"}
        for _, f in rec.frames:
            text = "\n".join(f["lines"])
            assert f["source"] == "simulated"
            if VERIFIED in text:
                assert f["mode"] == "VERIFIED" and f["kind"] == "verified", f
            if CONFIRMED in text:
                assert f["mode"] == "GUIDED", f
        guided_frames = [f for _, f in rec.frames if f["mode"] == "GUIDED"]
        assert guided_frames and not any("VERIFIED" in without_mode_header("\n".join(f["lines"]))
                                         for f in guided_frames)
    finally:
        rec.close()


def test_live_jig_verifies_as_measured_and_stale_jig_abstains(make_core):
    core = make_core()
    feeder = JigFeeder(core)
    try:
        core.load(LED)
        core.tap()
        core.wait_hud(lambda h: h["step_index"] == 1, timeout=4)
        feeder.fields = {"led": "missing", "button": "released"}
        h = core.wait_hud(lambda h: h["kind"] == "verified")
        assert h["source"] == "live" and VERIFIED in h["lines"]
        ev = [e for e in core.state()["events"] if e["text"] == "s2 verified"]
        assert ev and ev[0]["label"] == "MEASURED LIVE"
        core.wait_hud(lambda h: h["step_index"] == 2, timeout=4)
        feeder.stop()  # jig unplugged: readings go stale after 2 s
        time.sleep(2.3)
        assert core.state()["jig"]["link"] == "down"
        core.text("done")
        core.wait_status("JIG OFFLINE · ASK A MENTOR", timeout=4)
        assert "s3" not in core.completed()
    finally:
        feeder.running = False


@pytest.mark.xfail(strict=True, reason="F-16 (policy question for D): going 'back' to a step verified earlier shows "
                   "'● VERIFIED' from the stored completion even while the live jig now contradicts it.")
def test_revisited_step_does_not_show_stale_verified(core):
    core.load(LED)
    core.tap()
    core.wait_hud(lambda h: h["step_index"] == 1, timeout=4)
    core.sim_jig(led="missing")
    core.wait_hud(lambda h: h["step_index"] == 2, timeout=4)
    core.sim_jig(led="no_resistor")  # resistor pulled out again
    time.sleep(0.3)
    core.text("back")
    h = core.wait_hud(lambda h: h["step_index"] == 1)
    assert VERIFIED not in h["lines"], h["lines"]
