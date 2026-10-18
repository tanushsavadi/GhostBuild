"""Honest async-research queue: an unsupported request is saved as JSON for a human to hand to the research agent.

Nothing is generated, promised or made available now. Files go to <asset_root>/knowledge/requests/<utc-ts>-<n>.json.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional

from .clock import Clock

log = logging.getLogger("ghostbuild.research")

RATE_MS = 2000
SAVED_DETAIL = "saved for async research; not available now"


@dataclass(frozen=True)
class SaveResult:
    status: Literal["saved", "duplicate", "rate_limited", "failed"]
    path: Optional[Path] = None

    @property
    def queued(self) -> bool:
        return self.status in ("saved", "duplicate")


class ResearchQueue:
    def __init__(self, asset_root: Path | str, clock: Clock) -> None:
        self.dir = Path(asset_root) / "knowledge" / "requests"
        self.clock = clock
        self._last_ms: dict[str, int] = {}
        self._seen: dict[tuple[str, str, str], Path] = {}
        self._n = 0

    def save(self, session_id: str, mode: str, text: str, via: str = "phone_text") -> SaveResult:
        text = (text or "").strip()
        key = (session_id, mode, text.lower())
        if key in self._seen:
            return SaveResult("duplicate", self._seen[key])  # already queued this session; never write twice
        now = self.clock.now_ms()
        last = self._last_ms.get(session_id)
        if last is not None and now - last < RATE_MS:
            return SaveResult("rate_limited")
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            utc = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
            while True:
                self._n += 1
                path = self.dir / f"{utc}-{self._n}.json"
                try:
                    fh = open(path, "x", encoding="utf-8")
                except FileExistsError:
                    continue
                break
            with fh:
                json.dump(
                    {
                        "session_id": session_id,
                        "mode": mode,
                        "via": via,
                        "text": text,
                        "requested_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "status": "queued",
                        "note": "unsupported request saved for a human to hand to the research agent; no card exists for it yet",
                    },
                    fh,
                    indent=2,
                    ensure_ascii=False,
                )
        except Exception:
            log.exception("could not save research request")
            return SaveResult("failed")
        self._last_ms[session_id] = now
        self._seen[key] = path
        return SaveResult("saved", path)
