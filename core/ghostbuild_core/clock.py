"""Injectable clocks so the engine, tests and replay are deterministic and fast."""

from __future__ import annotations

import time
from typing import Callable, Union


class Clock:
    """now_ms(): monotonic milliseconds (all timing decisions). epoch_ms(): wall clock for Evidence.at only."""

    def now_ms(self) -> int:  # pragma: no cover - interface
        raise NotImplementedError

    def epoch_ms(self) -> int:  # pragma: no cover - interface
        raise NotImplementedError


class SystemClock(Clock):
    def __init__(self) -> None:
        self._t0 = time.monotonic()

    def now_ms(self) -> int:
        return int((time.monotonic() - self._t0) * 1000)

    def epoch_ms(self) -> int:
        return int(time.time() * 1000)


class ManualClock(Clock):
    """Time only moves when told to."""

    def __init__(self, start_ms: int = 0, epoch_base_ms: int = 1_792_283_000_000) -> None:
        self._now = int(start_ms)
        self._epoch_base = int(epoch_base_ms)

    def now_ms(self) -> int:
        return self._now

    def epoch_ms(self) -> int:
        return self._epoch_base + self._now

    def advance(self, ms: int) -> int:
        self._now += int(ms)
        return self._now

    def set(self, ms: int) -> int:
        self._now = int(ms)
        return self._now


class _CallableClock(Clock):
    def __init__(self, fn: Callable[[], int]) -> None:
        self._fn = fn

    def now_ms(self) -> int:
        return int(self._fn())

    def epoch_ms(self) -> int:
        return int(time.time() * 1000)


def as_clock(c: Union[Clock, Callable[[], int], None]) -> Clock:
    if c is None:
        return SystemClock()
    if isinstance(c, Clock):
        return c
    return _CallableClock(c)
