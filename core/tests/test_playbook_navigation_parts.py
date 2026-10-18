"""Generic playbook follow-ups added for assembly manuals: 'show me step N', 'which fastener', 'closer look'.

Nothing here knows about any product: a card with steps, Step.parts and guides is enough.
"""

from __future__ import annotations

import pytest

from contracts.models import Card
from ghostbuild_core import intent as intent_mod
from ghostbuild_core.clock import ManualClock
from ghostbuild_core.hud import Hud
from ghostbuild_core.playbook import PlaybookEngine

from pbhelpers import guide_dict, make_card


def _card(n: int = 20) -> Card:
    d = make_card(n, guides=[guide_dict("g3", 2, "knowledge/guides/g3")], guide_steps={2: "g3"}).model_dump(mode="json")
    d["steps"][2]["parts"] = [
        {"id": "101344", "qty": 2, "name": "wooden dowel", "note": None, "avoid": False},
        {"id": "113287", "qty": None, "name": "wide-head screw", "note": "crossed out in this step", "avoid": True},
    ]
    d["steps"][2]["cites"] = [{"source": "x", "loc": "page 7, step 3", "quote": None, "url": None}]
    d["steps"][3]["parts"] = []
    return Card.model_validate(d)


def _pb(card: Card | None = None):
    clock = ManualClock()
    hud = Hud(clock)
    return PlaybookEngine(card or _card(), clock, hud=hud), clock


@pytest.mark.parametrize("text,n", [
    ("show me step 14", 14), ("Show me step 14.", 14), ("go to step 14", 14), ("take me to step 14 please", 14),
    ("step 14", 14), ("jump to step number 14", 14), ("what is step 14", 14), ("back to step 3", 3),
])
def test_goto_intent_extracts_the_step_number(text, n):
    assert intent_mod.classify_playbook(text, []) == "goto"
    assert intent_mod.goto_number(text) == n


@pytest.mark.parametrize("text", ["which step am i on", "what step is this", "how many steps are left", "step by step please", "next step"])
def test_goto_does_not_steal_status_or_next(text):
    assert intent_mod.classify_playbook(text, []) != "goto"


@pytest.mark.parametrize("text", [
    "which fastener do I use", "Which screw?", "which bolt do i use here", "what parts do i need", "which part is this",
    "what hardware goes with this", "which dowel", "what do I need for this step", "which cam lock",
])
def test_parts_intent(text):
    assert intent_mod.classify_playbook(text, []) == "parts"


@pytest.mark.parametrize("text", ["show me a closer look", "closer look", "zoom in", "can I see it bigger", "give me a closer view"])
def test_closer_look_is_a_picture_request(text):
    assert intent_mod.classify_playbook(text, []) == "picture"


def test_goto_navigates_without_confirming_anything():
    pb, clock = _pb()
    clock.advance(1000)
    res = pb.ask("show me step 14")
    assert pb.index == 13 and pb.confirmed == [] and res.intent == "goto" and res.answered
    assert "14" in res.text and "20" in res.text
    assert pb.hud.current.step is not None and pb.hud.current.step.index == 13


def test_goto_out_of_range_is_refused_honestly():
    pb, _ = _pb()
    res = pb.ask("show me step 99")
    assert pb.index == 0 and not res.answered and "20" in res.text


def test_goto_backwards_keeps_earlier_confirmations():
    pb, clock = _pb()
    for _ in range(3):
        clock.advance(1000)
        pb.ask("done")
    assert pb.index == 3 and len(pb.confirmed) == 3
    pb.ask("go to step 2")
    assert pb.index == 1 and len(pb.confirmed) == 3


def test_parts_answer_uses_the_printed_parts_only_and_flags_avoid():
    pb, clock = _pb()
    pb.ask("show me step 3")
    res = pb.ask("which fastener do I use")
    assert res.intent == "parts" and res.answered
    assert "101344" in res.text and "2" in res.text
    assert "113287" in res.text and "not" in res.text.lower()  # the crossed-out screw is named as NOT to use
    assert res.cue.line1 != "" and len(res.cue.line1) <= 24 and len(res.cue.line2) <= 26
    assert res.label in ("MANUFACTURER DOC", "AUTHORED DEMO METADATA", "DETERMINISTIC") or res.label == pb.card.provenance


def test_parts_on_a_step_without_parts_says_nothing_is_printed():
    pb, _ = _pb()
    pb.ask("show me step 4")
    res = pb.ask("which screw")
    assert res.intent == "parts" and not res.answered
    assert "101344" not in res.text


def test_closer_look_opens_the_first_picture_and_never_advances():
    pb, clock = _pb(_card())
    pb.ask("show me step 3")
    before = (pb.index, list(pb.confirmed))
    # the fixture guide image does not exist on disk: the engine falls back to text and must still not advance
    pb.ask("show me a closer look")
    assert (pb.index, list(pb.confirmed)) == before
