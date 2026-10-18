"""One LED, digital output only, COMMANDED state only.

Safety: output pin only (no PWM, no other GPIO touched), 3.3 V logic, pin must be in a config
allowlist unless given explicitly with --led-pin, never toggled faster than 5 Hz, and always
driven off on exit. A GPIO write is a command. It is not measured light.
"""

from __future__ import annotations

import logging
import os
from typing import Dict, Iterable, Optional, Sequence

from .clock import Clock

log = logging.getLogger("ghostbuild_pi.led")

# BCM numbers. Defaults exclude 0-3 (ID EEPROM / I2C with on-board pull-ups).
DEFAULT_ALLOWLIST = tuple(range(4, 28))
EXPLICIT_PIN_RANGE = range(2, 28)
MIN_TOGGLE_INTERVAL_MS = 200.0  # 5 Hz ceiling
ENV_PIN = "GHOSTBUILD_LED_PIN"
ENV_ALLOWLIST = "GHOSTBUILD_LED_ALLOWLIST"


class LedPinError(ValueError):
    pass


class LedUnavailable(RuntimeError):
    pass


def parse_allowlist(text: Optional[str]) -> Sequence[int]:
    if not text:
        return DEFAULT_ALLOWLIST
    try:
        return tuple(int(p) for p in text.split(",") if p.strip())
    except ValueError as e:
        raise LedPinError("LED allowlist must be comma-separated BCM numbers") from e


def resolve_led_pin(cli_pin: Optional[int], env_pin: Optional[str] = None,
                    allowlist: Iterable[int] = DEFAULT_ALLOWLIST) -> Optional[int]:
    """--led-pin is explicit consent (still range-checked). A pin from config/env must be allowlisted."""
    if cli_pin is not None:
        if cli_pin not in EXPLICIT_PIN_RANGE:
            raise LedPinError("BCM GPIO %r refused: explicit --led-pin must be in 2..27" % (cli_pin,))
        if cli_pin in (2, 3):
            log.warning("BCM %d is an I2C pin with on-board pull-ups; make sure that is really your LED pin", cli_pin)
        return cli_pin
    if env_pin not in (None, ""):
        try:
            pin = int(env_pin)
        except ValueError as e:
            raise LedPinError("%s must be an integer BCM pin" % ENV_PIN) from e
        if pin not in set(allowlist):
            raise LedPinError("BCM GPIO %d from config is not in the allowlist; pass --led-pin %d to confirm it" % (pin, pin))
        return pin
    return None


# --------------------------------------------------------------------------- drivers
class DryRunDriver:
    real = False
    name = "dry-run"

    def __init__(self, pin: Optional[int] = None):
        self.pin = pin

    def write(self, on: bool) -> None:
        log.info("[dry-run LED pin=%s] %s", self.pin, "ON" if on else "OFF")

    def close(self) -> None:
        pass


class GpioZeroDriver:
    real = True
    name = "gpiozero"

    def __init__(self, pin: int, active_high: bool = True):
        from gpiozero import LED  # type: ignore  # digital output only; no PWMLED

        self.pin = pin
        self._led = LED(pin, active_high=active_high, initial_value=False)

    def write(self, on: bool) -> None:
        self._led.on() if on else self._led.off()

    def close(self) -> None:
        try:
            self._led.off()
        finally:
            self._led.close()


class RpiGpioDriver:
    real = True
    name = "RPi.GPIO"

    def __init__(self, pin: int, active_high: bool = True):
        import RPi.GPIO as GPIO  # type: ignore

        self._gpio, self.pin, self._active_high = GPIO, pin, active_high
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(pin, GPIO.OUT, initial=self._level(False))

    def _level(self, on: bool):
        return self._gpio.HIGH if (on == self._active_high) else self._gpio.LOW

    def write(self, on: bool) -> None:
        self._gpio.output(self.pin, self._level(on))

    def close(self) -> None:
        try:
            self._gpio.output(self.pin, self._level(False))
        finally:
            self._gpio.cleanup(self.pin)  # only our own pin


def open_driver(pin: Optional[int], dry_run: bool = False, active_high: bool = True):
    """Returns a driver, or raises LedUnavailable with the reason. Never falls back silently."""
    if dry_run:
        return DryRunDriver(pin)
    if pin is None:
        raise LedUnavailable("no LED pin configured (pass --led-pin N, or --dry-run-led)")
    errors = []
    for cls in (GpioZeroDriver, RpiGpioDriver):
        try:
            return cls(pin, active_high)
        except Exception as e:  # ImportError, permission denied, pin factory missing...
            errors.append("%s: %s" % (cls.name, e))
    raise LedUnavailable("no GPIO library could drive BCM %d (%s)" % (pin, "; ".join(errors)))


# --------------------------------------------------------------------------- controller
class LedController:
    def __init__(self, driver, clock: Clock, min_interval_ms: float = MIN_TOGGLE_INTERVAL_MS):
        self.driver = driver
        self.clock = clock
        self.min_interval_ms = max(min_interval_ms, MIN_TOGGLE_INTERVAL_MS)  # never faster than 5 Hz
        self.commanded_on = False
        self.cmd_seq = 0
        self.reason: Optional[str] = None
        self.healthy = True
        self._last_toggle_ms: Optional[float] = None
        try:
            driver.write(False)
        except Exception as e:
            self._fail(e)

    @property
    def real(self) -> bool:
        return bool(getattr(self.driver, "real", False))

    def _fail(self, e: Exception) -> None:
        log.error("LED driver failed (%s); LED disabled, observations will report led=null", e)
        self.healthy = False

    def set(self, on: bool, reason: str, force: bool = False) -> bool:
        """Command the LED. Returns True only if a command was issued. No-op repeats do not count."""
        if not self.healthy or on == self.commanded_on:
            return False
        now = self.clock.now_ms()
        if (not force and self._last_toggle_ms is not None
                and now - self._last_toggle_ms < self.min_interval_ms):
            return False  # rate limited; caller may retry later
        try:
            self.driver.write(on)
        except Exception as e:
            self._fail(e)
            return False
        self.commanded_on, self.reason = on, reason
        self.cmd_seq += 1
        self._last_toggle_ms = now
        return True

    def obs(self) -> Optional[Dict]:
        if not self.healthy:
            return None
        return {"commanded_on": self.commanded_on, "cmd_seq": self.cmd_seq, "reason": self.reason}

    def shutdown(self) -> None:
        """Always drive off, ignoring the rate limit, then release our pin."""
        try:
            if self.commanded_on or self.healthy:
                self.driver.write(False)
        except Exception as e:
            log.error("could not drive LED off at exit: %s", e)
        if self.commanded_on:
            self.commanded_on, self.reason = False, "shutdown"
            self.cmd_seq += 1
        try:
            self.driver.close()
        except Exception as e:
            log.error("LED driver close failed: %s", e)


class MotionLedRule:
    """motion > threshold for >= `frames` consecutive new frames -> LED on for hold_ms, then off."""

    def __init__(self, controller: LedController, threshold: float = 0.15, frames: int = 2,
                 hold_ms: float = 2000.0, enabled: bool = True):
        self.led, self.threshold, self.frames = controller, threshold, frames
        self.hold_ms, self.enabled = hold_ms, enabled
        self._count = 0
        self._off_at: Optional[float] = None

    def reset(self) -> None:
        self._count = 0

    def tick(self, now_ms: float) -> None:
        if self._off_at is not None and now_ms >= self._off_at:
            if not self.led.commanded_on or self.led.set(False, "motion_hold_elapsed"):
                self._off_at = None

    def on_frame(self, motion: float, now_ms: float, scene_change: bool = False) -> None:
        """Call once per NEW frame. scene_change (lens covered/uncovered, exposure jump) cancels counting."""
        self.tick(now_ms)
        if not self.enabled:
            return
        if self.led.commanded_on or scene_change or motion <= self.threshold:
            self._count = 0
            return
        self._count += 1
        if self._count >= self.frames and self.led.set(True, "motion_in_roi"):
            self._off_at = now_ms + self.hold_ms
            self._count = 0
