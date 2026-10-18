"""Checkpoint coverage: answer reading never commits a physical action."""

from ghostbuild_core.assistant.adaptive import TaskFact, TaskProfile, decide
from ghostbuild_core.assistant.brain import FakeBrain
from ghostbuild_core.assistant.schemas import IntakeReply
from ghostbuild_core.clock import ManualClock
from ghostbuild_core.playbook import PlaybookEngine
from ghostbuild_core.presentation import instruction
from ghostbuild_core.runtime import Runtime
from pbhelpers import Rig, make_card

from contracts.models import Cue, G2Hello, G2Input, GoalRequest


def test_full_answer_pages_persist_until_explicit_return_and_never_confirm():
    rig = Rig(make_card(6))
    rig.pb.ask("show me step 3")
    text = " ".join("word" + str(i) for i in range(180))
    rig.pb.show_answer(
        text, cue=Cue(line1="READ THE FULL ANSWER", line2="PRESS TO RETURN")
    )
    chunks = []
    count = rig.cur.answer.count
    for _ in range(count):
        chunks.append(rig.cur.answer.text)
        rig.send("swipe_down")
    assert " ".join(" ".join(chunks).split()) == text.upper()
    rig.wait(60_000)
    assert rig.cur.mode == "ask" and rig.cur.answer.index == count - 1
    assert rig.pb.index == 2 and not rig.pb.confirmed and not rig.pb.verified
    rig.send("press")
    assert rig.cur.mode == "step" and rig.pb.index == 2 and rig.pb.answer_data is None
    assert not rig.pb.confirmed


def test_answer_restore_and_voice_return_keep_the_original_step():
    rig = Rig(make_card(6))
    rig.pb.ask("show me step 3")
    rig.pb.show_answer("A detailed answer. " * 40, cue=Cue(line1="ANSWER", line2=""))
    rig.send("swipe_down")
    progress = rig.pb.progress()
    restored = PlaybookEngine(rig.pb.card, rig.clock, progress=progress)
    assert restored.hud.current.answer.index == 1
    restored.ask("take me back to my step")
    assert (
        restored.answer_data is None and restored.index == 2 and not restored.confirmed
    )


def test_plain_instruction_is_card_data_and_preserves_exact_reference():
    card = make_card(1)
    step = card.steps[0]
    old = step.cue
    assert instruction(step) == old
    step.instruction = Cue(line1="FIT THE ROUND LOCKS", line2="TURN A QUARTER TURN")
    assert instruction(step).line1 == "FIT THE ROUND LOCKS" and step.cue == old
    rig = Rig(card)
    assert rig.cur.cue.line1 == "FIT THE ROUND LOCKS"


def test_user_fact_requires_an_actual_accepted_quote():
    task = TaskProfile(goal="repair a display")
    task.observe("The external screen is green but the built-in display works.")
    task.merge(
        [
            TaskFact(
                field="symptom",
                value="external green",
                origin="user",
                quote="external screen is green",
            ),
            TaskFact(
                field="model",
                value="Model invented",
                origin="user",
                quote="unspoken model",
            ),
        ]
    )
    assert task.facts[0].origin == "user" and task.facts[1].origin == "inferred"
    task.observe("Actually, it's a different model.")
    assert task.revision == 1 and not any(f.field == "model" for f in task.facts)


def test_critical_unknowns_win_over_model_start_and_question_count():
    task = TaskProfile(
        goal="repair an unidentified object", critical_unknowns=["Exact model"]
    )
    task.asked = ["first", "second", "third", "fourth"]
    reply = IntakeReply(
        action="start", say="Ready", context_sufficient=True, question_key="model"
    )
    assert decide(reply, task, ready_exact=False) == "ASK_QUESTION"
    task.critical_unknowns = []
    assert decide(reply, task, ready_exact=False) == "RESEARCH"


def test_unknown_model_can_be_clarified_after_more_than_three_useful_questions(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("GB_LIVE_RESEARCH", "0")
    replies = [
        IntakeReply(
            action="ask",
            say=f"Check prerequisite {i}?",
            question_key=f"prerequisite{i}",
            critical_unknowns=[f"requirement{i}"],
        )
        for i in range(5)
    ]
    rt = Runtime(
        [make_card()],
        clock=ManualClock(),
        log_dir=tmp_path,
        brain=FakeBrain(intake=replies),
    )
    rt.hello(G2Hello(client_id="adaptive-test"))
    rt.clock.advance(2600)
    rt.tick()
    import time

    for i in range(5):
        rt.resolve_goal(
            GoalRequest(
                session_id=rt.session().id,
                mode="build",
                via="phone_text",
                text="repair a new model" if i == 0 else f"observation {i}",
            )
        )
        for _ in range(100):
            rt.tick()
            if not rt.assistant.pending:
                break
            time.sleep(0.001)
    assert rt.assistant.intakes[rt.session().id].asked == 5
    assert rt.playbook is None and rt.live.started == 0
    assert rt.assistant.tasks[rt.session().id].critical_unknowns == ["requirement4"]
    rt.close()


def test_an_answer_left_on_a_measured_step_never_traps_gestures_after_evidence_moves_on():
    from pbhelpers import verify_led

    rig = Rig(make_card(3, measured={0: verify_led(300)}))
    rig.pb.show_answer("Why the light matters. " * 30, cue=Cue(line1="WHY", line2=""))
    assert rig.cur.mode == "ask" and rig.cur.answer.count > 1
    rig.send("swipe_down")  # reading: page 2, the measured step is untouched
    assert rig.pb.index == 0 and not rig.pb.verified
    rig.feed(600, led=True)  # real evidence completes step 1
    assert rig.pb.verified == ["s0"] and rig.pb.index == 1 and rig.pb.answer_data is None
    rig.wait(4000)
    rig.send("swipe_down")  # a normal manual confirm of step 2, not an answer page turn
    assert rig.pb.confirmed == ["s1"] and rig.pb.index == 2


def test_a_stale_answer_from_another_step_is_dropped_on_the_next_gesture():
    rig = Rig(make_card(4))
    rig.pb.show_answer("Answer for step one.", cue=Cue(line1="ANSWER", line2=""))
    rig.pb.answer_data["step_id"] = "elsewhere"  # e.g. restored from an older progress file
    rig.wait(1600)
    rig.send("swipe_down")
    assert rig.pb.answer_data is None and rig.pb.confirmed == ["s0"]


def test_press_during_thinking_returns_to_the_step_and_keeps_the_late_answer_off_the_glasses(tmp_path):
    from test_assistant import boot, card_with_content, settle, step_reply, to_step

    brain = FakeBrain(step=[step_reply(), step_reply(answer="Second answer.")], delay_s=0.2)
    rt = boot(tmp_path, brain=brain)
    to_step(rt)
    res = rt.ask("how do I identify the three servo wires")
    assert res.pending and rt.hud.current.cue.line1 == "THINKING"
    view_before = rt.playbook.view_idx
    rt.handle_input(G2Input(gesture="press", seq_seen=rt.hud.current.seq))
    assert rt.hud.current.mode == "step" and rt.playbook.view_idx == view_before  # no picture cycling
    settle(rt)
    assert rt.playbook.answer_data is None and rt.hud.current.mode == "step"
    sid = rt.session().id
    assert any(m.role == "assistant" and "signal wire" in m.text for m in rt.assistant.chat[sid])  # still on the phone
    rt.ask("how do I identify the three servo wires please")  # a new question shows its answer again
    settle(rt)
    assert rt.playbook.answer_data is not None and rt.hud.current.mode == "ask"
    assert rt.playbook.confirmed == ["s0"]


def _persist_task_session(log_dir, card_id):
    import json

    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "sessions.json").write_text(json.dumps({
        "active": "s-old", "progress": {"s-old": {"card_id": card_id, "step_index": 1, "confirmed": ["s0"], "verified": [], "done": False}},
        "sessions": {"s-old": {"id": "s-old", "phase": "task", "goal": "build", "card_id": card_id, "welcome_shown": True}}}))


def test_restart_with_a_missing_card_returns_to_the_menu_not_another_engine(tmp_path):
    _persist_task_session(tmp_path / "l", "gone_card")
    rt = Runtime([make_card(3)], clock=ManualClock(), log_dir=tmp_path / "l", asset_root=tmp_path / "root", brain=False)
    assert rt.sessions.active.phase == "menu" and rt.playbook is None


def test_restart_reloads_the_researched_draft_a_session_was_following(tmp_path):
    import json

    draft = make_card(4, card_id="researched_thing", title="Researched thing")
    d = tmp_path / "root" / "knowledge" / "drafts" / "researched_thing-20261018T000000"
    d.mkdir(parents=True)
    (d / "envelope.json").write_text(json.dumps({"card": draft.model_dump(mode="json")}))
    _persist_task_session(tmp_path / "l", "researched_thing")
    rt = Runtime([make_card(3)], clock=ManualClock(), log_dir=tmp_path / "l", asset_root=tmp_path / "root", brain=False)
    assert rt.sessions.active.phase == "task" and rt.playbook.card.card_id == "researched_thing"
    assert rt.playbook.index == 1 and rt.playbook.confirmed == ["s0"]  # progress kept
    assert "researched_thing" in rt.live.cards  # still labelled AI-researched, unreviewed


def test_the_model_is_given_flat_all_required_wire_schemas_and_replies_convert():
    """The real API rejected the nested reply models ('Schema is too complex'); the wire shapes must stay flat."""
    from types import SimpleNamespace

    from ghostbuild_core.assistant.brain import AnthropicBrain
    from ghostbuild_core.assistant.schemas import IntakeWire, StepWire

    for wire in (IntakeWire, StepWire):
        schema = wire.model_json_schema()
        assert set(schema["required"]) == set(schema["properties"])  # no optional fields
        assert "anyOf" not in str(schema) and "minimum" not in str(schema)
    sent = {}

    class Client:
        class messages:
            @staticmethod
            def parse(**kw):
                sent.update(kw)
                out = kw["output_format"](action="ask", decision="ASK_QUESTION", say="Tube or tubeless?", cue1="TUBE OR TUBELESS?", cue2="",
                                          quick_replies=["Tube"], goal="", library_id="", context_sufficient=False,
                                          facts=[{"field": "product", "value": "bike", "origin": "user", "quote": "my bike"}],
                                          critical_unknowns=["tyre setup"], question_key="tyre setup", question_reason="changes the procedure",
                                          identification_help="", branch="", experience="first_time", profile_facts=["has a pump"])
                return SimpleNamespace(stop_reason="end_turn", parsed_output=out)

    brain = AnthropicBrain(client=Client())
    brain.fast = False
    reply = brain.intake("sys", [{"role": "user", "content": "my bike"}])
    assert sent["output_format"] is IntakeWire and sent["max_tokens"] >= 1600
    assert isinstance(reply, IntakeReply) and reply.critical_unknowns == ["tyre setup"]
    assert reply.profile.experience == "first_time" and reply.profile.facts == ["has a pump"] and reply.facts[0].origin == "user"


def test_answer_pages_flag_off_restores_the_short_timed_cue(monkeypatch):
    monkeypatch.setenv("GB_ANSWER_PAGES", "0")
    rig = Rig(make_card(3))
    rig.pb.show_answer("A long answer. " * 30, cue=Cue(line1="SHORT CUE", line2=""))
    assert rig.cur.mode == "ask" and rig.cur.answer is None and rig.cur.ttl_ms == 4000
    rig.wait(4100)
    assert rig.cur.mode == "step"


def test_answer_pages_spell_out_units_instead_of_dropping_them():
    from ghostbuild_core.answer import pages

    text = " ".join(pages("Use a 220 Ω resistor at 5 V — about 20 mA; keep it under 60 °C ±2."))
    assert "220 OHM" in text and "60 DEG C" in text and "+/- 2" in text and "ABOUT 20 MA" not in text
    assert all(ch.isascii() for ch in text)
