"""Injectable clock so everything is testable without sleeping."""

from __future__ import annotations

import time


class Clock:
    """Real time. now_ms() is monotonic; wall_ms() is epoch ms (advisory)."""

    def now_ms(self) -> float:
        return time.monotonic() * 1000.0

    def wall_ms(self) -> int:
        return int(time.time() * 1000)

    def sleep(self, seconds: float) -> None:
        if seconds > 0:
            time.sleep(seconds)


class FakeClock(Clock):
    """Manually advanced clock; sleep() advances it."""

    def __init__(self, start_ms: float = 1000.0, wall_start_ms: int = 1_792_283_000_000):
        self._now = float(start_ms)
        self._wall0 = int(wall_start_ms)
        self._start = float(start_ms)

    def now_ms(self) -> float:
        return self._now

    def wall_ms(self) -> int:
        return int(self._wall0 + (self._now - self._start))

    def advance(self, ms: float) -> None:
        self._now += ms

    def sleep(self, seconds: float) -> None:
        self._now += seconds * 1000.0
