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


def test_menu_defaults_to_build_and_first_press_starts_a_playbook_not_an_error():
    rt, clock = rig(require_device_link=True)
    press_through_welcome(rt, clock)
    assert rt.hud.current.menu is not None and rt.hud.current.menu.selected == 1  # BUILD
    rt.handle_input(G2Input(gesture="press", seq_seen=rt.hud.current.seq))
    f = rt.hud.current
    assert f.mode != "error" and not f.stale


def test_choosing_fix_with_no_device_says_nothing_loaded_not_stale_data():
    rt, clock = rig(require_device_link=True)
    press_through_welcome(rt, clock)
    rt.handle_input(G2Input(gesture="swipe_up", seq_seen=rt.hud.current.seq))  # FIX
    rt.handle_input(G2Input(gesture="press", seq_seen=rt.hud.current.seq))
    f = rt.hud.current
    assert not f.stale and f.mode != "error"
    assert rt.sessions.view().phase == "menu"  # still choosing; no task was started


def test_simulated_device_keeps_the_fault_card_available():
    rt, _ = rig(require_device_link=True, simulate=True)
    assert "camera_lens" in {c.card_id for c in rt.startable_cards()}
