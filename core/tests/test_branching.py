"""Branching guides: question steps choose the route, observations are HUMAN CONFIRMED reports, back follows the route taken."""

from __future__ import annotations

import pytest

from contracts.models import Card
from pbhelpers import Rig


def graph_card() -> Card:
    def step(id, line1, **kw):
        return {"id": id, "title": id, "cue": {"line1": line1, "line2": ""}, **kw}

    return Card.model_validate({
        "v": 2, "card_id": "graph", "title": "Graph", "provenance": "AUTHORED DEMO METADATA",
        "sources": [{"id": "s", "kind": "AUTHORED DEMO METADATA", "title": "test"}],
        "task_kind": "diagnosis",
        "steps": [
            step("which", "WHICH DISPLAY?", kind="question", choices=[
                {"id": "builtin", "label": "BUILT-IN SCREEN", "say": ["built in", "laptop screen"], "next": "a1", "records": "Only the built-in display"},
                {"id": "external", "label": "EXTERNAL MONITOR", "say": ["external", "monitor"], "next": "b1", "records": "Only the external display"},
            ]),
            step("a1", "RESTART THE MAC", next="a_done"),
            step("b1", "RESEAT THE CABLE", risk="hazard"),
            step("b_done", "EXTERNAL CHECKED", kind="outcome"),
            step("a_done", "BUILT-IN CHECKED", kind="stop"),
        ],
    })


def test_question_step_is_a_menu_and_press_follows_the_highlighted_answer():
    r = Rig(graph_card())
    f = r.cur
    assert f.mode == "menu" and f.menu.options == ["BUILT-IN SCREEN", "EXTERNAL MONITOR"] and f.menu.selected == 0
    r.send("swipe_down")
    assert r.cur.menu.selected == 1 and r.pb.index == 0 and not r.pb.confirmed  # moving the highlight decides nothing
    r.send("press")
    assert r.pb.step.id == "b1" and r.pb.observations == [{"step": "which", "choice": "external", "text": "Only the external display"}]
    assert any(e.label == "HUMAN CONFIRMED" and "Only the external display" in e.text for e in r.pb.events)
    assert r.pb.playbook_state().observations == ["Only the external display"]


def test_spoken_answer_matches_deterministically_and_ambiguity_does_not_choose():
    r = Rig(graph_card())
    assert r.pb.match_choice("it's only on my external monitor") == "external"
    assert r.pb.match_choice("both the laptop screen and the external monitor") is None  # two answers: ask, don't guess
    assert r.pb.match_choice("the second one") == "external"
    assert r.pb.match_choice("I first noticed it this morning after an update") is None


def test_back_follows_the_route_and_a_jump_target_is_honoured():
    r = Rig(graph_card())
    r.pb.choose("builtin")
    assert r.pb.step.id == "a1"
    r.confirm()
    assert r.pb.step.id == "a_done"  # `next` skips the other branch
    r.send("swipe_up")
    assert r.pb.step.id == "a1"
    r.send("swipe_up")
    assert r.pb.step.id == "which" and r.cur.mode == "menu"


def test_hazard_step_needs_a_second_deliberate_swipe():
    r = Rig(graph_card())
    r.pb.choose("external")
    r.confirm()
    assert r.pb.step.id == "b1" and "b1" not in r.pb.confirmed and r.cur.cue.line1 == "SAFETY STEP: DONE IT?"
    r.send("swipe_down")
    assert "b1" in r.pb.confirmed and r.pb.step.id == "b_done"


def test_stop_and_outcome_steps_end_the_guide_honestly():
    r = Rig(graph_card())
    r.pb.choose("builtin")
    r.confirm()
    r.confirm()
    assert r.pb.done and r.cur.cue.line1 == "STOPPED SAFELY HERE"
    r2 = Rig(graph_card())
    r2.pb.choose("external")
    r2.confirm()
    r2.send("swipe_down")
    r2.confirm()
    assert r2.pb.done and r2.cur.cue.line1 == "✓ GUIDE FINISHED" and not r2.pb.verified


def test_route_and_observations_survive_a_restart():
    from ghostbuild_core.playbook import PlaybookEngine

    r = Rig(graph_card())
    r.pb.choose("builtin")
    again = PlaybookEngine(r.pb.card, r.clock, progress=r.pb.progress())
    assert again.step.id == "a1" and again.observations[0]["choice"] == "builtin" and again.path == [0]


def test_cards_with_dangling_routes_or_one_choice_questions_are_rejected():
    c = graph_card().model_dump(mode="json")
    c["steps"][1]["next"] = "nowhere"
    with pytest.raises(ValueError):
        Card.model_validate(c)
    c = graph_card().model_dump(mode="json")
    c["steps"][0]["choices"] = c["steps"][0]["choices"][:1]
    with pytest.raises(ValueError):
        Card.model_validate(c)


def test_linear_cards_are_unchanged():
    from pbhelpers import make_card

    r = Rig(make_card(3))
    r.confirm()
    r.send("swipe_up")
    assert r.pb.index == 0 and r.cur.mode == "step"


def test_expected_state_requests_use_the_sources_words_or_say_it_is_not_described():
    c = graph_card().model_dump(mode="json")
    c["steps"][1]["expected"] = "The Apple logo appears and the desktop colours look normal."
    r = Rig(Card.model_validate(c))
    r.pb.choose("builtin")
    res = r.pb.ask("what should it look like when it's done?")
    assert res.intent == "correct" and "desktop colours look normal" in res.detail and r.cur.answer is not None
    r.send("press")
    r.confirm()  # a1 -> a_done (no expected text)
    res = r.pb.ask("how do I know it worked")
    assert res.intent == "correct" and "does not describe" in res.detail and not r.pb.verified


def test_engine_summary_describes_every_guide_from_its_data(tmp_path):
    from fastapi.testclient import TestClient

    from ghostbuild_core.clock import ManualClock
    from ghostbuild_core.runtime import Runtime
    from ghostbuild_core.server import create_app

    rt = Runtime([graph_card()], clock=ManualClock(), log_dir=tmp_path, asset_root=tmp_path, brain=None)
    with TestClient(create_app(rt, tick_interval=None)) as c:
        g = c.get("/engine/summary").json()["guides"][0]
    assert g["task_kind"] == "diagnosis" and g["questions"] == 1 and g["endings"] == 2 and g["hazards"] == 1 and g["quoted"] == 0
