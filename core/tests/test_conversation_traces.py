"""Scripted conversation traces (cases C-H of the adaptive handoff) through the real Runtime and Assistant.

A FakeBrain plays the model, so these prove ORCHESTRATION only: which decision the policy takes, what is persisted,
what is blocked, and that nothing leaks between tasks. They say nothing about live-model question quality.
"""

from __future__ import annotations

import time

from ghostbuild_core.assistant.adaptive import TaskFact
from ghostbuild_core.assistant.brain import BrainError, FakeBrain
from ghostbuild_core.assistant.schemas import IntakeReply

from test_assistant import ask_goal, boot, settle, step_reply, to_step


def task_of(rt):
    return rt.assistant.tasks[rt.session().id]


def decisions(rt):
    return [d["decision"] for d in task_of(rt).decisions]


def user_said(brain, call=-1):
    return " ".join(m["content"] for m in brain.calls[call][2] if m["role"] == "user")


# ------------------------------------------------------------------ C: which display -> observation -> research only after it
def test_c_screen_issue_discriminates_the_display_then_asks_for_the_observation_before_research(tmp_path):
    brain = FakeBrain(intake=[
        IntakeReply(action="ask", say="Is it the built-in screen, an external display, or both?", question_key="which display",
                    critical_unknowns=["which display is affected"], decision="ASK_QUESTION", quick_replies=["Built-in", "External", "Both"]),
        IntakeReply(action="ask", say="What does the external display show: no signal, flicker, or wrong colours?", question_key="external symptom",
                    critical_unknowns=["what the external display shows"],
                    facts=[TaskFact(field="symptom", value="only the external display", origin="user", quote="only the external monitor")]),
        IntakeReply(action="start", say="Thanks. I will look for a sourced procedure for that.", goal="Mac external display shows no signal; built-in works",
                    context_sufficient=True,
                    facts=[TaskFact(field="observation", value="external shows no signal", origin="user", quote="it says no signal")]),
    ])
    rt = boot(tmp_path, brain)
    ask_goal(rt, "my mac screen is acting weird", via="phone_text")
    settle(rt)
    assert rt.playbook is None and task_of(rt).pending_question.startswith("Is it the built-in")
    ask_goal(rt, "only the external monitor, the laptop screen is fine", via="phone_text")
    settle(rt)
    assert rt.playbook is None and decisions(rt) == ["ASK_QUESTION", "ASK_QUESTION"]
    ask_goal(rt, "it says no signal", via="phone_text")
    settle(rt)
    assert decisions(rt)[-1] == "RESEARCH" and rt.playbook is None  # no ready card fits; no generic guide was started
    facts = {(f.field, f.origin) for f in task_of(rt).facts}
    assert ("symptom", "user") in facts and ("observation", "user") in facts
    assert "only the external monitor" in user_said(brain) and "my mac screen" in user_said(brain)  # earlier turns are history


# ------------------------------------------------------------------ D + F: "I don't know" gets identification help, not the same question
def test_d_f_unknown_tyre_type_gets_identification_help_then_the_answer_unlocks_the_procedure(tmp_path):
    q = dict(action="ask", say="Is it an inner tube or a tubeless tyre?", question_key="tyre setup", critical_unknowns=["inner tube or tubeless"])
    brain = FakeBrain(intake=[
        IntakeReply(**q),
        IntakeReply(**q, identification_help="Let the air out and look at the valve: if you can pull out a separate tube it is an inner tube."),
        IntakeReply(action="start", say="Inner tube. I will find the procedure.", goal="replace a bicycle inner tube", context_sufficient=True,
                    facts=[TaskFact(field="configuration", value="inner tube", origin="user", quote="there is a separate tube")]),
    ])
    rt = boot(tmp_path, brain)
    ask_goal(rt, "fix my bike tyre", via="phone_text")
    settle(rt)
    ask_goal(rt, "I don't know", via="phone_text")
    settle(rt)
    t = task_of(rt)
    assert decisions(rt) == ["ASK_QUESTION", "EXPLAIN"] and t.pending_question.startswith("Let the air out")  # a method, not a repeat
    assert t.asked.count("tyre setup") == 1 and rt.playbook is None
    ask_goal(rt, "ok there is a separate tube", via="phone_text")
    settle(rt)
    assert decisions(rt)[-1] == "RESEARCH" and any(f.origin == "user" and f.value == "inner tube" for f in task_of(rt).facts)


# ------------------------------------------------------------------ E: a correction revises the context and drops stale in-flight work
def test_e_correction_replaces_the_earlier_identity_and_rejects_the_answer_to_the_old_one(tmp_path):
    slow = IntakeReply(action="start", say="Road bike chain it is.", goal="replace a road bike chain", context_sufficient=True)
    brain = FakeBrain(intake=[
        IntakeReply(action="ask", say="How many gears at the back?", question_key="speeds", critical_unknowns=["drivetrain speed"],
                    facts=[TaskFact(field="product", value="road bike", origin="user", quote="road bike")]),
        lambda m: (time.sleep(0.3), slow)[1],  # answer to the OLD context, arrives after the correction
        IntakeReply(action="ask", say="Got it, a mountain bike. How many gears at the back?", question_key="speeds mtb",
                    critical_unknowns=["drivetrain speed"],
                    facts=[TaskFact(field="product", value="mountain bike", origin="user", quote="mountain bike")]),
    ])
    rt = boot(tmp_path, brain)
    ask_goal(rt, "replace the chain on my road bike", via="phone_text")
    settle(rt)
    rev = task_of(rt).revision
    ask_goal(rt, "11 speed", via="phone_text")  # in flight...
    ask_goal(rt, "actually it's a mountain bike, not a road bike", via="phone_text")  # ...corrected before it lands
    settle(rt)
    time.sleep(0.4)
    rt.tick()
    t = task_of(rt)
    assert t.revision == rev + 1 and rt.playbook is None and rt.live.active is None  # the stale "start" never ran
    assert [f.value for f in t.facts if f.field == "product"] == ["mountain bike"]
    assert "RESEARCH" not in decisions(rt) and t.pending_question.startswith("Got it, a mountain bike")


# ------------------------------------------------------------------ G: the assistant/audio failing leaves a complete text path
def test_g_assistant_failure_with_critical_unknowns_blocks_and_typed_text_continues(tmp_path):
    brain = FakeBrain(intake=[
        IntakeReply(action="ask", say="Which model is it?", question_key="model", critical_unknowns=["exact model"]),
        BrainError("APIConnectionError"),
        IntakeReply(action="ask", say="Thanks. Is the hinge loose or broken?", question_key="hinge state", critical_unknowns=["hinge state"]),
    ])
    rt = boot(tmp_path, brain)
    ask_goal(rt, "tighten my cabinet hinge", via="voice")
    settle(rt)
    ask_goal(rt, "it's the blum one", via="voice")
    settle(rt)
    assert rt.playbook is None and decisions(rt)[-1] == "ESCALATE_OR_STOP"  # no guessing a procedure while the model is unknown
    msgs = rt.assistant.chat[rt.session().id]
    assert any(m.role == "system" and "need the missing product" in m.text for m in msgs)  # readable on the phone, no audio needed
    ask_goal(rt, "it's a Blum clip top hinge", via="phone_text")  # typing works the same as speaking
    settle(rt)
    assert task_of(rt).pending_question.startswith("Thanks. Is the hinge")


def test_g_full_step_answer_is_kept_as_text_without_truncation(tmp_path):
    long = " ".join(f"word{i}" for i in range(120))
    rt = boot(tmp_path, FakeBrain(step=[step_reply(answer=long, add_note=False)]))
    to_step(rt)
    rt.ask("how do I identify the three servo wires")
    settle(rt)
    sid = rt.session().id
    assert any(m.role == "assistant" and m.text == long for m in rt.assistant.chat[sid])
    assert rt.playbook.answer_data["text"].startswith(long)  # the glasses pages carry all of it


# ------------------------------------------------------------------ H: a new goal mid-interview starts a clean task
def test_h_new_goal_during_questions_starts_a_new_task_without_old_context(tmp_path):
    brain = FakeBrain(intake=[
        IntakeReply(action="ask", say="Inner tube or tubeless?", question_key="tyre setup", critical_unknowns=["tyre setup"],
                    facts=[TaskFact(field="product", value="bike", origin="user", quote="bike tyre")]),
        IntakeReply(action="ask", say="What size bookshelf, and do you have a drill?", question_key="shelf size"),
    ])
    rt = boot(tmp_path, brain)
    ask_goal(rt, "fix my bike tyre", via="phone_text")
    settle(rt)
    old = task_of(rt)
    ask_goal(rt, "actually I want to build a bookshelf instead", via="phone_text")
    settle(rt)
    new = task_of(rt)
    assert new.id != old.id and new.goal.endswith("bookshelf instead") and not new.facts and not new.critical_unknowns
    sent = user_said(brain)
    assert "bookshelf" in sent and "bike" not in sent  # no old-task history reached the model
    assert new.pending_question.startswith("What size bookshelf")


def test_h_mid_step_questions_starting_with_a_verb_never_switch_tasks(tmp_path):
    rt = boot(tmp_path, FakeBrain(step=[step_reply(add_note=False)]))
    to_step(rt)
    card = rt.playbook.card.card_id
    rt.ask("make sure the servo wires are the right way round?")
    settle(rt)
    assert rt.playbook is not None and rt.playbook.card.card_id == card and rt.session().phase == "task"
    assert rt.playbook.confirmed == ["s0"]


def test_restart_during_an_interview_asks_the_open_question_again_and_keeps_the_task(tmp_path):
    from contracts.models import G2Hello

    brain = FakeBrain(intake=[IntakeReply(action="ask", say="Is it an inner tube or tubeless?", cue1="TUBE OR TUBELESS?", cue2="",
                                          question_key="tyre setup", critical_unknowns=["tyre setup"])])
    rt = boot(tmp_path, brain)
    ask_goal(rt, "fix my bike tyre", via="phone_text")
    settle(rt)
    sid, task_id = rt.session().id, task_of(rt).id
    rt.close()
    from ghostbuild_core.clock import ManualClock
    from ghostbuild_core.runtime import Runtime
    from test_assistant import card_with_content

    rt2 = Runtime([card_with_content()], clock=ManualClock(), log_dir=tmp_path / "l", asset_root=tmp_path / "root", brain=FakeBrain())
    rt2.hello(G2Hello(client_id="g2-1", session_id=sid))
    assert rt2.session().id == sid and rt2.assistant.tasks[sid].id == task_id
    assert rt2.hud.current.cue.line1.startswith("IS IT AN INNER TUBE")
    assert rt2.assistant.intakes[sid].active


def _real_runtime(tmp_path, brain):
    from pathlib import Path

    from contracts.models import G2Hello
    from ghostbuild_core.cards import load_cards
    from ghostbuild_core.clock import ManualClock
    from ghostbuild_core.runtime import Runtime

    repo = Path(__file__).resolve().parents[2]
    clock = ManualClock()
    rt = Runtime(load_cards(repo / "knowledge" / "cards"), clock=clock, log_dir=tmp_path / "l", asset_root=repo, brain=brain)
    rt.clock = clock
    rt.hello(G2Hello(client_id="g2-1", session_id=None))
    clock.advance(2600)
    rt.tick()
    return rt


def test_c_interview_answer_selects_the_branch_of_the_sourced_mac_guide_without_asking_again(tmp_path):
    import pytest

    rt0 = None
    brain = FakeBrain(intake=[
        IntakeReply(action="ask", say="Is it the built-in screen, an external monitor, or both?", question_key="which display",
                    critical_unknowns=["which display"]),
        IntakeReply(action="start", say="Okay, I have enough. Here's what I'd check first.", goal="Mac external display looks green",
                    library_id="mac_display_colors", context_sufficient=True),
    ])
    rt = _real_runtime(tmp_path, brain)
    if rt.card_by_id("mac_display_colors") is None:
        pytest.skip("compiled Mac guide not present")
    ask_goal(rt, "My MacBook screen suddenly turned green", via="phone_text")
    settle(rt)
    ask_goal(rt, "only the external monitor, the laptop screen looks fine", via="phone_text")
    settle(rt)
    pb = rt.playbook
    assert pb is not None and pb.card.card_id == "mac_display_colors"
    assert pb.step.id != pb.card.steps[0].id and pb.observations and "external" in pb.observations[0]["text"].lower()
    assert any(e.label == "HUMAN CONFIRMED" and "earlier answer" in e.text for e in pb.events)  # recorded as their word
    assert not pb.verified


def test_d_bike_guide_tubeless_answer_stops_with_the_sources_reason(tmp_path):
    import pytest

    rt = _real_runtime(tmp_path, None)
    card = rt.card_by_id("bike_flat_tire")
    if card is None:
        pytest.skip("compiled bike guide not present")
    rt.sessions.start_card(rt.session().id, card)
    rt.tick()
    pb = rt.playbook
    assert pb.step.kind == "question"
    res = rt.ask("it's tubeless")
    assert res.intent == "choice" and pb.step.kind == "stop"
