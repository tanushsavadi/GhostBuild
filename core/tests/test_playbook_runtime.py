"""Playbook through Runtime/Session/server: onboarding, chooser, resume, restart, free-text scoring, research, /ask."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from contracts.models import Card, G2Hello, G2Input, GoalRequest
from ghostbuild_core import goal
from ghostbuild_core.clock import ManualClock
from ghostbuild_core.runtime import Runtime
from ghostbuild_core.server import create_app

from conftest import make_card_dict
from pbhelpers import Obs, example_card, make_card, guide_dict, verify_led, write_pngs


def gi(g):
    return G2Input(gesture=g, seq_seen=0)


def boot(cards, tmp_path, clock=None, asset_root=None):
    clock = clock or ManualClock()
    rt = Runtime(cards, clock=clock, log_dir=tmp_path / "logs", asset_root=asset_root or tmp_path / "root")
    rt.clock = clock
    return rt


def to_menu(rt, client="g2-1"):
    rt.hello(G2Hello(client_id=client, session_id=None))
    rt.clock.advance(2600)
    rt.tick()
    assert rt.hud.current.mode == "menu"


def swipes(rt, n):
    for _ in range(n):
        rt.handle_input(gi("swipe_down"))


def settle(rt, ms=2700):
    for _ in range(ms // 100):
        rt.clock.advance(100)
        rt.tick()


def start_build(rt):
    to_menu(rt)
    swipes(rt, 1)
    f = rt.handle_input(gi("press"))
    return f


@pytest.fixture
def led():
    return example_card()


@pytest.fixture
def lens(card):
    return card


def cur(rt):
    return rt.hud.current


def confirm(rt):
    rt.clock.advance(1600)
    rt.tick()
    return rt.handle_input(gi("swipe_down"))


# ------------------------------------------------------------------ onboarding into a playbook
def test_build_menu_single_card_starts_playbook_with_short_cue(led, lens, tmp_path):
    rt = boot([lens, led], tmp_path)
    f = start_build(rt)
    assert f.mode == "intervene" and f.cue.line1 == "BUILD: LIGHT AN LED ON A" and len(f.cue.line1) <= 24 and f.ttl_ms == 2500
    assert rt.playbook is not None and rt.state().engine == "PLAYBOOK"
    settle(rt)
    assert cur(rt).mode == "step" and cur(rt).step.step_id == "parts"
    st = rt.state()
    assert st.playbook.step_index == 0 and st.playbook.step_count == 3 and st.card_id == "led_breadboard" and st.step_id == "parts"


def test_gesture_during_task_start_cue_only_reveals_the_first_step(led, tmp_path):
    rt = boot([led], tmp_path)
    to_menu(rt)
    f = rt.handle_input(gi("press"))  # only a build card: FIX has none; go to BUILD instead
    assert f.mode == "uncertain" and f.cue.line1 == "NOTHING LOADED YET"
    swipes(rt, 1)
    rt.handle_input(gi("press"))
    assert cur(rt).cue.line1.startswith("BUILD:")
    rt.clock.advance(300)
    rt.handle_input(gi("swipe_down"))  # dismisses the cue; must NOT confirm a step nobody has seen
    assert cur(rt).mode == "step" and cur(rt).step.index == 0
    assert rt.state().playbook.confirmed == []


def test_fix_with_zero_cards_is_honest_and_not_a_guess(led, tmp_path):
    rt = boot([led], tmp_path)
    to_menu(rt)
    f = rt.handle_input(gi("press"))  # FIX selected, only a build card loaded
    assert (f.cue.line1, f.cue.line2) == ("NOTHING LOADED YET", "TRY THE OTHER OPTION") and f.mode == "uncertain"


def test_full_playbook_walk_through_runtime_no_pi(led, tmp_path):
    write_pngs(tmp_path / "root", prefix="knowledge/guides/led", names=("where",))
    rt = boot([led], tmp_path)
    start_build(rt)
    settle(rt)
    assert confirm(rt).step.step_id == "led"  # step 0 manual
    f = rt.handle_input(gi("press"))  # step 1 has guide 'led' and a real PNG
    assert f.mode == "visual" and f.image.guide_id == "led" and f.step.step_id == "led"
    assert rt.handle_input(gi("press")).mode == "step"
    # measured step 2 can't be completed without evidence: NO PI DATA
    confirm(rt)
    assert cur(rt).step.step_id == "power"
    rt.clock.advance(1600)
    f = rt.handle_input(gi("swipe_down"))
    assert f.mode == "uncertain" and f.cue.line1 == "NO PI DATA"
    settle(rt, 2100)
    # now evidence arrives (a simulated LED command): advances and finishes with the mixed wording
    o = Obs(rt.clock)
    for _ in range(8):
        rt.clock.advance(100)
        rt.ingest(o(led=True, source="simulated", camera=False))
        rt.tick()
    assert [x.cue.line1 for x in rt.hud.frames if x.mode == "verified"] == ["● CHECK PASSED"]
    settle(rt, 3000)
    done = [x for x in rt.hud.frames if x.cue and x.cue.line1 == "✓ ALL STEPS DONE"]
    assert len(done) == 1 and done[0].cue.line2 == "SOME CHECKED, SOME BY YOU"
    labels = {e.label for e in rt.state().events}
    assert {"HUMAN CONFIRMED", "SIMULATED"} <= labels and "MEASURED LIVE" not in labels
    assert [f.source for f in rt.hud.frames if f.mode == "verified"] == ["simulated"] and rt.hud.frames[-1].source == "manual"


# ------------------------------------------------------------------ resume
def test_reconnect_resumes_same_step_and_never_rewelcomes(led, tmp_path):
    rt = boot([led], tmp_path)
    start_build(rt)
    settle(rt)
    confirm(rt)
    sid = rt.session().id
    n_welcome = sum(1 for f in rt.hud.frames if f.mode == "welcome")
    f = rt.hello(G2Hello(client_id="g2-1", session_id=sid))
    assert f.mode == "step" and f.step.index == 1 and f.session_id == sid
    assert sum(1 for f in rt.hud.frames if f.mode == "welcome") == n_welcome == 1
    assert rt.state().playbook.step_index == 1 and rt.state().playbook.confirmed == ["parts"]


def test_restart_persists_step_index_and_confirmations(led, tmp_path):
    c1 = ManualClock()
    rt = boot([led], tmp_path, c1)
    start_build(rt)
    settle(rt)
    confirm(rt)
    sid = rt.session().id
    rt.close()
    rt2 = boot([led], tmp_path, ManualClock())
    assert rt2.playbook is not None and rt2.state().playbook.step_index == 1
    f = rt2.hello(G2Hello(client_id="g2-1", session_id=sid))
    assert f.mode == "step" and f.step.index == 1 and f.step.step_id == "led" and f.step.check == "manual"
    assert rt2.state().playbook.confirmed == ["parts"]
    assert not [x for x in rt2.hud.frames if x.mode == "welcome"]
    data = json.loads((tmp_path / "logs" / "sessions.json").read_text())
    assert data["progress"][sid]["step_index"] == 1


def test_new_goal_restarts_the_playbook_from_step_zero(led, tmp_path):
    rt = boot([led], tmp_path)
    start_build(rt)
    settle(rt)
    confirm(rt)
    sid = rt.session().id
    res = rt.resolve_goal(GoalRequest(session_id=sid, mode="build", via="phone_text", text="light an LED"))
    assert res.status == "supported"
    assert rt.state().playbook.step_index == 0 and rt.state().playbook.confirmed == []


def test_health_is_not_unhealthy_just_because_there_is_no_pi_on_a_manual_step(led, tmp_path):
    rt = boot([led], tmp_path)
    start_build(rt)
    settle(rt)
    h = rt.health()
    assert h.pi_link == "down" and h.ok is True
    confirm(rt), confirm(rt)  # to the measured step
    assert rt.health().ok is False


def test_fault_card_still_uses_the_engine_and_playbook_to_fault_switch(led, lens, tmp_path):
    rt = boot([lens, led], tmp_path)
    start_build(rt)
    assert rt.playbook is not None and rt.engine.passive
    sid = rt.session().id
    res = rt.resolve_goal(GoalRequest(session_id=sid, mode="fix", via="phone_text", text="camera is black"))
    assert res.status == "supported" and rt.playbook is None and not rt.engine.passive
    assert rt.state().engine in ("NO_LINK", "HEALTHY") and rt.state().card_id == "camera_lens"


def test_passive_engine_never_writes_error_frames_for_a_playbook(led, tmp_path):
    rt = boot([led], tmp_path)
    start_build(rt)
    settle(rt, 20_000)
    assert not [f for f in rt.hud.frames if f.mode == "error"]
    assert cur(rt).mode == "step"


# ------------------------------------------------------------------ chooser
def build_cards(n):
    out = []
    names = ["Assemble a shelf", "Build a bird feeder", "Change a bike tire", "Descale a kettle", "Light an LED on a breadboard"]
    for i in range(n):
        out.append(make_card(2, card_id=f"task_{i}", title=names[i], aliases=[names[i].split()[-1].lower()]))
    return out


def test_chooser_two_cards_swipe_press(tmp_path):
    cards = build_cards(2)
    rt = boot(cards, tmp_path)
    f = start_build(rt)
    assert f.mode == "menu" and f.menu.prompt == "PICK A TASK"
    assert f.menu.options == ["ASSEMBLE A SHELF", "BUILD A BIRD FEEDER"] and f.menu.selected == 0
    assert rt.handle_input(gi("swipe_down")).menu.selected == 1
    assert rt.handle_input(gi("swipe_down")).menu.selected == 1  # clamped
    assert rt.handle_input(gi("swipe_up")).menu.selected == 0
    rt.handle_input(gi("swipe_down"))
    f = rt.handle_input(gi("press"))
    assert f.mode == "intervene" and f.cue.line1.startswith("BUILD: BUILD A BIRD")
    assert rt.session().card_id == "task_1" and rt.playbook.card.card_id == "task_1"


def test_chooser_three_cards(tmp_path):
    rt = boot(build_cards(3), tmp_path)
    f = start_build(rt)
    assert f.menu.options == ["ASSEMBLE A SHELF", "BUILD A BIRD FEEDER", "CHANGE A BIKE TIRE"] and all(len(o) <= 24 for o in f.menu.options)
    swipes(rt, 2)
    rt.handle_input(gi("press"))
    assert rt.session().card_id == "task_2"


def test_chooser_more_than_three_shows_more_on_phone_hint_only(tmp_path):
    rt = boot(build_cards(5), tmp_path)
    f = start_build(rt)
    # the Menu contract allows at most 4 options: three cards + MORE ON PHONE
    assert f.menu.options == ["ASSEMBLE A SHELF", "BUILD A BIRD FEEDER", "CHANGE A BIKE TIRE", "MORE ON PHONE"]
    swipes(rt, 3)
    f = rt.handle_input(gi("press"))
    assert f.mode == "uncertain" and (f.cue.line1, f.cue.line2) == ("USE THE PHONE", "TYPE YOUR TASK")
    assert rt.session().phase == "menu" and rt.playbook is None
    settle(rt)
    assert cur(rt).mode == "menu" and cur(rt).menu.selected == 3


def test_chooser_four_cards_shows_all_four_no_more(tmp_path):
    rt = boot(build_cards(4), tmp_path)
    f = start_build(rt)
    assert len(f.menu.options) == 4 and "MORE ON PHONE" not in f.menu.options
    swipes(rt, 3)
    rt.handle_input(gi("press"))
    assert rt.session().card_id == "task_3"


def test_double_press_is_never_sent_so_chooser_has_no_special_case(tmp_path):
    rt = boot(build_cards(2), tmp_path)
    start_build(rt)
    n = len(rt.hud.frames)
    rt.handle_input(gi("hold_start"))  # holds are the voice lane's; the chooser ignores them
    assert rt.hud.current.mode == "menu" and len(rt.hud.frames) == n


def test_phone_text_tie_opens_chooser_on_the_glasses(tmp_path):
    a = make_card(2, card_id="a", title="Fix the bike chain", goal_mode="fix", aliases=["bike"])
    b = make_card(2, card_id="b", title="Fix the bike brakes", goal_mode="fix", aliases=["bike"])
    rt = boot([a, b], tmp_path)
    to_menu(rt)
    res = rt.resolve_goal(GoalRequest(session_id=rt.session().id, mode="fix", via="phone_text", text="my bike is broken"))
    assert res.status == "ambiguous" and set(res.alternatives) == {"Fix the bike chain", "Fix the bike brakes"}
    assert cur(rt).mode == "menu" and cur(rt).menu.options == ["FIX THE BIKE BRAKES", "FIX THE BIKE CHAIN"]
    rt.handle_input(gi("press"))
    assert rt.session().card_id == "b" and rt.playbook.card.card_id == "b"


# ------------------------------------------------------------------ free-text scoring
def req(text, mode="build"):
    return GoalRequest(session_id="s", mode=mode, via="phone_text", text=text)


def test_free_text_unique_ambiguous_none(led):
    other = make_card(2, card_id="o", title="Set up a breadboard power rail", aliases=["power rail", "breadboard"])
    cards = [led, other]
    r = goal.resolve(req("I want to light an LED"), cards)
    assert r.status == "supported" and r.card_id == "led_breadboard"
    r = goal.resolve(req("blinking my led"), cards)  # light stemming: blinking ~ blink
    assert r.status == "supported" and r.card_id == "led_breadboard"
    r = goal.resolve(req("how do I use the breadboard"), cards)  # both cards list the alias 'breadboard'
    assert r.status == "ambiguous" and len(r.alternatives) == 2
    r = goal.resolve(req("plant a tree"), cards)
    assert r.status == "unsupported" and r.card_id is None and r.research_queued is False
    assert r.cue.line1 == "NOT SUPPORTED YET" and "Light an LED" in r.detail  # lists supported tasks


def test_alias_is_a_word_match_not_a_substring(led):
    assert goal.resolve(req("the controlled installed system"), [led]).status == "unsupported"  # 'led' inside other words


def test_free_text_respects_goal_mode(led, lens):
    assert goal.resolve(req("light an led", "fix"), [led, lens]).status == "unsupported"
    assert goal.resolve(req("camera is black", "fix"), [led, lens]).status == "supported"


# ------------------------------------------------------------------ research queue
def test_unsupported_text_is_saved_and_cue_says_queued_only_when_saved(led, tmp_path):
    root = tmp_path / "root"
    rt = boot([led], tmp_path, asset_root=root)
    to_menu(rt)
    sid = rt.session().id
    res = rt.resolve_goal(GoalRequest(session_id=sid, mode="build", via="phone_text", text="assemble a telescope"))
    assert res.status == "unsupported" and res.research_queued is True
    assert (res.cue.line1, res.cue.line2) == ("NOT SUPPORTED YET", "QUEUED FOR RESEARCH")
    assert (cur(rt).cue.line1, cur(rt).cue.line2) == ("NOT SUPPORTED YET", "QUEUED FOR RESEARCH")
    files = sorted((root / "knowledge" / "requests").glob("*.json"))
    assert len(files) == 1
    d = json.loads(files[0].read_text())
    assert d["text"] == "assemble a telescope" and d["session_id"] == sid and d["mode"] == "build"
    # rate limited second request (different text, < 2 s): honest, not queued, no file
    res2 = rt.resolve_goal(GoalRequest(session_id=sid, mode="build", via="phone_text", text="assemble a boat"))
    assert res2.research_queued is False and res2.cue.line2.startswith("TRY: ")
    assert len(list((root / "knowledge" / "requests").glob("*.json"))) == 1
    # a menu confirm (no text) never saves anything
    rt.clock.advance(3000)
    res3 = rt.resolve_goal(GoalRequest(session_id=sid, mode="fix", via="g2_menu", text=None))
    assert res3.research_queued is False


def mk_client(rt):
    app = create_app(rt, tick_interval=None, sim_interval=None, web_dir=rt.asset_root / "no-web")
    return TestClient(app)


def test_research_request_endpoint(led, tmp_path):
    root = tmp_path / "root"
    rt = boot([led], tmp_path, asset_root=root)
    with mk_client(rt) as c:
        body = {"session_id": "s-1", "mode": "build", "text": "  tune a guitar  "}
        r = c.post("/research/request", json=body)
        assert r.status_code == 200
        j = r.json()
        assert j["status"] == "unsupported" and j["research_queued"] is True
        assert j["detail"] == "saved for async research; not available now"
        assert j["cue"]["line2"] == "QUEUED FOR RESEARCH"
        files = list((root / "knowledge" / "requests").glob("*.json"))
        assert len(files) == 1 and json.loads(files[0].read_text())["text"] == "tune a guitar"
        assert c.post("/research/request", json={**body, "text": "other"}).status_code == 429  # 1 per 2 s per session
        rt.clock.advance(2100)
        assert c.post("/research/request", json={**body, "text": "other"}).status_code == 200
        assert c.post("/research/request", json={**body, "mode": "nope"}).status_code == 422
        assert c.post("/research/request", json={"session_id": "s-1", "mode": "fix", "text": ""}).status_code == 422
        assert c.post("/research/request", json={"session_id": "s-1", "mode": "fix", "text": "x", "extra": 1}).status_code == 422
        assert len(list((root / "knowledge" / "requests").glob("*.json"))) == 2


# ------------------------------------------------------------------ /ask
def ask_rig(tmp_path):
    card = make_card(4, card_id="asky", title="Ask me", aliases=["ask"], measured={3: verify_led(0)})
    rt = boot([card], tmp_path)
    start_build(rt)
    settle(rt)
    return rt


def test_ask_requires_an_active_playbook(lens, tmp_path):
    rt = boot([lens], tmp_path)
    with mk_client(rt) as c:
        assert c.post("/ask", json={"session_id": "x", "text": "where"}).status_code == 409


def test_ask_intents_answer_from_card_text_only(tmp_path):
    rt = ask_rig(tmp_path)
    confirm(rt)  # now on step s1 (has faq + troubleshoot + where + why)
    with mk_client(rt) as c:
        def ask(t):
            r = c.post("/ask", json={"session_id": rt.session().id, "text": t})
            assert r.status_code == 200, r.text
            return r.json()

        j = ask("where is it")
        assert j["intent"] == "where" and j["answer"] == {"line1": "WHERE 1 IS", "line2": "ON THE LEFT"}
        assert j["text"] == "WHERE 1 IS ON THE LEFT"
        f = cur(rt)
        assert f.mode == "ask" and f.cue.line1 == "WHERE 1 IS" and f.ttl_ms == 4000
        settle(rt, 4100)
        assert cur(rt).mode == "step" and cur(rt).step.step_id == "s1"
        j = ask("why do I do this")
        assert j["intent"] == "why" and j["answer"]["line1"] == "WHY 1: SAFETY"
        settle(rt, 4100)
        j = ask("which part is thing 1")
        assert j["intent"] == "faq" and j["answer"]["line1"] == "PART 1 IS BLUE"
        settle(rt, 4100)
        j = ask("it didn't work, what now")
        assert j["intent"] == "troubleshoot" and j["answer"]["line1"] == "CHECK PART 1" and "slips" in j["text"]
        ev = rt.state().events
        assert any(e.label == "INFERRED" and "troubleshoot" in e.text for e in ev)
        assert any(e.label == "AUTHORED DEMO METADATA" and "CHECK PART 1" in e.text and "slips" in e.text for e in ev)  # provenance = the card's
        settle(rt, 4100)
        j = ask("which step am I on")
        assert j["intent"] == "status" and j["answer"]["line1"] == "STEP 2 OF 4"
        settle(rt, 4100)
        j = ask("flibbertigibbet")
        assert j["intent"] == "unknown" and j["answer"] is None and j["text"] == "NOT IN MY PLAYBOOK SEE PHONE"
        assert j["label"] == "DETERMINISTIC" and j["step_id"] == "s1" and j["card_id"] == rt.active_card.card_id
        assert cur(rt).mode == "ask"
        settle(rt, 4100)
        # a step without that content never invents it
        confirm(rt)  # s2: no troubleshoot entry of its own; the confirmed step s1's check is the only candidate
        j = ask("what if it didn't work")
        assert j["answer"]["line1"] == "CHECK PART 1" and "which you already confirmed" in j["text"]
        settle(rt, 4100)
        j = ask("what if it didn't work")  # already suggested: no repeat, no invention
        assert j["answer"]["line1"] == "NO MORE CHECKS HERE" and j["label"] == "DETERMINISTIC"


def test_ask_navigation_matches_gestures_and_never_verifies(tmp_path):
    rt = ask_rig(tmp_path)
    with mk_client(rt) as c:
        j = c.post("/ask", json={"session_id": "", "text": "next"}).json()
        assert j["intent"] == "next" and rt.state().playbook.step_index == 1  # typing "next" on the phone = the wearer's confirm
        assert rt.state().playbook.confirmed == ["s0"]
        j = c.post("/ask", json={"session_id": "", "text": "go back"}).json()
        assert j["intent"] == "back" and rt.state().playbook.step_index == 0
        c.post("/ask", json={"session_id": "", "text": "next"})
        c.post("/ask", json={"session_id": "", "text": "next"})
        c.post("/ask", json={"session_id": "", "text": "next"})
        assert rt.state().playbook.step_index == 3 and rt.state().playbook.step_id == "s3"  # s3 is measured
        j = c.post("/ask", json={"session_id": "", "text": "next"}).json()
        assert j["answer"]["line1"] == "NO PI DATA" and rt.state().playbook.step_index == 3 and rt.state().playbook.verified == []


def test_ask_show_picture_opens_the_guide(tmp_path):
    card = make_card(2, card_id="pic", title="Pic", aliases=["pic"], guides=[guide_dict("gd", 2)], guide_steps={0: "gd"})
    root = tmp_path / "root"
    write_pngs(root)
    rt = boot([card], tmp_path, asset_root=root)
    start_build(rt)
    settle(rt)
    with mk_client(rt) as c:
        c.post("/ask", json={"session_id": "", "text": "show me the picture"})
        assert cur(rt).mode == "visual" and cur(rt).image.view == "where"


def test_voice_transcript_during_a_playbook_is_answered_from_the_card(tmp_path):
    from ghostbuild_core.voice import VoiceService

    rt = ask_rig(tmp_path)
    confirm(rt)
    svc = VoiceService(rt, lambda: None)
    svc.on_hold("hold_start")
    svc.on_transcript("where does it go", "fake", "test")
    f = cur(rt)
    assert f.mode == "ask" and f.cue.line1 == "WHERE 1 IS"


def test_card_endpoint_and_state_endpoint_follow_the_active_playbook(led, tmp_path):
    rt = boot([led], tmp_path)
    start_build(rt)
    settle(rt)
    with mk_client(rt) as c:
        assert c.get("/card").json()["card_id"] == "led_breadboard"
        st = c.get("/state").json()
        assert st["engine"] == "PLAYBOOK" and st["playbook"]["step_id"] == "parts" and st["hud"]["mode"] == "step"
