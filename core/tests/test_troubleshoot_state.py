"""'That did not work' is answered from card checks and from what the wearer already did, never repeated, never invented."""

from __future__ import annotations

from contracts.models import Card
from pbhelpers import Rig, make_card


def card_with_checks() -> Card:
    c = make_card(4).model_dump(mode="json")
    chk = lambda text, why, line2="": {"when": [], "action": {"line1": text, "line2": line2}, "why": why, "cites": [], "guide_id": None}
    c["steps"][0]["troubleshoot"] = [chk("CHECK LED DIRECTION", "Long leg is positive.")]
    c["steps"][1]["troubleshoot"] = [chk("CHECK SOURCE", "Source for this step.", "SEE PHONE"), chk("CHECK PIN 11", "Pin 11 is GPIO17."), chk("CHECK PIN 9", "Pin 9 is ground.")]
    c["steps"][3]["troubleshoot"] = [chk("CHECK STEP FOUR", "Not reached yet.")]
    return Card.model_validate(c)


def ask(r: Rig, text="that didn't work"):
    r.wait(4100)  # let any previous answer flash expire
    return r.pb.ask(text)


def walk_to(r: Rig, index: int) -> None:
    while r.pb.index < index:
        r.wait(2000)
        r.send("swipe_down")


def test_current_step_checks_in_card_order_then_confirmed_earlier_steps_then_exhausted():
    r = Rig(card_with_checks())
    walk_to(r, 2)  # steps 0 and 1 confirmed; step 2 has no checks of its own
    a = [ask(r) for _ in range(5)]
    # step 2 has none, so the most recent confirmed step (1) first, in card order, source links skipped, then step 0
    assert [x.cue.line1 for x in a] == ["CHECK PIN 11", "CHECK PIN 9", "CHECK LED DIRECTION", "NO MORE CHECKS HERE", "NO MORE CHECKS HERE"]
    assert "From step 2, which you already confirmed" in a[0].detail
    assert a[3].label == "DETERMINISTIC" and "3 checks" in a[3].detail
    assert all("CHECK STEP FOUR" not in x.text for x in a)  # a step not reached yet is never consulted


def test_current_step_first_and_tried_list_resets_when_a_step_is_confirmed():
    r = Rig(card_with_checks())
    walk_to(r, 1)
    assert ask(r).cue.line1 == "CHECK PIN 11"  # own step first, not the earlier LED check
    assert ask(r).cue.line1 == "CHECK PIN 9"
    assert ask(r).cue.line1 == "CHECK LED DIRECTION"
    r.wait(2000)
    r.send("swipe_down")  # progress: a new situation, suggestions start over
    r.wait(2000)
    again = ask(r)  # now on step 2 (no checks of its own): the confirmed step 1's checks come back from the top
    assert again.cue.line1 == "CHECK PIN 11" and "which you already confirmed" in again.detail


def test_asking_never_confirms_a_step_and_events_record_what_was_suggested():
    r = Rig(card_with_checks())
    walk_to(r, 1)
    before = (r.pb.index, list(r.pb.confirmed))
    ask(r)
    assert (r.pb.index, list(r.pb.confirmed)) == (before[0], before[1])
    texts = [e.text for e in r.pb.events]
    assert any(t.startswith("problem reported; suggested check 1: CHECK PIN 11") for t in texts)


def test_natural_symptom_phrases_route_to_troubleshoot():
    from ghostbuild_core.intent import classify_playbook

    for phrase in ["the LED isn't lighting up", "it doesn't light", "nothing's happening", "the LED is not blinking", "no light at all", "it's not working"]:
        assert classify_playbook(phrase, []) == "troubleshoot", phrase


def test_spoken_filler_does_not_make_a_deictic_question_abstain():
    r = Rig(make_card(4, guides=None))
    for phrase in ["wait where exactly is that", "hey, why do I do this", "um where does it go"]:
        res = ask(r, phrase)
        assert res.intent in ("where", "why") and res.answered, phrase
