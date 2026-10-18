"""Corrections replace reported facts without inventing physical completion."""

import pytest

from contracts.models import Card, G2Hello, G2Input, GoalRequest
from ghostbuild_core.clock import ManualClock
from ghostbuild_core.goal import candidates, model_conflict, model_tokens
from ghostbuild_core.playbook import PlaybookEngine
from ghostbuild_core.runtime import Runtime
from pbhelpers import Rig, make_card
from test_branching import graph_card


def question_card():
    data = graph_card().model_dump(mode="json")
    data["steps"][0]["choices"].append({
        "id": "both", "label": "BOTH DISPLAYS", "say": ["both", "all displays"],
        "next": "b1", "records": "Both displays are affected",
    })
    return Card.model_validate(data)


def runtime(tmp_path, monkeypatch, card=None):
    for flag in ("GB_ASSISTANT", "GB_CREAO", "GB_LIVE_RESEARCH", "GB_DISCOVERY_LIVE", "GB_VOICE"):
        monkeypatch.setenv(flag, "0")
    rt = Runtime([card or question_card()], clock=ManualClock(), log_dir=tmp_path,
                 asset_root=tmp_path, brain=None)
    rt.hello(G2Hello(client_id="correction-test"))
    rt.clock.advance(2600)
    rt.tick()
    rt.sessions.start_card(rt.session().id, rt.cards[0])
    rt.tick()
    rt.clock.advance(4500)
    rt.tick()
    return rt


@pytest.mark.parametrize("text", [
    "My screen is green, but my external monitor looks fine.",
    "Actually, the external monitor is not affected.",
    "The external monitor isn't green.",
    "My external monitor is working normally.",
])
def test_ruled_out_choice_is_never_selected(text):
    assert Rig(question_card()).pb.match_choice(text) is None


def test_positive_clause_survives_negative_clause():
    assert Rig(question_card()).pb.match_choice(
        "The laptop screen is green, but the external monitor looks fine"
    ) == "builtin"


@pytest.mark.parametrize("label", ["RIGHT", "WORKING NORMALLY", "NOT SURE"])
def test_explicit_choice_labels_remain_selectable(label):
    data = question_card().model_dump(mode="json")
    data["steps"][0]["choices"][0].update(label=label, say=[label.lower()])
    assert Rig(Card.model_validate(data)).pb.match_choice(label.lower()) == "builtin"


@pytest.mark.parametrize("text", ["It looks normal now", "The colors are fine now"])
def test_positive_outcome_sentences_remain_selectable(text):
    data = question_card().model_dump(mode="json")
    data["steps"][0]["choices"][0].update(label="LOOKS NORMAL", say=["looks normal", "fine"])
    assert Rig(Card.model_validate(data)).pb.match_choice(text) == "builtin"


@pytest.mark.parametrize("backtrack", [False, True])
def test_reanswer_invalidates_later_question_reports_even_after_backtracking(backtrack):
    data = question_card().model_dump(mode="json")
    data["steps"][0]["choices"][0]["next"] = "followup"
    data["steps"].insert(1, {"id": "followup", "title": "More detail", "cue": {"line1": "WHICH CHECK?", "line2": ""},
        "kind": "question", "choices": [{"id": "yes", "label": "YES", "next": "a1"}, {"id": "no", "label": "NO", "next": "b1"}]})
    r = Rig(Card.model_validate(data))
    r.pb.choose("builtin")
    r.pb.choose("yes")
    if backtrack:
        r.send("swipe_up")
        r.send("swipe_up")
        assert r.pb.step.id == "which" and not r.pb.path
    r.pb.reanswer("which", "external")
    assert r.pb.step.id == "b1"
    assert [o["step"] for o in r.pb.observations] == ["which"]
    assert "followup" not in r.pb.confirmed


def test_corrected_report_reroutes_and_preserves_completed_actions(tmp_path, monkeypatch):
    rt = runtime(tmp_path, monkeypatch)
    try:
        assert rt.ask("the laptop screen").intent == "choice"
        rt.clock.advance(1700)
        rt.tick()
        rt.playbook.handle_input(G2Input(gesture="swipe_down", seq_seen=rt.hud.current.seq))
        assert "a1" in rt.playbook.confirmed
        result = rt.ask("Actually, I just checked. The external monitor is green too.")
        assert result.intent == "revised"
        assert rt.playbook.observations == [{"step": "which", "choice": "both", "text": "Both displays are affected"}]
        assert rt.playbook.step.id == "b1" and "a1" in rt.playbook.confirmed
        assert not rt.playbook.verified
        rt.clock.advance(1700)
        rt.tick()
        rt.playbook.handle_input(G2Input(gesture="swipe_up", seq_seen=rt.hud.current.seq))
        assert rt.playbook.step.id == "which"  # old branch is no longer the route back
    finally:
        rt.close()


def tire_card():
    data = graph_card().model_dump(mode="json")
    data["steps"][0]["choices"] = [
        {"id": "tube", "label": "INNER TUBE", "say": ["inner tube", "tube"], "next": "a1"},
        {"id": "tubeless", "label": "TUBELESS", "say": ["tubeless"], "next": "b1"},
    ]
    return Card.model_validate(data)


def test_uncertain_correction_reopens_question_without_accepting_guess(tmp_path, monkeypatch):
    rt = runtime(tmp_path, monkeypatch, tire_card())
    try:
        rt.ask("inner tube")
        result = rt.ask("Wait, I think it's actually tubeless")
        assert result.intent == "revised" and "confirm" in result.text.lower()
        assert rt.playbook.step.id == "which" and not rt.playbook.observations
        assert "which" not in rt.playbook.confirmed and not rt.playbook.verified
        assert result.label == "DETERMINISTIC"
    finally:
        rt.close()


@pytest.mark.parametrize("text", ["tubeless ready", "Actually it says tubeless ready", "I think it is tubeless"])
def test_readiness_and_uncertainty_do_not_answer_configuration(text):
    assert Rig(tire_card()).pb.match_choice(text) is None


def test_definite_configuration_correction_follows_new_route(tmp_path, monkeypatch):
    rt = runtime(tmp_path, monkeypatch, tire_card())
    try:
        rt.ask("inner tube")
        assert rt.ask("Sorry, it's actually tubeless").intent == "revised"
        assert rt.playbook.step.id == "b1" and rt.playbook.observations[0]["choice"] == "tubeless"
        assert not rt.playbook.verified
        restored = PlaybookEngine(rt.playbook.card, rt.clock, progress=rt.playbook.progress())
        assert restored.step.id == "b1" and restored.observations == rt.playbook.observations
    finally:
        rt.close()


def test_correction_invalidates_late_assistant_answers(tmp_path, monkeypatch):
    rt = runtime(tmp_path, monkeypatch)
    try:
        rt.ask("laptop screen")
        sid = rt.session().id
        task = rt.assistant.tasks[sid]
        revision = task.revision
        rt.assistant.pending[sid] = "step"
        rt.assistant._latest[sid] = 123
        rt.ask("Actually the external monitor is green too")
        assert sid not in rt.assistant.pending
        assert rt.assistant._latest.get(sid) != 123
        assert task.revision == revision + 1 and task.branch == "both"
    finally:
        rt.close()


@pytest.mark.parametrize("text", ["Sorry, it's actually an MK3S+.", "It's an MK3S+, not an MK4."])
def test_changed_model_does_not_match_old_model_guide(text):
    card = make_card(title="Prusa MK4 extrusion", aliases=["Prusa MK4", "printer extrusion"], goal_mode="fix")
    assert model_conflict(text, card)
    req = GoalRequest(session_id="test", mode="fix", via="phone_text", text="printer extrusion. " + text)
    assert not candidates(req, [card])


def test_units_and_sizes_are_not_model_corrections():
    assert not model_tokens("8mm 3cm 1m 2in 12V 5W 16GB 60Hz 1st 2nd 3rd 4th")


def test_cached_model_variant_cannot_bypass_identity_check(tmp_path, monkeypatch):
    card = make_card(title="Prusa MK3S clogged nozzle", aliases=["Prusa MK3S clogged nozzle"], goal_mode="fix")
    rt = runtime(tmp_path, monkeypatch, card)
    try:
        rt.cache.remember_guide("Prusa MK3S clogged nozzle", "fix", card)
        req = GoalRequest(session_id=rt.session().id, mode="fix", via="phone_text", text="Prusa MK3S+ clogged nozzle")
        assert not rt._reuse_goal(req)
    finally:
        rt.close()


def test_model_correction_drops_old_steps_and_pictures(tmp_path, monkeypatch):
    card = make_card(title="Prusa MK4 extrusion", aliases=["Prusa MK4"], goal_mode="fix")
    rt = runtime(tmp_path, monkeypatch, card)
    try:
        result = rt.ask("Sorry, it's actually an MK3S+, not an MK4.")
        assert result.intent == "goal" and rt.playbook is None
        assert rt.hud.current.image is None and rt.hud.current.step is None
        assert rt.live.active is None  # no live provider enabled in this test
    finally:
        rt.close()
