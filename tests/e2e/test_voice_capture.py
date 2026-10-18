"""1. Voice capture and input transport, core side: POST /ptt + POST /audio -> stt.transcribe -> engine.

Real core subprocess; the speech-to-text provider is the local FakeSTT (never ElevenLabs, dummy key only).
Plugin-side hold-to-talk (long press, PCM buffering, tail, tap guard) is in test_g2_plugin.py.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import pytest

from tests.e2e.harness.core_proc import DUMMY_KEY, free_port
from tests.fixtures import audio

CUP = "origami-cup-v1"
LISTENING, HEARING, MISSED, FAILED, OFF = (
    "LISTENING...", "HEARING YOU...", "DIDN'T CATCH THAT", "VOICE FAILED · TAP INSTEAD", "VOICE OFF · TAP INSTEAD")
ROOT = Path(__file__).resolve().parents[2]


def audio_post(core, clip: bytes, timeout: float = 30.0):
    return core.post("/audio", raw=clip, timeout=timeout)


def assert_untouched(core) -> None:
    s = core.state()
    assert s["step_index"] == 0 and s["completed"] == [], s


def test_ptt_start_shows_listening_and_cancel_restores(core):
    core.load(CUP)
    base = core.lines()
    assert core.post("/ptt", {"phase": "start"}) == (200, {"ok": True, "voice": True})
    core.wait_status(LISTENING)
    core.post("/ptt", {"phase": "cancel"})
    core.wait_hud(lambda h: h["lines"] == base, what="step HUD restored")
    assert_untouched(core)


def test_voice_off_without_key_falls_back_to_tap(make_core, stt):
    core = make_core("--simulate-jig", voice_key=False)
    core.load(CUP)
    assert core.get("/health")[1]["voice"] is False
    assert core.post("/ptt", {"phase": "start"})[1] == {"ok": True, "voice": False}
    core.wait_status(OFF)
    code, body = audio_post(core, audio.tone(1.0))
    assert code == 200 and body["ok"] is False and "voice disabled" in body["error"]
    assert stt.requests == []
    core.tap()
    core.wait_hud(lambda h: core.completed() == {"c1": "confirmed"}, what="tap still confirms")


def test_gb_voice_0_turns_voice_off_even_with_key(make_core, stt):
    core = make_core(env={"GB_VOICE": "0"})
    assert core.get("/health")[1]["voice"] is False
    assert audio_post(core, audio.tone(1.0))[1]["ok"] is False and stt.requests == []


@pytest.mark.parametrize("clip", [b"", audio.tone(0.29)], ids=["empty", "below-0.3s"])
def test_empty_or_short_clip_never_calls_provider(core, stt, clip):
    core.load(CUP)
    assert audio_post(core, clip) == (200, {"ok": True, "text": ""})
    core.wait_status(MISSED)
    assert stt.requests == []
    assert_untouched(core)


@pytest.mark.parametrize("transcript", ["", "   "], ids=["silence", "whitespace"])
def test_silence_transcript_is_ignored(core, stt, transcript):
    core.load(CUP)
    stt.say(transcript)
    assert audio_post(core, audio.silence(1.0)) == (200, {"ok": True, "text": ""})
    core.wait_status(MISSED)
    assert len(stt.requests) == 1
    assert_untouched(core)


@pytest.mark.parametrize("clip", [audio.odd_length(), audio.wav_file(), audio.not_audio()],
                         ids=["odd-byte-count", "wav-container", "not-audio"])
def test_malformed_pcm_fails_safe_then_recovers(core, stt, clip):
    """Core does not validate the clip; it forwards it as-is. A provider rejection must leave the step untouched."""
    core.load(CUP)
    stt.say(None, status=400, body=b'{"detail":{"status":"invalid_audio"}}')
    code, body = audio_post(core, clip)
    assert code == 200 and body["ok"] is False
    assert stt.requests[-1].file == clip  # observed: forwarded unvalidated (finding F-07)
    core.wait_status(FAILED)
    assert_untouched(core)
    stt.say("done")
    assert audio_post(core, audio.tone(1.0))[1] == {"ok": True, "text": "done"}
    core.wait_hud(lambda h: core.completed() == {"c1": "confirmed"}, what="recovered voice command")


@pytest.mark.parametrize("status,body", [
    (401, b'{"detail":{"status":"invalid_api_key"}}'),
    (429, b'{"detail":{"status":"too_many_concurrent_requests"}}'),
    (500, b'{"detail":"internal"}'),
    (503, b"Service Unavailable"),
    (200, b"<html>captive portal</html>"),
], ids=["401", "429", "500", "503", "200-not-json"])
def test_provider_error_fails_safe_and_recovers(core, stt, status, body):
    core.load(CUP)
    stt.say(None, status=status, body=body)
    code, res = audio_post(core, audio.tone(1.0))
    assert code == 200 and res["ok"] is False and res["error"]
    assert DUMMY_KEY not in json.dumps(res)
    core.wait_status(FAILED)
    assert_untouched(core)
    stt.say("done")
    assert audio_post(core, audio.tone(1.0))[1] == {"ok": True, "text": "done"}
    core.wait_hud(lambda h: core.completed() == {"c1": "confirmed"}, what="recovered voice command")


@pytest.mark.parametrize("body", [b'{"text": null}', b"{}", b""], ids=["text-null", "no-text", "empty-body"])
def test_provider_empty_answer_is_didnt_catch_that(core, stt, body):
    core.load(CUP)
    stt.say(None, body=body)
    assert audio_post(core, audio.tone(1.0)) == (200, {"ok": True, "text": ""})
    core.wait_status(MISSED)
    assert_untouched(core)


def test_provider_unreachable_fails_safe(make_core):
    core = make_core(env={"GB_TEST_STT_URL": f"http://127.0.0.1:{free_port()}/v1/speech-to-text"})
    core.load(CUP)
    code, res = audio_post(core, audio.tone(1.0))
    assert code == 200 and res["ok"] is False and "refused" in res["error"].lower()
    core.wait_status(FAILED)
    assert_untouched(core)


def test_provider_request_format_and_key_stays_server_side(core, stt):
    core.load(CUP)
    clip = audio.tone(1.2)
    stt.say("help")
    assert audio_post(core, clip)[1] == {"ok": True, "text": "help"}
    seen = stt.requests[-1]
    assert seen.fields == {"model_id": "scribe_v1", "file_format": "pcm_s16le_16", "language_code": "en",
                           "tag_audio_events": "false"}
    assert seen.file == clip and seen.headers["xi-api-key"] == DUMMY_KEY
    for path in ("/state", "/health"):
        assert DUMMY_KEY not in json.dumps(core.get(path)[1])
    plugin_src = (ROOT / "g2" / "src" / "main.ts").read_text()
    assert "xi-api-key" not in plugin_src and "ELEVENLABS" not in plugin_src and "elevenlabs.io" not in plugin_src


def test_duplicate_clip_pair_completes_only_one_step(core, stt):
    """Two identical "next" clips (e.g. a double release) -> step 1 confirmed, ack skipped, step 2 NOT confirmed."""
    core.load(CUP)
    for _ in range(2):
        stt.say("next")
        assert audio_post(core, audio.tone(1.0))[1]["text"] == "next"
    core.wait_hud(lambda h: h["step_index"] == 1, what="step 2")
    time.sleep(0.3)
    assert core.completed() == {"c1": "confirmed"}


def _in_thread(fn):
    out: dict = {}
    t = threading.Thread(target=lambda: out.setdefault("r", fn()), daemon=True)
    t.start()
    return t, out


def test_slow_provider_never_blocks_the_live_loop(core, stt):
    core.load(CUP)
    stt.say("what is the capital of france", delay=3.0)
    t, out = _in_thread(lambda: audio_post(core, audio.tone(1.0)))
    core.wait_status(HEARING)
    t0 = time.time()
    core.tap()
    core.wait_hud(lambda h: h["kind"] == "confirmed", what="tap acknowledged during STT")
    assert time.time() - t0 < 1.0, "tap must be handled while speech-to-text is in flight"
    t.join(10)
    assert out["r"][1]["ok"] is True
    core.wait_status("ASK A MENTOR", timeout=4)


@pytest.mark.slow
def test_provider_timeout_fails_safe_and_drops_late_transcript(core, stt):
    core.load(CUP)
    stt.say("done", delay=17.0)  # stt.transcribe times out at 15 s
    t0 = time.time()
    code, res = audio_post(core, audio.tone(1.0))
    took = time.time() - t0
    assert code == 200 and res["ok"] is False and "timed out" in res["error"].lower()
    assert 14.0 <= took <= 17.0, took
    core.wait_status(FAILED)
    assert_untouched(core)


@pytest.mark.xfail(strict=True, reason="F-03: a transcript is applied to whichever step is current when STT returns. "
                   "/audio carries no seq_seen/step binding, so a slow 'done' confirms a step the user never saw.")
def test_late_transcript_does_not_confirm_the_next_step(core, stt):
    core.load(CUP)
    stt.say("done", delay=2.5)  # user says "done", sees nothing for 2 s, taps instead
    t, out = _in_thread(lambda: audio_post(core, audio.tone(1.0)))
    core.wait_status(HEARING)
    core.tap()
    core.wait_hud(lambda h: h["step_index"] == 1, what="ack advanced to step 2")
    t.join(10)
    assert out["r"][1]["text"] == "done"
    time.sleep(0.4)
    assert core.completed() == {"c1": "confirmed"}, f"step 2 confirmed by a stale transcript: {core.completed()}"
