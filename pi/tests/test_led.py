import pytest

from ghostbuild_pi.clock import FakeClock
from ghostbuild_pi.led import (DryRunDriver, LedController, LedPinError, LedUnavailable, MotionLedRule, open_driver,
                               parse_allowlist, resolve_led_pin)


class Rec:
    real = True
    name = "rec"

    def __init__(self):
        self.writes = []
        self.closed = False

    def write(self, on):
        self.writes.append(on)

    def close(self):
        self.closed = True


def mk():
    clock, drv = FakeClock(), Rec()
    return LedController(drv, clock), drv, clock


def test_starts_off_and_cmd_seq_counts_changes_only():
    led, drv, clock = mk()
    assert drv.writes == [False] and led.obs() == {"commanded_on": False, "cmd_seq": 0, "reason": None}
    assert led.set(True, "manual") and led.cmd_seq == 1
    assert not led.set(True, "manual")  # no-op repeat is not a command
    clock.advance(300)
    assert led.set(False, "manual") and led.cmd_seq == 2
    assert led.obs() == {"commanded_on": False, "cmd_seq": 2, "reason": "manual"}


def test_never_toggles_faster_than_5hz():
    led, drv, clock = mk()
    assert led.set(True, "a")
    clock.advance(199)
    assert not led.set(False, "b") and led.commanded_on
    clock.advance(1)
    assert led.set(False, "b")
    fast = LedController(Rec(), clock, min_interval_ms=1)
    assert fast.min_interval_ms >= 200  # cannot be configured faster than the ceiling


def test_shutdown_always_drives_off_even_when_rate_limited():
    led, drv, clock = mk()
    led.set(True, "a")
    clock.advance(10)  # well inside the rate limit
    led.shutdown()
    assert drv.writes[-1] is False and drv.closed and not led.commanded_on


def test_driver_failure_disables_led_reporting():
    class Bad(Rec):
        def write(self, on):
            if on:
                raise OSError("permission denied")

    led = LedController(Bad(), FakeClock())
    assert not led.set(True, "x")
    assert led.obs() is None and not led.commanded_on and led.cmd_seq == 0


def test_motion_rule_needs_two_consecutive_frames_then_holds_two_seconds():
    led, drv, clock = mk()
    rule = MotionLedRule(led)
    rule.on_frame(0.5, clock.now_ms())
    assert not led.commanded_on
    clock.advance(200)
    rule.on_frame(0.1, clock.now_ms())  # below threshold resets the count
    clock.advance(200)
    rule.on_frame(0.5, clock.now_ms())
    clock.advance(200)
    rule.on_frame(0.5, clock.now_ms())
    assert led.commanded_on and led.reason == "motion_in_roi"
    on_at = clock.now_ms()
    clock.advance(1700)
    rule.on_frame(0.9, clock.now_ms())
    assert led.commanded_on  # continued motion does not extend or retrigger
    clock.advance(400)
    rule.tick(clock.now_ms())
    assert not led.commanded_on and clock.now_ms() - on_at >= 2000
    assert led.cmd_seq == 2


def test_motion_exactly_at_threshold_does_not_count():
    led, _, clock = mk()
    rule = MotionLedRule(led)
    for _ in range(5):
        rule.on_frame(0.15, clock.now_ms())
        clock.advance(200)
    assert not led.commanded_on


def test_scene_change_cancels_counting():
    led, _, clock = mk()
    rule = MotionLedRule(led)
    rule.on_frame(0.9, clock.now_ms(), scene_change=True)
    clock.advance(200)
    rule.on_frame(0.9, clock.now_ms(), scene_change=False)
    assert not led.commanded_on


def test_motion_rule_can_be_disabled():
    led, _, clock = mk()
    rule = MotionLedRule(led, enabled=False)
    for _ in range(5):
        rule.on_frame(0.9, clock.now_ms())
        clock.advance(200)
    assert not led.commanded_on


def test_rapid_retrigger_never_exceeds_5hz():
    led, drv, clock = mk()
    rule = MotionLedRule(led, hold_ms=200)
    for _ in range(60):
        rule.on_frame(0.9, clock.now_ms())
        clock.advance(100)
    assert led.cmd_seq <= 6000 / 200  # at most one command per 200 ms over 6 s


def test_pin_policy():
    assert resolve_led_pin(17) == 17
    assert resolve_led_pin(None) is None
    assert resolve_led_pin(None, "17") == 17  # in default allowlist
    with pytest.raises(LedPinError):
        resolve_led_pin(None, "17", allowlist=[22, 23])  # config pin not allowlisted
    assert resolve_led_pin(17, "99", allowlist=[22]) == 17  # explicit --led-pin wins
    for bad in (0, 1, 28, -1, 40):
        with pytest.raises(LedPinError):
            resolve_led_pin(bad)
    with pytest.raises(LedPinError):
        resolve_led_pin(None, "abc")
    assert parse_allowlist("17, 27") == (17, 27)
    with pytest.raises(LedPinError):
        parse_allowlist("x")


def test_open_driver_never_silently_falls_back_to_dry_run():
    assert isinstance(open_driver(17, dry_run=True), DryRunDriver)
    assert isinstance(open_driver(None, dry_run=True), DryRunDriver)
    with pytest.raises(LedUnavailable):
        open_driver(None)
    with pytest.raises(LedUnavailable):  # no gpiozero / RPi.GPIO on the laptop
        open_driver(17)
