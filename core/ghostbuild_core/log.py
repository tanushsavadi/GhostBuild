"""Append-only JSONL session log (observations, events, frames, inputs). Never raises into the cue path."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Optional

log = logging.getLogger("ghostbuild.log")


class EventLog:
    def __init__(self, directory: Path | str | None, clock=None) -> None:
        self.path: Optional[Path] = None
        self._fh = None
        self._clock = clock
        if directory is None:
            return
        try:
            d = Path(directory)
            d.mkdir(parents=True, exist_ok=True)
            self.path = d / f"session-{time.strftime('%Y%m%d-%H%M%S')}-{int(time.time() * 1000) % 100000}.jsonl"
            self._fh = open(self.path, "a", buffering=1)
        except Exception:
            log.exception("session log disabled")
            self._fh = None

    def write(self, kind: str, **data: Any) -> None:
        if self._fh is None:
            return
        try:
            rec = {"kind": kind, "t": self._clock.now_ms() if self._clock is not None else None, "wall": int(time.time() * 1000), **data}
            self._fh.write(json.dumps(rec, default=str) + "\n")
        except Exception:
            log.exception("session log write failed")

    def close(self) -> None:
        if self._fh is not None:
            try:
                self._fh.close()
            except Exception:
                pass
            self._fh = None
