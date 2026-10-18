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


def test_first_screen_lists_what_can_start_and_a_press_starts_it_without_an_error():
    rt, clock = rig(require_device_link=True)
    press_through_welcome(rt, clock)
    m = rt.hud.current.menu
    assert m is not None and m.prompt == "WHAT DO YOU NEED?" and "PI CAMERA VIEW" not in m.options  # no Pi: the fault card is not offered
    rt.handle_input(G2Input(gesture="press", seq_seen=rt.hud.current.seq))
    f = rt.hud.current
    assert f.mode != "error" and not f.stale and rt.sessions.view().phase == "task"


def test_with_a_device_reporting_the_fault_card_is_listed_too():
    from contracts.models import Observation  # noqa: F401  (link state is what matters)

    rt, clock = rig(require_device_link=True, simulate=True)
    press_through_welcome(rt, clock)
    assert any("CAMERA" in o for o in rt.hud.current.menu.options)


def test_simulated_device_keeps_the_fault_card_available():
    rt, _ = rig(require_device_link=True, simulate=True)
    assert "camera_lens" in {c.card_id for c in rt.startable_cards()}
