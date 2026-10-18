"""Without its device a fault card is not offered: FIX on a bench with no Pi must not dead-end in LINK LOST."""

from __future__ import annotations

from pathlib import Path

from contracts.models import G2Input
from ghostbuild_core.cards import load_cards
from ghostbuild_core.clock import ManualClock
from ghostbuild_core.runtime import Runtime

REPO = Path(__file__).resolve().parents[2]


def rig(**kw) -> tuple[Runtime, ManualClock]:
    clock = ManualClock()
    rt = Runtime(load_cards(REPO / "knowledge" / "cards"), clock=clock, asset_root=REPO, **kw)
    from contracts.models import G2Hello

    rt.hello(G2Hello(client_id="g2-test"))
    return rt, clock


def press_through_welcome(rt: Runtime, clock: ManualClock) -> None:
    clock.advance(10_000)
    rt.tick()


def test_fault_cards_hidden_without_a_device_but_every_playbook_remains():
    rt, _ = rig(require_device_link=True)
    ids = {c.card_id for c in rt.startable_cards()}
    assert "camera_lens" not in ids and {"paper_cup", "led_breadboard"} <= ids
    assert "camera_lens" in {c.card_id for c in rt.cards}  # still loaded: a running session can resolve it


def tap(rt):
    rt.handle_input(G2Input(gesture="press", seq_seen=rt.hud.current.seq))


def test_front_screen_is_a_conversation_and_the_failsafe_list_hides_what_cannot_start():
    rt, clock = rig(require_device_link=True)
    press_through_welcome(rt, clock)
    p = rt.hud.current
    assert p.mode == "intervene" and p.menu is None and p.cue.line1 == "WHAT DO YOU NEED?"  # no list, no BUILD/FIX
    tap(rt)
    m = rt.hud.current.menu
    assert m is not None and m.prompt == "PICK A TASK" and "PI CAMERA VIEW" not in m.options  # no Pi: the fault card is not offered
    tap(rt)
    f = rt.hud.current
    assert f.mode != "error" and not f.stale and rt.sessions.view().phase == "task"


def test_with_a_device_reporting_the_fault_card_is_listed_too():
    rt, clock = rig(require_device_link=True, simulate=True)
    press_through_welcome(rt, clock)
    tap(rt)
    assert any("CAMERA" in o for o in rt.hud.current.menu.options)


def test_swipe_up_from_the_top_of_the_failsafe_list_returns_to_the_conversation():
    rt, clock = rig()
    press_through_welcome(rt, clock)
    tap(rt)
    assert rt.hud.current.menu is not None
    rt.handle_input(G2Input(gesture="swipe_up", seq_seen=rt.hud.current.seq))
    assert rt.hud.current.menu is None and rt.hud.current.cue.line1 == "WHAT DO YOU NEED?"


def test_simulated_device_keeps_the_fault_card_available():
    rt, _ = rig(require_device_link=True, simulate=True)
    assert "camera_lens" in {c.card_id for c in rt.startable_cards()}


def test_front_screen_says_hold_to_speak_only_when_voice_is_on():
    rt, clock = rig()
    press_through_welcome(rt, clock)
    assert rt.hud.current.cue.line2 == "TYPE ON YOUR PHONE"
    rt.voice = object()  # VoiceService attaches itself here when enabled
    rt.sessions.refresh()
    assert (rt.hud.current.cue.line1, rt.hud.current.cue.line2) == ("WHAT DO YOU NEED?", "HOLD TO SPEAK")


def test_prompt_rests_when_nothing_is_asked_and_any_gesture_wakes_it_without_acting():
    rt, clock = rig()
    press_through_welcome(rt, clock)
    assert rt.hud.current.cue.line1 == "WHAT DO YOU NEED?"
    clock.advance(21_000)
    rt.tick()
    assert rt.hud.current.mode == "quiet"  # the wearer is not made to stare at a prompt
    tap(rt)  # first gesture wakes the screen, nothing more
    assert rt.hud.current.cue.line1 == "WHAT DO YOU NEED?" and rt.hud.current.menu is None
    tap(rt)  # a second one is the failsafe list
    assert rt.hud.current.menu is not None


def test_hold_to_speak_works_from_the_resting_screen_and_keeps_it_lit():
    rt, clock = rig()
    press_through_welcome(rt, clock)
    clock.advance(21_000)
    rt.tick()
    assert rt.hud.current.mode == "quiet"
    rt.sessions.wake()  # what voice.on_hold does at the start of a hold
    assert rt.hud.current.cue.line1 == "WHAT DO YOU NEED?"
    clock.advance(10_000)
    rt.tick()
    assert rt.hud.current.cue.line1 == "WHAT DO YOU NEED?"  # still within the rest time after the interaction
