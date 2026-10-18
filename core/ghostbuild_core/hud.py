"""THE single HUD writer. Nothing else constructs HudFrames.

Renders engine Views to at most 4 lines, never re-sends an unchanged frame (unless forced by "repeat"),
and holds G2 to <= 4 frames per second by coalescing to the latest view.
"""

from __future__ import annotations

import os
import time
from typing import Callable

from contracts.models import HUD_MAX, HudFrame

from .engine import View

MIN_GAP_S = 0.25
ASCII = os.environ.get("GB_ASCII_HUD") == "1"  # fallback if the glyph test fails on G2
BAR_FULL, BAR_EMPTY = ("=", "-") if ASCII else ("━", "─")
BAR_WIDTH = 14


def _ascii(s: str) -> str:
    return s.replace("●", "*").replace("·", "-").replace("°", " DEG").replace("→", "->") if ASCII else s


def render(view: View) -> list[str]:
    if view.kind == "clear":
        return []
    h = view.lines_hint
    lines = [h[k] for k in ("header", "action", "status") if h.get(k)]
    if view.progress:
        done, total = view.progress
        n = round(BAR_WIDTH * done / total) if total else 0
        lines.append(BAR_FULL * n + BAR_EMPTY * (BAR_WIDTH - n))
    return [_ascii(line)[:HUD_MAX] for line in lines][:4]


class Hud:
    def __init__(self, source: str = "live", clock: Callable[[], float] = time.monotonic) -> None:
        self.source = source
        self.clock = clock
        self.seq = 0
        self.last: HudFrame | None = None
        self.last_at = -1e9
        self.pending: View | None = None
        self.pending_force = False

    def _key(self, f: HudFrame) -> tuple:
        return (f.kind, tuple(f.lines), f.procedure_id, f.step_index, f.mode)

    def update(self, view: View, force: bool = False) -> HudFrame | None:
        """Offer the engine's current view; returns a frame to send now, or None."""
        self.pending, self.pending_force = view, self.pending_force or force
        return self.flush()

    def flush(self) -> HudFrame | None:
        if self.pending is None or self.clock() - self.last_at < MIN_GAP_S:
            return None
        view, force = self.pending, self.pending_force
        self.pending, self.pending_force = None, False
        frame = HudFrame(
            seq=self.seq + 1,
            kind=view.kind,
            lines=render(view),
            ttl_ms=view.ttl_ms,
            procedure_id=view.procedure_id,
            step_index=view.step_index,
            step_total=view.step_total,
            mode=view.mode,
            source=self.source,  # type: ignore[arg-type]
        )
        if self.last is not None and not force and self._key(frame) == self._key(self.last):
            return None
        self.seq += 1
        self.last, self.last_at = frame, self.clock()
        return frame
