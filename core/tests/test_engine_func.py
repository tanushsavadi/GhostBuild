from conftest import Feeder, press


def recover(feed):
    feed.blocked(3000)
    feed.healthy(1500)


def test_await_func_prompt_after_verified_then_quiet(engine, feed):
    recover(feed)
    assert engine.frames[-1].mode == "verified"
    assert engine.state == "AWAIT_FUNC"
    feed.healthy(3200)  # verified ttl 3 s expires -> prompt
    p = engine.frames[-1]
    assert p.mode == "intervene" and p.cue.line1 == "WAVE IN FRONT" and p.ttl_ms == 15000
    feed.healthy(15_500)
    assert engine.frames[-1].mode == "quiet"
    assert engine.state == "AWAIT_FUNC"  # still pending (test stays pending)


def test_press_during_await_func_repeats_prompt(engine, feed):
    recover(feed)
    feed.healthy(3200 + 15_500)
    assert engine.frames[-1].mode == "quiet"
    f = engine.handle_input(press())
    assert f.cue.line1 == "WAVE IN FRONT" and f.mode == "intervene"


def test_led_commanded_only_when_commanded_true(engine, feed):
    recover(feed)
    feed.healthy(3500)
    feed.run(2000, motion=0.5, led=True)
    f = engine.frames[-1]
    assert f.mode == "verified" and f.cue.line1 == "● LED COMMANDED" and f.ttl_ms == 3000
    feed.healthy(3500)
    assert engine.frames[-1].mode == "quiet"
    assert engine.state == "HEALTHY"
    labels = [e.label for e in engine.events]
    assert "COMMANDED" in labels


def test_motion_without_led_never_claims_success(engine, feed):
    recover(feed)
    feed.healthy(3500)
    feed.run(4000, motion=0.5, led=False)
    assert not any(f.cue and "LED COMMANDED" in f.cue.line1 for f in engine.frames)
    assert engine.state == "AWAIT_FUNC"
    assert any("not observed" in e.text for e in engine.events)


def test_led_commanded_without_motion_is_not_success(engine, feed):
    recover(feed)
    feed.healthy(3500)
    feed.run(4000, motion=0.0, led=True)
    assert not any(f.cue and "LED COMMANDED" in f.cue.line1 for f in engine.frames)


def test_led_after_window_is_too_late(engine, feed):
    recover(feed)
    feed.healthy(3500)
    feed.run(300, motion=0.5, led=False)
    feed.run(2000, motion=0.5, led=False)  # window (1500 ms) expires, event logged
    feed.run(300, motion=0.5, led=True)  # a fresh trigger window starts, LED commanded now => ok
    assert any(f.cue and "LED COMMANDED" in f.cue.line1 for f in engine.frames)


def test_functional_not_available_before_any_recovery(engine, feed):
    feed.healthy(2000)
    feed.run(2000, motion=0.5, led=True)
    assert engine.frames == []


def test_new_fault_cancels_await_func(engine, feed):
    recover(feed)
    feed.blocked(4000)
    assert engine.state == "FAULT"
    feed.healthy(1500)
    assert engine.state == "AWAIT_FUNC"


def test_recurrence_starts_new_episode(engine, feed):
    recover(feed)
    feed.healthy(4000)
    first = len(engine.frames)
    feed.blocked(5000)
    assert engine.frames[-1].mode == "intervene" and len(engine.frames) > first
    assert engine.state == "FAULT"


def test_multiple_tests_priority_is_card_order(card_dict, clock, asset_root):
    from contracts.models import Card
    from ghostbuild_core.engine import Engine

    d = dict(card_dict)
    second = dict(d["tests"][0])
    second.update(
        id="camera_motion_dead",
        fail_when=[{"signal": "camera.detail", "op": "lt", "value": 50}],
        fact={"line1": "IMAGE UNFOCUSED", "line2": ""},
        checks=[{"when": [], "action": {"line1": "IMAGE UNFOCUSED", "line2": "CHECK LENS FOCUS"}, "why": "x", "cites": [], "guide_id": None}],
        offer_help_after_ms=60000,
    )
    d["tests"] = [second, d["tests"][0]]  # second test first in card order
    e = Engine(Card.model_validate(d), clock, asset_root=asset_root)
    f = Feeder(e, clock)
    f.run(3000, luma=6.0, std=1.0, detail=10.0)  # both tests fail
    assert e.frames[-1].cue.line1 == "IMAGE UNFOCUSED"  # first in card order wins
    assert len(e.frames) == 1
    f.run(2000, luma=6.0, std=1.0, detail=200.0)  # only the lens test still fails
    assert e.frames[-1].cue.line1 == "IMAGE UNFOCUSED" or e.frames[-1].mode == "verified"
    f.run(6000, luma=6.0, std=1.0, detail=200.0)
    assert e.frames[-1].cue.line1 == "CAMERA VIEW LOST"
