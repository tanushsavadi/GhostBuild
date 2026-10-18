"""Pure intent rules + grounded answer assembly (no server, no engine)."""

import pytest

from contracts.models import Card, Cue
from ghostbuild_core import intent as I


@pytest.mark.parametrize(
    "text,expected",
    [
        ("where is it?", "where"),
        ("Where is the camera lens", "where"),
        ("how do I fix it?", "how"),
        ("what should it look like?", "correct_look"),
        ("why does it matter?", "why"),
        ("what if that didn't work?", "fallback_if_failed"),
        ("what if that didn’t work", "fallback_if_failed"),
        ("it's still black", "fallback_if_failed"),
        ("show the next picture", "next_picture"),
        ("previous", "previous_picture"),
        ("go back", "previous_picture"),
        ("what's wrong?", "status"),
        ("is it fixed", "status"),
        ("banana", "unknown"),
        ("", "unknown"),
        ("   ", "unknown"),
    ],
)
def test_classify(text, expected):
    assert I.classify(text) == expected


def test_classify_is_total_and_closed():
    for t in ["a", "uh", "the sky is blue", "12345", "WHERE", "HoW"]:
        assert I.classify(t) in I.INTENTS


def test_goal_mode_inference():
    assert I.infer_goal_mode("my camera view is black") == "fix"
    assert I.infer_goal_mode("set up the station") == "build"
    assert I.infer_goal_mode("fix my setup") == "fix"
    assert I.infer_goal_mode("hello") == "fix"


def test_wrap_two_lines_limits_and_never_adds_words():
    c = I.wrap_two_lines("A lens cover is the first check")
    assert c is not None and len(c.line1) <= 24 and len(c.line2) <= 26
    assert (c.line1 + " " + c.line2).split() == "A LENS COVER IS THE FIRST CHECK".split()
    assert I.wrap_two_lines("x " * 40) is None
    assert I.wrap_two_lines("") is None


def test_shorten_why_picks_a_fitting_fragment_and_skips_authoring_notes():
    why = "Dark frames mean little light. Placeholder threshold, calibrate on the Pi spike."
    c = I.shorten_why(why)
    assert c is not None and "PLACEHOLDER" not in (c.line1 + c.line2)
    assert I.shorten_why("This sentence is far too long to be shown on two short glasses lines at all, sorry") is None


def test_shorten_why_real_card_text_does_not_fit_and_falls_back_to_phone():
    real = "Dark and flat frames mean little light reaches the sensor. A lens cover or paper flap is the first thing to check."
    assert I.shorten_why(real) is None


def _ctx(card_dict, **kw):
    card = Card.model_validate(card_dict)
    t = card.tests[0]
    base = dict(card=card, fault=t, check=t.checks[0], check_idx=0, guide=card.guides[0])
    base.update(kw)
    return I.Ctx(**base)


def test_answers_come_from_card_fields(card_dict):
    ctx = _ctx(card_dict)
    assert I.answer("where", ctx).kind == "help_goto" and I.answer("where", ctx).target == "where"
    assert I.answer("correct_look", ctx).target == "correct"
    assert I.answer("next_picture", ctx).target == "next"
    assert I.answer("status", ctx).cue == ctx.fault.fact
    r = I.answer("why", ctx)  # real why is too long for two glasses lines
    assert r.cue == I.NOT_IN_CARD and r.phone_text == ctx.check.why and r.phone_label == ctx.card.provenance


def test_why_short_text_is_shown_verbatim_uppercase(card_dict):
    card_dict["tests"][0]["checks"][0]["why"] = "Dark frames mean low light"
    r = I.answer("why", _ctx(card_dict))
    assert r.kind == "show" and (r.cue.line1 + " " + r.cue.line2).split() == "DARK FRAMES MEAN LOW LIGHT".split()


def test_fallback_uses_next_documented_check_else_not_in_card(card_dict):
    assert I.answer("fallback_if_failed", _ctx(card_dict)).cue == I.NOT_IN_CARD
    card_dict["tests"][0]["checks"].append(
        {"when": [], "action": {"line1": "CHECK USB CABLE", "line2": "AT THE PI"}, "why": "Cable.", "cites": [], "guide_id": None}
    )
    r = I.answer("fallback_if_failed", _ctx(card_dict))
    assert r.cue == Cue(line1="CHECK USB CABLE", line2="AT THE PI")


def test_unknown_and_error_and_healthy(card_dict):
    assert I.answer("unknown", _ctx(card_dict)).cue == I.NOT_SURE
    assert I.answer("where", _ctx(card_dict, erroring=True)).kind == "suppress"
    assert I.answer("where", _ctx(card_dict, fault=None, check=None)).kind == "status"
    assert I.NOT_SURE.line2 == "TRY: WHERE? HOW?"


@pytest.mark.parametrize("text", [
    "What is the next step?", "Why is the next step important?",
    "What if I am done but it still looks wrong?", "I am not done",
    "Don't continue", "I think I am done", "why should I go back to the previous step?",
])
def test_questions_and_ambiguous_speech_never_confirm_or_navigate(text):
    assert I.classify_playbook(text, []) not in ("next", "back")


@pytest.mark.parametrize("text", ["next", "please continue", "I'm done", "I've done that. What's next?", "I have finished this", "all done", "next step please"])
def test_deliberate_control_utterances_can_request_manual_progress(text):
    assert I.classify_playbook(text, []) == "next"


@pytest.mark.parametrize("text,intent", [("show me how", "how"), ("How do I do this?", "how"), ("What should it look like?", "correct"), ("repeat that", "repeat")])
def test_explicit_visual_and_repeat_intents(text, intent):
    assert I.classify_playbook(text, []) == intent
