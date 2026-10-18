"""Voice lane end to end through TestClient. The STT is FakeStt (a clearly named test double): no microphone, no network."""

import asyncio
import json
import os

import pytest
from fastapi.testclient import TestClient

from contracts.models import G2Hello, GoalRequest
from ghostbuild_core import voice as V
from ghostbuild_core.cards import load_cards
from ghostbuild_core.clock import ManualClock
from ghostbuild_core.runtime import Runtime
from ghostbuild_core.server import create_app
from ghostbuild_core.voice import FakeStt, VoiceService

from conftest import REPO, Feeder, make_card_dict
from contracts.models import Card

AUDIO = b"\x7f\x01\xfe\x02" * 800  # marker bytes: must never reach disk or logs


def inp(g):
    return {"type": "g2_input", "v": 2, "gesture": g, "seq_seen": 0, "surface": "g2"}


class Rig:
    def __init__(self, tmp_path, cards, asset_root, *, voice, stt=None, factory=None):
        self.clock = ManualClock()
        self.rt = Runtime(cards, clock=self.clock, log_dir=tmp_path / "logs", asset_root=asset_root)
        self.stt = stt
        self.svc = VoiceService(self.rt, factory or (lambda: self.stt)) if voice else None
        self.client = TestClient(create_app(self.rt, tick_interval=None, sim_interval=None, web_dir=tmp_path / "noweb"))
        self.client.__enter__()
        self.feed = Feeder(self.rt.engine, self.clock)

    # --- session / engine
    def to_menu(self):
        self.rt.hello(G2Hello(client_id="t1", session_id=None))
        self.clock.advance(2600)
        self.rt.tick()
        assert self.rt.sessions.active.phase == "menu"

    def to_task(self, mode="fix", text=None, feed=True):
        self.to_menu()
        res = self.rt.resolve_goal(GoalRequest(session_id=self.rt.sessions.active.id, mode=mode, via="phone_text", text=text))
        assert res.status == "supported"
        self.advance(3000 if feed else 1000, **({} if feed else {"obs": False}))

    obs_kw: dict = {}

    def advance(self, ms, **kw):
        """Step the clock; keeps feeding observations like the current scenario (healthy unless fault() was called)."""
        kw = kw or self.obs_kw
        for _ in range(ms // 100):
            self.clock.advance(100)
            if kw.get("obs", True):
                self.rt.ingest(self.feed.obs(**{k: v for k, v in kw.items() if k != "obs"}))
            self.rt.tick()

    def fault(self):
        self.obs_kw = {"luma": 6.0, "std": 1.0}
        self.advance(2500)
        assert self.rt.engine.state == "FAULT"
        self.advance(2500)

    def healthy(self, ms=1500):
        self.obs_kw = {}
        self.advance(ms)

    # --- voice
    def hold(self, g):
        r = self.client.post("/input", content=json.dumps(inp(g)))
        assert r.status_code == 200

    def say(self, transcript, *, consent=True, audio=AUDIO, release=True):
        """Hold, stream audio on /ws/voice, release: the same order the plugin uses."""
        self.stt = self.stt or FakeStt(transcript)
        self.stt.transcript = transcript
        self.hold("hold_start")
        with self.client.websocket_connect("/ws/voice?session_id=x") as ws:
            ws.send_json({"type": "start", "consent": consent})
            if consent:
                if audio:
                    ws.send_bytes(audio)
                    ws.send_bytes(audio)
                ws.send_json({"type": "end"})
                if release:
                    self.hold("hold_end")
                return ws.receive_json()
            return ws.receive_json()

    @property
    def cue(self):
        c = self.rt.hud.current
        return (c.mode, c.cue.line1 if c.cue else None, c.cue.line2 if c.cue else None)

    def close(self):
        self.client.__exit__(None, None, None)


@pytest.fixture
def mk(tmp_path, card, asset_root):
    rigs = []

    def make(voice=True, cards=None, root=None, **kw):
        r = Rig(tmp_path, cards or [card], root or asset_root, voice=voice, **kw)
        rigs.append(r)
        return r

    yield make
    for r in rigs:
        r.close()


# ----------------------------------------------------------------------------- off by default
def test_voice_off_changes_nothing(mk):
    r = mk(voice=False)
    r.to_task()
    r.fault()
    before = (r.rt.hud.current.seq, r.cue)
    assert r.client.get("/health").json()["voice"] == "off"
    r.hold("hold_start")
    r.hold("hold_end")
    assert (r.rt.hud.current.seq, r.cue) == before
    with pytest.raises(Exception):
        with r.client.websocket_connect("/ws/voice"):
            pass
    assert r.client.post("/input", content=json.dumps(inp("press"))).status_code == 200  # touch still works
    assert r.rt.hud.current.mode == "visual"


def test_health_reports_voice_on_and_stays_a_valid_health(mk):
    r = mk(stt=FakeStt("x"))
    h = r.client.get("/health").json()
    assert h["voice"] == "on"
    from contracts.models import Health

    Health.model_validate({k: v for k, v in h.items() if k != "voice"})


# ----------------------------------------------------------------------------- HUD states
def test_hold_start_listening_hold_end_thinking(mk):
    r = mk(stt=FakeStt("where is it"))
    r.to_task()
    r.fault()
    r.hold("hold_start")
    assert r.cue == ("ask", "LISTENING", "RELEASE WHEN DONE")
    r.hold("hold_end")
    assert r.cue == ("ask", "THINKING", "")


def test_disconnected_audio_immediately_falls_back_then_restores_previous_screen(mk):
    r = mk(stt=FakeStt("x"))
    r.to_task()
    r.fault()
    prev = r.cue
    assert prev[0] == "intervene"
    r.hold("hold_start")
    with r.client.websocket_connect("/ws/voice") as ws:  # the plugin opened the socket, then never sent `end`
        ws.send_json({"type": "start", "consent": True})
        ws.send_bytes(AUDIO)
    r.hold("hold_end")
    assert r.cue == ("ask", "VOICE UNAVAILABLE", "USE TOUCH")
    r.advance(5200)
    assert r.cue[:2] == prev[:2] and r.rt.engine.state == "FAULT"  # same fault cue (line2 may be the engine's own PRESS FOR PICTURE offer)


def test_empty_transcript_is_didnt_catch(mk):
    r = mk(stt=FakeStt(""))
    r.to_task()
    r.fault()
    r.say("", audio=b"")
    assert r.cue[1] == "DIDN'T CATCH THAT"


# ----------------------------------------------------------------------------- grounded answers in a task
@pytest.mark.parametrize("phrase,view", [("where is it?", "where"), ("how do I fix it?", "how"), ("what should it look like?", "correct")])
def test_guide_views_by_voice(mk, phrase, view):
    r = mk()
    r.to_task()
    r.fault()
    assert r.say(phrase)["type"] == "done"
    f = r.rt.hud.current
    assert f.mode == "visual" and f.image.view == view
    assert r.rt.engine.state == "FAULT"  # a voice command never clears a fault


def test_next_and_previous_picture(mk):
    r = mk()
    r.to_task()
    r.fault()
    r.say("where is it")
    r.say("show the next picture")
    assert r.rt.hud.current.image.view == "how"
    r.say("next")
    assert r.rt.hud.current.image.view == "correct"
    r.say("go back")
    assert r.rt.hud.current.image.view == "how"


def test_context_persists_across_questions(mk):
    r = mk()
    r.to_task()
    r.fault()
    r.say("how do i fix it")
    r.say("why does it matter")  # answer overlays, then the HOW picture is still the underlying screen
    assert r.cue[0] == "ask"
    r.advance(5200)
    f = r.rt.hud.current
    assert f.mode == "visual" and f.image.view == "how"


def test_why_too_long_goes_to_phone_with_full_card_text(mk):
    r = mk()
    r.to_task()
    r.fault()
    r.say("why does it matter")
    assert r.cue == ("ask", "NOT IN MY CARD", "SEE PHONE")
    why = r.rt.engine.card.tests[0].checks[0].why
    ev = [e for e in r.client.get("/state").json()["events"] if e["text"].startswith("voice answer (why)")]
    assert ev and why in ev[-1]["text"] and ev[-1]["label"] == "AUTHORED DEMO METADATA"


def test_why_short_card_text_on_hud_two_lines(mk, asset_root):
    d = make_card_dict()
    d["tests"][0]["checks"][0]["why"] = "Dark frames mean low light"
    r = mk(cards=[Card.model_validate(d)])
    r.to_task()
    r.fault()
    r.say("why does it matter")
    c = r.rt.hud.current.cue
    assert r.rt.hud.current.mode == "ask" and (c.line1 + " " + c.line2).split() == "DARK FRAMES MEAN LOW LIGHT".split()


def test_fallback_shows_next_documented_check(mk):
    d = make_card_dict()
    d["tests"][0]["checks"].append(
        {"when": [], "action": {"line1": "CHECK USB CABLE", "line2": "AT THE PI"}, "why": "Cable.", "cites": [], "guide_id": None}
    )
    r = mk(cards=[Card.model_validate(d)])
    r.to_task()
    r.fault()
    r.say("what if that didn't work")
    assert r.cue == ("ask", "CHECK USB CABLE", "AT THE PI")


def test_fallback_without_more_checks_is_honest(mk):
    r = mk()
    r.to_task()
    r.fault()
    r.say("what if that didn't work")
    assert r.cue == ("ask", "NOT IN MY CARD", "SEE PHONE")


def test_status_in_fault_shows_the_card_fact_not_a_diagnosis_or_fix(mk):
    r = mk()
    r.to_task()
    r.fault()
    r.say("what's wrong")
    assert r.cue[0] == "ask" and r.cue[1] == r.rt.engine.card.tests[0].fact.line1
    assert r.rt.engine.state == "FAULT"


def test_unknown_intent_is_honest(mk):
    r = mk()
    r.to_task()
    r.fault()
    r.say("banana smoothie")
    assert r.cue == ("ask", "NOT SURE", "TRY: WHERE? HOW?")


def test_healthy_question_gets_measured_status_only(mk):
    r = mk()
    r.to_task()
    r.healthy()
    r.say("is it fixed")
    assert r.cue == ("verified", "ALL TESTS PASSING", "LIVE")


def test_healthy_without_measurement_never_says_verified(mk):
    r = mk()
    r.to_task(feed=False)  # task started, no observation received yet (link not yet timed out)
    r.say("is it fixed")
    assert r.cue == ("ask", "NO DATA YET", "WAITING FOR PI")
    assert all(f.mode != "verified" for f in r.rt.hud.frames)


def test_error_state_suppresses_answers(mk):
    r = mk()
    r.to_task()
    r.fault()
    r.advance(6000, obs=False)  # Pi silent: PI LINK LOST
    assert r.cue[0] == "error"
    r.say("where is it")
    assert r.cue[0] == "error"


# ----------------------------------------------------------------------------- goals by voice
@pytest.fixture
def real_cards():
    return load_cards(REPO / "knowledge" / "cards")


def test_goal_by_voice_fix(mk, real_cards):
    r = mk(cards=real_cards, root=REPO)
    r.to_menu()
    r.say("my camera view is black")
    s = r.rt.sessions.active
    assert s.phase == "task" and s.goal == "fix" and s.card_id == "camera_lens"
    assert r.rt.hud.current.cue.line1.startswith("FIX:")
    log = "".join(p.read_text() for p in (r.rt.elog.path.parent).glob("session-*.jsonl"))
    assert '"via": "voice"' in log


def test_goal_by_voice_build(mk, real_cards):
    r = mk(cards=real_cards, root=REPO)
    r.to_menu()
    r.say("set up the pi camera")
    s = r.rt.sessions.active
    assert s.phase == "task" and s.goal == "build" and s.card_id == "pi_camera_setup"


def test_unsupported_goal_by_voice_is_honest(mk, real_cards):
    r = mk(cards=real_cards, root=REPO)
    r.to_menu()
    r.say("help me build a rocket")
    assert r.rt.sessions.active.phase == "menu"
    assert r.cue[1] == "NOT SUPPORTED YET"


# ----------------------------------------------------------------------------- failures, consent, privacy
def test_provider_start_failure_shows_unavailable_and_touch_still_works(mk):
    r = mk(stt=FakeStt("x", fail_start=True))
    r.to_task()
    r.fault()
    r.hold("hold_start")
    with r.client.websocket_connect("/ws/voice") as ws:
        ws.send_json({"type": "start", "consent": True})
        assert ws.receive_json()["type"] == "unavailable"
    assert r.cue == ("ask", "VOICE UNAVAILABLE", "USE TOUCH")
    r.advance(5200)
    assert r.client.post("/input", content=json.dumps(inp("press"))).status_code == 200
    assert r.rt.hud.current.mode == "visual"  # the existing press -> WHERE picture


def test_provider_finalize_failure_shows_unavailable(mk):
    r = mk(stt=FakeStt("x", fail_finalize=True))
    r.to_task()
    r.fault()
    r.say("where is it")
    assert r.cue == ("ask", "VOICE UNAVAILABLE", "USE TOUCH")


def test_no_api_key_shows_unavailable(mk, monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    r = mk(factory=V.elevenlabs_factory)
    r.to_task()
    r.fault()
    r.hold("hold_start")
    with r.client.websocket_connect("/ws/voice") as ws:
        ws.send_json({"type": "start", "consent": True})
        assert ws.receive_json()["type"] == "unavailable"
    assert r.cue == ("ask", "VOICE UNAVAILABLE", "USE TOUCH")


def test_release_without_any_audio_socket_falls_back_after_grace(mk):
    r = mk(stt=FakeStt("x"))
    r.to_task()
    r.fault()
    r.hold("hold_start")
    r.hold("hold_end")
    r.advance(1800)
    assert r.cue == ("ask", "THINKING", "")
    r.advance(300)
    assert r.cue == ("ask", "VOICE UNAVAILABLE", "USE TOUCH")


def test_plugin_abort_shows_fallback_immediately(mk):
    r = mk(stt=FakeStt("x"))
    r.to_task()
    r.fault()
    r.hold("hold_start")
    with r.client.websocket_connect("/ws/voice") as ws:
        ws.send_json({"type": "start", "consent": True})
        ws.send_json({"type": "abort", "reason": "no_audio"})
    r.hold("hold_end")
    r.advance(100)
    assert r.cue == ("ask", "VOICE UNAVAILABLE", "USE TOUCH")


def test_consent_gate_shows_screen_and_drops_audio(mk):
    stt = FakeStt("where is it")
    r = mk(stt=stt)
    r.to_task()
    r.fault()
    out = r.say("where is it", consent=False)
    assert out["type"] == "consent_required"
    assert r.cue == ("ask", "HOLD TO TALK", "AUDIO SENT TO SERVER")
    assert stt.bytes == 0  # no provider was ever fed


def test_transcript_logged_with_true_origin_and_no_audio_persisted(mk, tmp_path):
    r = mk()
    r.to_task()
    r.fault()
    r.say("where is it")
    r.say("why does it matter")
    r.client.__exit__(None, None, None)
    r.client.__enter__()
    files = [p for p in (tmp_path / "logs").rglob("*") if p.is_file()]
    assert files, "log dir should have content"
    for p in files:
        assert AUDIO[:16] not in p.read_bytes(), f"raw audio found in {p}"
        assert p.suffix in (".jsonl", ".json"), p
    recs = [json.loads(line) for p in (tmp_path / "logs").rglob("session-*.jsonl") for line in p.read_text().splitlines()]
    tr = [x for x in recs if x["kind"] == "voice_transcript"]
    assert [x["text"] for x in tr] == ["where is it", "why does it matter"]
    assert all(x["provider"] == "FakeStt" and x["origin"] == "fake_test" for x in tr)
    assert not any("audio" in json.dumps(x).lower() for x in recs if x["kind"].startswith("voice"))


def test_late_transcript_after_timeout_is_ignored(mk):
    r = mk(stt=FakeStt("where is it"))
    r.to_task()
    r.fault()
    r.hold("hold_start")
    r.svc.socket_started = True  # plugin opened the socket but the provider never answered
    r.hold("hold_end")
    r.advance(8300)
    assert r.cue[1] == "DIDN'T CATCH THAT"
    r.svc.on_transcript("where is it", "FakeStt", "fake_test")
    assert r.cue[1] == "DIDN'T CATCH THAT"




def test_phone_ptt_alone_starts_and_finishes_lifecycle(mk):
    r = mk(stt=FakeStt("where is it"))
    r.to_task()
    r.fault()
    with r.client.websocket_connect("/ws/voice") as ws:
        ws.send_json({"type": "start", "consent": True})
        ws.send_bytes(AUDIO)
        ws.send_json({"type": "end"})
        result = ws.receive_json()
    assert result["type"] == "done" and result["origin"] == "fake_test"
    assert result["transcript"] == "where is it" and result["ignored"] is False
    assert r.rt.hud.current.mode == "visual"


def test_changed_step_rejects_late_done_transcript(mk):
    from pbhelpers import make_card
    r = mk(cards=[make_card(3)], stt=FakeStt("done"))
    r.to_task(mode="build", text="synthetic", feed=False)
    r.advance(1600, obs=False)
    r.hold("hold_start")
    with r.client.websocket_connect("/ws/voice") as ws:
        ws.send_json({"type": "start", "consent": True})
        ws.send_bytes(AUDIO)
        # Another interface advances while STT is pending. The transcript belongs to s0.
        r.rt.playbook.index = 1
        ws.send_json({"type": "end"})
        result = ws.receive_json()
    assert result["ignored"] is True and result["transcript"] == ""
    assert r.rt.playbook.index == 1 and r.rt.playbook.confirmed == []


def test_duplicate_start_does_not_replace_provider_or_repeat_action(mk):
    stt = FakeStt("where is it")
    r = mk(stt=stt)
    r.to_task()
    r.fault()
    with r.client.websocket_connect("/ws/voice") as ws:
        ws.send_json({"type": "start", "consent": True})
        ws.send_bytes(AUDIO)
        ws.send_json({"type": "start", "consent": True})
        assert ws.receive_json()["type"] == "busy"
        ws.send_json({"type": "end"})
        assert ws.receive_json()["type"] == "done"
    assert stt.bytes == len(AUDIO) and stt.closed


def test_oversized_or_odd_pcm_is_rejected_before_provider_feed(mk):
    stt = FakeStt("done")
    r = mk(stt=stt)
    r.to_task()
    with r.client.websocket_connect("/ws/voice") as ws:
        ws.send_json({"type": "start", "consent": True})
        ws.send_bytes(b"\0" * (V.MAX_AUDIO_BYTES + 2))
        assert ws.receive_json()["type"] == "unavailable"
    assert stt.bytes == 0 and stt.closed


def test_done_response_contains_documented_card_answer_for_phone_audio(mk):
    from pbhelpers import make_card
    r = mk(cards=[make_card(3)], stt=FakeStt("why"))
    r.to_task(mode="build", text="synthetic", feed=False)
    with r.client.websocket_connect("/ws/voice") as ws:
        ws.send_json({"type": "start", "consent": True})
        ws.send_bytes(AUDIO)
        ws.send_json({"type": "end"})
        result = ws.receive_json()
    assert result["text"] == "WHY 0: SAFETY"
    assert result["origin"] == "fake_test"  # never represent this fixture as microphone/provider evidence


def test_abort_while_transcribing_never_applies_the_late_command(mk):
    stt = FakeStt("where is it", delay_s=0.2)
    r = mk(stt=stt)
    r.to_task()
    r.fault()
    with r.client.websocket_connect("/ws/voice") as ws:
        ws.send_json({"type": "start", "consent": True})
        ws.send_bytes(AUDIO)
        ws.send_json({"type": "end"})
        ws.send_json({"type": "abort"})
        assert ws.receive_json()["type"] == "unavailable"
    assert stt.closed and r.rt.hud.current.mode != "visual"
    assert r.cue[1] == "VOICE UNAVAILABLE"


def test_other_socket_cannot_cancel_active_capture(mk):
    stt = FakeStt("where is it")
    r = mk(stt=stt)
    r.to_task()
    r.fault()
    with r.client.websocket_connect("/ws/voice") as active:
        active.send_json({"type": "start", "consent": True})
        active.send_bytes(AUDIO)
        with r.client.websocket_connect("/ws/voice") as other:
            other.send_json({"type": "start", "consent": True})
            assert other.receive_json()["type"] == "busy"
            other.send_json({"type": "abort"})
        active.send_json({"type": "end"})
        assert active.receive_json()["type"] == "done"
    assert r.rt.hud.current.mode == "visual" and stt.closed
