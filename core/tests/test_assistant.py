"""Assistant: routing, step questions with notes, and the intake conversation. A scripted FakeBrain stands in for the model; nothing here
calls the network. Whether the real model answers well is measured separately (see docs/FINAL_SPRINT_STATUS.md)."""

from __future__ import annotations

import time

import pytest

from contracts.models import G2Hello, G2Input, GoalRequest
from ghostbuild_core.assistant import cuefmt, prompts
from ghostbuild_core.assistant.brain import BrainError, FakeBrain
from ghostbuild_core.assistant.router import route
from ghostbuild_core.assistant.schemas import IntakeReply, Message, Profile, StepReply
from ghostbuild_core.clock import ManualClock
from ghostbuild_core.runtime import Runtime

from pbhelpers import make_card, step_dict


def gi(g: str) -> G2Input:
    return G2Input(gesture=g, seq_seen=0)


def card_with_content():
    c = make_card(4, card_id="servo", title="Wire a servo", goal_mode="build", aliases=["servo"]).model_dump(mode="json")
    c["steps"][1]["title"] = "Connect the three wires"
    c["steps"][1]["detail"] = "A servo has three wires: signal, power and ground. Match them to the header."
    c["steps"][1]["warnings"] = ["Never connect power before the wires are placed."]
    return type(make_card(4)).model_validate(c)


def boot(tmp_path, brain=None, cards=None):
    clock = ManualClock()
    rt = Runtime(cards or [card_with_content()], clock=clock, log_dir=tmp_path / "l", asset_root=tmp_path / "root", brain=brain)
    rt.clock = clock
    rt.hello(G2Hello(client_id="g2-1", session_id=None))
    clock.advance(2600)
    rt.tick()
    return rt


def to_step(rt, n=1):
    rt.handle_input(gi("press"))  # failsafe list
    rt.handle_input(gi("press"))  # start
    for _ in range(n):
        rt.clock.advance(1600)
        rt.tick()
        rt.handle_input(gi("swipe_down"))
    assert rt.playbook is not None and rt.playbook.index == n


def settle(rt, timeout=5.0):
    end = time.time() + timeout
    while time.time() < end:
        rt.tick()
        if not rt.assistant.pending:
            return
        time.sleep(0.01)
    raise AssertionError("assistant did not answer")


def step_reply(**kw) -> StepReply:
    base = dict(answer="The signal wire is usually yellow or white; power is red; ground is brown or black.", cue1="SIGNAL: YELLOW/WHITE", cue2="RED + BROWN = POWER/GND",
                grounding="general", add_note=True, note_title="Servo wire colours")
    base.update(kw)
    return StepReply(**base)


# ------------------------------------------------------------------ pure pieces
def test_cuefmt_folds_to_the_safe_glyph_set_and_two_short_lines():
    c = cuefmt.fit_cue("Use a 220 Ω resistor — about 20 mA; don't use 5 V!")
    assert len(c.line1) <= 24 and len(c.line2) <= 26 and set((c.line1 + c.line2).replace(" ", "")) <= cuefmt.SAFE
    assert "OHM" in (c.line1 + c.line2)
    long = cuefmt.fit_cue("word " * 40)
    assert long.line2.endswith("...") and len(long.line2) <= 26 and len(long.line1) <= 24
    assert cuefmt.cue_from_reply("EXPERIENCE WITH THIS?", "FIRST TIME OR DONE IT?", "x").line2 == "FIRST TIME OR DONE IT?"
    assert cuefmt.cue_from_reply("THIS LINE IS FAR TOO LONG FOR THE GLASSES", "", "short fallback").line1 == "SHORT FALLBACK"  # brain cue rejected, text wrapped


def test_step_context_carries_the_step_notes_profile_and_safety_text():
    card = card_with_content()
    from ghostbuild_core.assistant.schemas import Note

    ctx = prompts.step_context(card, 1, confirmed=["s0"], tried=["CHECK PART 1"], notes=[Note(card_id="servo", step_id="s1", title="t", question="q?", answer="a.")],
                               profile=Profile(experience="first_time", facts=["Raspberry Pi 4"]))
    for needle in ("THE PERSON IS ON STEP 2 OF 4", "three wires", "WARNING: Never connect power", "CHECK PART 1", "Q: q? A: a.", "first-timer", "Raspberry Pi 4"):
        assert needle in ctx
    msgs = prompts.to_messages([Message(role="user", text="a", kind="step"), Message(role="assistant", text="b", kind="step"),
                                Message(role="user", text="intake-only", kind="intake")], "c", kind="step")
    assert [m["role"] for m in msgs] == ["user", "assistant", "user"] and "intake-only" not in str(msgs)


def test_router_keeps_commands_and_faq_deterministic_and_sends_real_questions_to_the_assistant(tmp_path):
    rt = boot(tmp_path)
    to_step(rt)
    pb = rt.playbook
    plain = ["where is that", "show me how", "why do I do this", "next", "what step am I on", "wait where exactly is that"]
    real = ["how do I identify the three servo wires", "which wire is ground", "can I use a different kind of header"]
    assert all(route(t, pb, assistant_available=True) == "deterministic" for t in plain)
    assert all(route(t, pb, assistant_available=True) == "assistant" for t in real)
    assert all(route(t, pb, assistant_available=False) == "deterministic" for t in real)  # no brain: exactly today's behaviour


# ------------------------------------------------------------------ step conversation
def test_a_real_question_gets_an_answer_a_cue_and_a_note_on_that_step(tmp_path):
    brain = FakeBrain(step=[step_reply()])
    rt = boot(tmp_path, brain)
    to_step(rt)
    res = rt.ask("how do I identify the three servo wires")
    assert res.pending and res.intent == "assistant" and res.cue.line1 == "THINKING"
    assert rt.hud.current.mode == "ask" and rt.hud.current.cue.line1 == "THINKING"  # immediate feedback on the glasses
    settle(rt)
    f = rt.hud.current
    assert f.mode == "ask" and f.cue.line1 == "SIGNAL: YELLOW/WHITE"
    st = rt.assistant.state()
    assert [m["role"] for m in st["messages"]] == ["user", "assistant"] and st["messages"][1]["grounding"] == "general" and st["messages"][1]["speak"] is True
    assert len(st["notes"]) == 1 and st["notes"][0]["step_id"] == "s1" and st["notes"][0]["title"] == "Servo wire colours"
    kind, system, messages = brain.calls[0]
    assert "THE PERSON IS ON STEP 2 OF 4" in system and "three wires" in system and messages[-1]["content"] == "how do I identify the three servo wires"
    assert rt.playbook.index == 1 and rt.playbook.confirmed == ["s0"]  # asking never moves or confirms anything
    assert any(e.label == "INFERRED" and "AI answer (general)" in e.text for e in rt.state().events)


def test_a_note_can_be_recalled_by_voice_without_calling_the_model_again(tmp_path):
    brain = FakeBrain(step=[step_reply()])
    rt = boot(tmp_path, brain)
    to_step(rt)
    rt.ask("how do I identify the three servo wires")
    settle(rt)
    rt.clock.advance(8000)
    rt.tick()
    res = rt.ask("remind me what you said about this step")
    assert res.intent == "notes" and res.answered and "SIGNAL" in res.cue.line1 + res.cue.line2 or "YELLOW" in res.text
    assert len(brain.calls) == 1  # recalled from the kept note


def test_a_follow_up_question_is_shown_and_the_conversation_continues_with_history(tmp_path):
    brain = FakeBrain(step=[step_reply(answer="Depends on the servo model.", cue1="WHICH SERVO MODEL?", cue2="", follow_up="Which servo do you have?",
                                       quick_replies=["SG90", "MG996R", "Not sure"], add_note=False),
                            step_reply(answer="SG90: brown ground, red power, orange signal.", cue1="ORANGE = SIGNAL", cue2="RED PWR, BROWN GND", add_note=True)])
    rt = boot(tmp_path, brain)
    to_step(rt)
    rt.ask("how do I identify the three servo wires")
    settle(rt)
    msgs = rt.assistant.state()["messages"]
    assert msgs[-1]["text"] == "Which servo do you have?" and msgs[-1]["quick_replies"] == ["SG90", "MG996R", "Not sure"]
    rt.clock.advance(6000)
    rt.tick()
    assert rt.hud.current.cue.line1 == "WHICH SERVO MODEL?" or rt.hud.current.cue.line1.startswith("WHICH SERVO")
    rt.ask("it is an SG90")  # specific ('SG90') -> assistant again, with the earlier turns as history
    settle(rt)
    prior = brain.calls[1][2]
    assert [m["role"] for m in prior] == ["user", "assistant", "user"] and "Which servo do you have?" in prior[1]["content"]


def test_when_the_model_fails_the_wearer_is_told_and_nothing_breaks(tmp_path):
    rt = boot(tmp_path, FakeBrain(step=[BrainError("TimeoutError")]))
    to_step(rt)
    rt.ask("how do I identify the three servo wires")
    settle(rt)
    assert rt.hud.current.cue.line1 == "CAN'T ANSWER NOW" and rt.assistant.state()["messages"][-1]["role"] == "system"
    rt.clock.advance(5000)
    rt.tick()
    assert rt.hud.current.mode == "step" and rt.playbook.index == 1  # the guide is still right there


def test_without_a_brain_everything_behaves_exactly_as_before(tmp_path):
    rt = boot(tmp_path, None)
    to_step(rt)
    res = rt.ask("how do I identify the three servo wires")
    assert res.intent in ("how", "unknown") and not res.pending and not rt.assistant.enabled
    assert rt.assistant.state()["enabled"] is False


# ------------------------------------------------------------------ intake conversation
def ask_goal(rt, text, via="voice", mode="build"):
    return rt.resolve_goal(GoalRequest(session_id=rt.session().id, mode=mode, via=via, text=text))


def test_intake_asks_then_starts_a_ready_guide_and_remembers_the_person(tmp_path):
    brain = FakeBrain(intake=[
        IntakeReply(action="ask", say="Have you wired a servo before, or is this your first time?", cue1="EXPERIENCE WITH THIS?", cue2="FIRST TIME OR DONE IT?", quick_replies=["First time", "Done it before"]),
        IntakeReply(action="start", say="Great, I will keep it simple.", goal="Wire a servo to a Raspberry Pi, first-timer", library_id="servo", profile=Profile(experience="first_time", facts=["Raspberry Pi 4"]))])
    rt = boot(tmp_path, brain)
    res = ask_goal(rt, "I want to wire a servo")
    assert res.conversing is True and res.cue.line1 == "THINKING" and rt.hud.current.cue.line1 == "THINKING"
    settle(rt)
    assert rt.hud.current.cue.line1 == "EXPERIENCE WITH THIS?" and rt.session().phase == "menu"  # the question stays on the glasses until answered
    state = rt.assistant.state()
    assert state["intake"] == {"active": True, "asked": 1, "max": 3} and state["messages"][-1]["quick_replies"] == ["First time", "Done it before"]
    ask_goal(rt, "first time, I have a Raspberry Pi 4")  # the answer (voice or tapped chip) continues the same conversation
    settle(rt)
    assert rt.session().phase == "task" and rt.playbook.card.card_id == "servo" and rt.hud.current.mode == "intervene"
    prof = rt.assistant.state()["profile"]
    assert prof["experience"] == "first_time" and "Raspberry Pi 4" in prof["facts"]
    assert rt.assistant.intakes[rt.session().id].active is False


def test_intake_never_asks_more_than_three_questions(tmp_path):
    ask = IntakeReply(action="ask", say="One more thing?", cue1="ONE MORE THING?", cue2="")
    brain = FakeBrain(intake=[ask, ask, ask, ask])  # a chatty model
    rt = boot(tmp_path, brain)
    ask_goal(rt, "tighten a loose cabinet hinge")
    for answer in ("a", "b", "c"):
        settle(rt)
        ask_goal(rt, answer)
    settle(rt)
    assert rt.assistant.intakes[rt.session().id].asked == 3 and rt.assistant.intakes[rt.session().id].active is False  # the 4th 'ask' became 'start'


def test_intake_can_decline_something_out_of_scope(tmp_path):
    brain = FakeBrain(intake=[IntakeReply(action="decline", say="I cannot help with mains wiring; please call an electrician.", cue1="CALL AN ELECTRICIAN", cue2="NOT FOR DIY")])
    rt = boot(tmp_path, brain)
    ask_goal(rt, "rewire my house outlet")
    settle(rt)
    assert rt.hud.current.cue.line1 == "CALL AN ELECTRICIAN" and rt.session().phase == "menu"
    assert rt.assistant.state()["intake"]["active"] is False


def test_intake_failure_falls_back_to_the_direct_path(tmp_path):
    rt = boot(tmp_path, FakeBrain(intake=[BrainError("RateLimitError")]))
    res = ask_goal(rt, "wire a servo", via="phone_text")
    assert res.conversing
    settle(rt)
    assert rt.session().phase == "task" and rt.playbook.card.card_id == "servo"  # the deterministic matcher still starts it


def test_swipe_up_leaves_the_conversation_and_drops_a_late_answer(tmp_path):
    brain = FakeBrain(intake=[IntakeReply(action="ask", say="Which servo?", cue1="WHICH SERVO?", cue2="")], delay_s=0.2)
    rt = boot(tmp_path, brain)
    ask_goal(rt, "wire a servo")
    rt.handle_input(gi("swipe_up"))  # leave while the model is still thinking
    settle(rt)
    time.sleep(0.3)
    rt.tick()
    assert rt.hud.current.cue.line1 == "WHAT DO YOU NEED?" and rt.assistant.state()["intake"]["active"] is False


def test_g2_menu_picks_bypass_the_assistant(tmp_path):
    rt = boot(tmp_path, FakeBrain())
    assert rt.assistant.wants_goal(GoalRequest(session_id=rt.session().id, mode="build", via="g2_menu", text=None)) is False
