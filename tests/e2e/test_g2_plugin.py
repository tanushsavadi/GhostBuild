"""1 + 3. The REAL g2/src/main.ts (bundled, Even SDK bridge faked) against the REAL core over real HTTP/WebSocket.

Covers hold-to-talk on the plugin side, WebSocket reconnection, HTTP polling fallback, stale frames and restarts.
This proves plugin LOGIC only. It says nothing about G2 rendering, BLE delivery, mic quality or touch timing.
"""

from __future__ import annotations

import json
import socket
import time

import pytest

from tests.e2e.harness.plugin import LISTENING, OFFLINE

pytestmark = pytest.mark.plugin
CUP, LED = "origami-cup-v1", "led-button-v1"
IDLE = "LOAD A BUILD ON THE PHONE"


def pattern(n: int) -> bytes:
    return bytes((i * 37) & 0xFF for i in range(n))


@pytest.fixture
def rig(core, make_plugin):
    core.load(CUP)
    p = make_plugin(core)
    p.wait_shown("STEP 1/6")
    return core, p


def resume_past(core, seq: int) -> None:
    """Make the restarted core's seq pass the old core's, so F-17 (seq collision) can't mask what we test."""
    while core.hud()["seq"] <= seq:
        core.text("repeat")
        time.sleep(0.3)


def hold(p, chunks=(("u8", 3200),) * 10, held: float = 0.6, release: bool = True) -> int:
    p.op("long_press")
    for enc, n in chunks:
        p.op("audio", bytes=n, enc=enc)
    time.sleep(held)
    if release:
        p.op("release")
    return sum(n for _, n in chunks)


def ptt_phases(p) -> list[str]:
    return [json.loads(f["body"])["phase"] for f in p.posts("/ptt")]


# --- boot + input ----------------------------------------------------------------------------------------------


def test_boot_shows_connecting_then_core_frame(core, make_plugin):
    p = make_plugin(core)
    s = p.wait_shown(IDLE)
    assert s["upgrades"][0]["content"] == "GHOSTBUILD\nCONNECTING..."
    assert s["status"].endswith("(WebSocket)")
    core.load(CUP)
    p.wait_shown("FOLD SQUARE INTO TRIANGLE")


def test_tap_goes_over_websocket_with_seq_seen(rig):
    core, p = rig
    seq = core.hud()["seq"]
    p.op("tap")
    p.wait_shown("DONE (YOU CONFIRMED)")
    msg = p.snapshot()["wsSends"][-1]["msg"]
    assert msg == {"type": "g2_input", "seq_seen": seq, "text": None, "kind": "tap"}
    assert core.completed() == {"c1": "confirmed"}


def test_text_event_click_counts_as_tap(rig):
    _, p = rig
    p.op("text_tap")
    p.wait_shown("DONE (YOU CONFIRMED)")


def test_double_tap_exits_and_is_not_a_tap(rig):
    core, p = rig
    s = p.op("double_tap")
    assert s["shutdowns"] == [1] and s["wsSends"] == []
    time.sleep(0.3)
    assert core.completed() == {}


def test_audio_frames_outside_a_hold_are_ignored(rig):
    core, p = rig
    for enc in ("u8", "array", "base64"):
        p.op("audio", bytes=3200, enc=enc)
    time.sleep(0.3)
    s = p.snapshot()
    assert s["wsSends"] == [] and s["fetches"] == [] and core.completed() == {}


# --- hold-to-talk ----------------------------------------------------------------------------------------------


def test_hold_to_talk_full_lifecycle(rig, stt):
    core, p = rig
    stt.say("next")
    p.op("long_press")
    p.wait(lambda s: s["fetches"] and s["fetches"][-1]["url"] == "/ptt", what="/ptt start")
    p.wait_shown(LISTENING)  # rendered by core, not the plugin
    chunks = [("u8", 3200), ("array", 3200), ("base64", 3200)] * 4
    for enc, n in chunks:
        p.op("audio", bytes=n, enc=enc)
    time.sleep(0.5)
    p.op("release")
    s = p.wait(lambda s: s["status"].startswith("Heard"), timeout=4, what="transcript on phone")
    assert s["status"] == 'Heard: "next"'
    audio_posts = p.posts("/audio")
    assert len(audio_posts) == 1 and audio_posts[0]["bodyLen"] == 3200 * len(chunks)
    assert stt.requests[-1].file == pattern(3200) * len(chunks)  # all three bridge encodings decoded to bytes
    on, off = s["audioControl"]
    assert on["on"] is True and on["source"] == "glasses" and off["on"] is False
    assert ptt_phases(p) == ["start"]
    core.wait_hud(lambda h: core.completed() == {"c1": "confirmed"}, what="voice next confirmed step 1")


def test_short_hold_is_cancelled_silently(rig):
    core, p = rig
    hold(p, held=0.05)
    p.wait(lambda s: "cancel" in ptt_phases(p), what="/ptt cancel")
    assert p.posts("/audio") == [] and p.snapshot()["status"].startswith("Voice cancelled")
    p.wait_shown("FOLD SQUARE INTO TRIANGLE")
    p.wait(lambda s: LISTENING not in s["shown"], what="LISTENING cleared")
    assert core.completed() == {}


def test_hold_with_no_audio_is_cancelled(rig):
    _, p = rig
    hold(p, chunks=(), held=0.6)
    p.wait(lambda s: "cancel" in ptt_phases(p), what="/ptt cancel")
    assert p.posts("/audio") == []


def test_taps_during_and_right_after_a_hold_are_ignored(rig, stt):
    _, p = rig
    stt.say("")
    p.op("long_press")
    p.op("tap")  # while recording
    time.sleep(0.5)
    p.op("release")
    time.sleep(0.3)
    p.op("tap")  # inside the 600 ms guard (and inside the 250 ms tail)
    time.sleep(0.2)
    assert p.snapshot()["wsSends"] == []
    time.sleep(0.6)
    p.op("tap")
    p.wait(lambda s: len(s["wsSends"]) == 1, what="tap after guard sent")


def test_mic_unavailable_reports_on_phone_and_taps_still_work(rig):
    _, p = rig
    p.op("mic", mode="fail")
    p.op("long_press")
    p.wait(lambda s: "mic failed" in s["status"], what="mic failure on phone")
    time.sleep(0.5)
    p.op("release")
    time.sleep(0.8)
    assert p.posts("/audio") == []
    p.op("tap")
    p.wait(lambda s: len(s["wsSends"]) == 1, what="tap works after mic failure")


@pytest.mark.xfail(strict=True, reason="F-05: plugin POSTs /ptt start before the mic opens and never cancels when "
                   "audioControl fails, so core shows LISTENING... for up to 15 s with the mic off.")
def test_mic_unavailable_does_not_leave_listening_on_glasses(rig):
    _, p = rig
    p.op("mic", mode="fail")
    hold(p, chunks=(), held=0.5)
    time.sleep(1.0)
    assert LISTENING not in p.shown()


def test_mic_open_throwing_does_not_wedge_the_plugin(rig):
    _, p = rig
    p.op("mic", mode="throw")
    hold(p, chunks=(), held=0.5)
    time.sleep(0.9)
    p.op("tap")
    p.wait(lambda s: len(s["wsSends"]) == 1, what="tap works after mic exception")


def test_duplicate_release_event_sends_one_clip(rig, stt):
    _, p = rig
    stt.say("next")
    hold(p, held=0.5)
    p.op("release")
    time.sleep(1.5)
    assert len(p.posts("/audio")) == 1


@pytest.mark.xfail(strict=True, reason="F-06: a second hold that starts inside the 250 ms tail of the first is "
                   "swallowed: startTalk() returns early while `recording` is still true.")
def test_second_hold_inside_release_tail_is_not_lost(rig, stt):
    _, p = rig
    stt.say("help")
    stt.say("next")
    hold(p, held=0.5)
    time.sleep(0.1)
    hold(p, held=0.5)
    time.sleep(1.5)
    assert len(p.posts("/audio")) == 2


@pytest.mark.slow
@pytest.mark.xfail(strict=True, reason="F-04: no cap on hold length. If LONG_PRESS_RELEASE is lost, the mic stays "
                   "open, PCM buffers without bound and every tap is ignored until another release arrives.")
def test_lost_release_does_not_disable_taps_forever(rig):
    _, p = rig
    hold(p, release=False)
    time.sleep(16)  # longer than core's 15 s LISTENING notice
    p.op("tap")
    p.wait(lambda s: len(s["wsSends"]) == 1, timeout=2, what="tap accepted after a lost release")


# --- transport: reconnect, fallback, stale frames, restarts ----------------------------------------------------


def test_ws_drop_reconnects_transport(rig):
    core, p = rig
    p.op("drop_ws")
    p.wait_shown("GHOSTBUILD OFFLINE")
    p.wait(lambda s: s["wsOpened"] == 2 and s["status"].endswith("(WebSocket)"), what="ws reconnected")
    assert core.get("/health")[1]["g2_connected"] == 1
    p.op("tap")  # input path works again
    core.wait_hud(lambda h: core.completed() == {"c1": "confirmed"})


@pytest.mark.xfail(strict=True, reason="F-08: after a WS drop to the SAME core, core resends hud.last with the seq "
                   "the plugin already saw; onFrame() drops it, so the glasses stay on GHOSTBUILD OFFLINE while the "
                   "phone says Connected, until the HUD next changes.")
def test_ws_drop_restores_the_step_on_glasses(rig):
    _, p = rig
    p.op("drop_ws")
    p.wait_shown("GHOSTBUILD OFFLINE")
    p.wait(lambda s: s["wsOpened"] == 2, what="ws reconnected")
    p.wait_shown("FOLD SQUARE INTO TRIANGLE", timeout=3)


def test_backend_restart_reconnects_but_session_is_lost(rig):
    core, p = rig
    p.op("tap")
    core.wait_hud(lambda h: core.completed() == {"c1": "confirmed"})
    seen = core.wait_hud(lambda h: h["seq"] > 1 and p.snapshot()["shown"] == "\n".join(h["lines"]),
                         what="glasses caught up with core")["seq"]
    assert seen > 1  # the new core starts at seq 1; see F-17 for the seq == 1 collision
    core.stop()
    p.wait_shown("GHOSTBUILD OFFLINE")
    core.start()
    s = p.wait_shown(IDLE, timeout=8)  # finding F-09: in-memory session gone; user must reload on the phone
    assert core.state()["engine"] == "IDLE" and core.completed() == {}
    assert s["status"].startswith("Connected")


@pytest.mark.xfail(strict=True, reason="F-17: hud.seq restarts at 1 on every core boot and onFrame() drops any "
                   "frame whose seq equals the last one seen. If the plugin's last frame from the old core had the "
                   "same seq as the new core's first frame, the glasses stay on GHOSTBUILD OFFLINE after a restart "
                   "while the phone says Connected. Observed intermittently in the restart test before this repro.")
def test_backend_restart_with_colliding_seq_restores_glasses(core, make_plugin):
    p = make_plugin(core)
    p.wait_shown(IDLE)
    assert core.hud()["seq"] == 1
    core.stop()
    p.wait_shown("GHOSTBUILD OFFLINE")
    core.start()
    p.wait(lambda s: s["wsOpened"] >= 2, timeout=8, what="ws reconnected to new core")
    p.wait_shown(IDLE, timeout=3)


def test_backend_crash_shows_offline(rig):
    core, p = rig
    core.kill()
    p.wait_shown(OFFLINE, timeout=3)


def test_long_outage_downgrades_to_polling_for_good(rig):
    core, p = rig
    seq = core.hud()["seq"]
    core.stop()
    p.wait(lambda s: "polling" in s["status"] or s["wsCreated"] >= 3, timeout=6, what="3 ws failures")
    core.start()
    core.load(CUP)
    resume_past(core, seq)
    p.wait_shown("FOLD SQUARE INTO TRIANGLE", timeout=6)
    s1 = p.snapshot()
    time.sleep(2.5)
    s2 = p.snapshot()
    assert "(polling)" in s2["status"]
    assert s2["wsCreated"] == s1["wsCreated"], "observed: no WebSocket retry once polling (finding F-11)"
    assert s2["polls"] > s1["polls"]


@pytest.mark.xfail(strict=True, reason="F-18: no WebSocket connect timeout. If the TCP connect succeeds but the "
                   "upgrade never completes (core mid-shutdown, captive portal, hung accept loop), the plugin sits "
                   "in 'Connecting' until the WebView's own timeout (browser-specific, can be minutes): no OFFLINE on "
                   "the glasses, no retry, no polling fallback.")
def test_websocket_handshake_that_never_completes_is_abandoned(make_plugin):
    hole = socket.socket()
    hole.bind(("127.0.0.1", 0))
    hole.listen(8)  # kernel completes TCP; nobody ever answers the HTTP upgrade

    class Hole:
        url = f"http://127.0.0.1:{hole.getsockname()[1]}"

    try:
        p = make_plugin(Hole)
        p.wait(lambda s: OFFLINE in (s["shown"] or "") or s["wsCreated"] >= 2 or s["polls"] > 0, timeout=8,
               what="plugin to give up on a dead handshake")
    finally:
        hole.close()


@pytest.mark.xfail(strict=True, reason="F-12: no heartbeat or staleness timeout. A core that stops answering "
                   "without closing TCP (laptop sleep, hung loop, Wi-Fi gone without FIN) leaves the last HUD frame "
                   "(possibly a step instruction or VERIFIED) on the glasses indefinitely. ttl_ms is ignored.")
def test_frozen_backend_is_flagged_on_glasses(rig):
    core, p = rig
    core.freeze()
    try:
        p.wait_shown("OFFLINE", timeout=6)
    finally:
        core.thaw()


def test_http_fallback_when_websocket_is_blocked(core, make_plugin):
    core.load(CUP)
    p = make_plugin(core, ws="blocked")
    s = p.wait_shown("FOLD SQUARE INTO TRIANGLE", timeout=8)
    assert "(polling)" in s["status"] and s["wsCreated"] == 3
    p.op("tap")
    p.wait_shown("DONE (YOU CONFIRMED)", timeout=3)
    tap = [f for f in p.snapshot()["fetches"] if f["url"] == "/input"]
    assert len(tap) == 1 and json.loads(tap[0]["body"])["kind"] == "tap"
    assert core.completed() == {"c1": "confirmed"}


@pytest.mark.xfail(strict=True, reason="F-08 (polling path): a failed poll shows GHOSTBUILD OFFLINE; the next "
                   "successful poll returns the same seq, which onFrame() drops, so OFFLINE sticks.")
def test_polling_blip_restores_the_step_on_glasses(core, make_plugin):
    core.load(CUP)
    p = make_plugin(core, ws="blocked")
    p.wait_shown("FOLD SQUARE INTO TRIANGLE", timeout=8)
    p.op("net", down=True)
    p.wait_shown("GHOSTBUILD OFFLINE")
    p.op("net", down=False)
    p.wait(lambda s: s["status"].endswith("(polling)"), what="poll recovered")
    p.wait_shown("FOLD SQUARE INTO TRIANGLE", timeout=3)


def test_tap_while_offline_is_dropped_not_replayed(rig):
    core, p = rig
    seq = core.hud()["seq"]
    core.stop()
    p.wait_shown("GHOSTBUILD OFFLINE")
    p.op("tap")
    time.sleep(0.3)
    assert p.snapshot()["fetches"][-1]["url"] == "/input"  # fell back to HTTP, which failed
    core.start()
    core.load(CUP)
    resume_past(core, seq)
    p.wait_shown("FOLD SQUARE INTO TRIANGLE", timeout=8)
    time.sleep(0.5)
    assert core.completed() == {}


def test_voice_while_core_is_down_reports_on_phone(rig):
    core, p = rig
    core.stop()
    p.wait_shown("GHOSTBUILD OFFLINE")
    hold(p, held=0.5)
    p.wait(lambda s: s["status"].startswith("Cannot reach") and s["status"].endswith("/audio"), what="audio error")


def test_voice_disabled_reaches_phone_and_glasses(make_core, make_plugin):
    core = make_core("--simulate-jig", voice_key=False)
    core.load(CUP)
    p = make_plugin(core)
    p.wait_shown("STEP 1/6")
    hold(p, held=0.5)
    p.wait(lambda s: s["status"].startswith("Voice error: voice disabled"), what="voice disabled on phone")
    p.wait_shown("VOICE OFF · TAP INSTEAD")


def test_repeat_frame_is_not_resent_to_glasses(rig):
    """Observed: 'repeat' makes core send a new seq with identical lines; the plugin dedupes on content and does
    not call textContainerUpgrade. Repeat therefore cannot recover a display update lost over BLE (F-13)."""
    core, p = rig
    n = len(p.snapshot()["upgrades"])
    seq = core.hud()["seq"]
    core.text("repeat")
    core.wait_hud(lambda h: h["seq"] > seq)
    time.sleep(0.3)
    assert len(p.snapshot()["upgrades"]) == n


@pytest.mark.xfail(strict=True, reason="F-14: frames carry source='simulated' but the plugin renders only `lines`, "
                   "so a simulated-jig '● VERIFIED' looks identical to a measured one on the glasses.")
def test_simulated_verified_is_labelled_on_glasses(core, make_plugin):
    core.load(LED)
    p = make_plugin(core)
    p.wait_shown("STEP 1/6")
    p.op("tap")
    p.wait_shown("STEP 2/6", timeout=4)
    core.sim_jig(led="missing")
    s = p.wait_shown("● VERIFIED")
    assert "SIM" in s["shown"]
