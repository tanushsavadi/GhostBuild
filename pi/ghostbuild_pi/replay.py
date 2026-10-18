"""Replay a recorded JSONL as observations labelled source="replay" (never pi_live)."""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Dict, Iterator, List, Optional

from .clock import Clock
from .runner import initial_seq

log = logging.getLogger("ghostbuild_pi.replay")


def load_jsonl(path: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                o = json.loads(line)
            except ValueError:
                log.warning("%s:%d is not JSON, skipped", path, i)
                continue
            if isinstance(o, dict) and "camera" in o:
                out.append(o)
    return out


def replay_observations(records: List[Dict[str, Any]], dev: str, clock: Clock,
                        loop: bool = False, default_gap_ms: float = 200.0,
                        seq_start: Optional[int] = None) -> Iterator[tuple]:
    """Yields (gap_ms_before_this, observation). seq/ms/at are re-stamped; source is forced to 'replay'.

    On loop, frame_seq and cmd_seq keep increasing (recorded stuck values stay stuck within a pass).
    """
    if not records:
        return
    seq = seq_start if seq_start is not None else initial_seq(clock.wall_ms())
    fs = [r["camera"]["frame_seq"] for r in records if r.get("camera")]
    cs = [r["led"]["cmd_seq"] for r in records if r.get("led")]
    fs_span = (max(fs) - min(fs) + 1) if fs else 0
    cs_span = (max(cs) - min(cs) + 1) if cs else 0
    npass = 0
    while True:
        prev_ms: Optional[float] = None
        for r in records:
            gap = default_gap_ms
            if prev_ms is not None and isinstance(r.get("ms"), (int, float)) and r["ms"] > prev_ms:
                gap = float(r["ms"] - prev_ms)
            if isinstance(r.get("ms"), (int, float)):
                prev_ms = r["ms"]
            seq += 1
            cam = dict(r["camera"]) if r.get("camera") else None
            led = dict(r["led"]) if r.get("led") else None
            if cam:
                cam["frame_seq"] += npass * fs_span
            if led:
                led["cmd_seq"] += npass * cs_span
            yield (gap if (npass or r is not records[0]) else 0.0), {
                "v": 2, "dev": dev, "seq": seq, "ms": int(clock.now_ms()), "at": clock.wall_ms(),
                "source": "replay", "camera": cam, "led": led, "error": r.get("error"),
            }
        npass += 1
        if not loop:
            return


def run_replay(records: List[Dict[str, Any]], sink: Callable[[Dict[str, Any]], None], clock: Clock, dev: str,
               should_stop: Callable[[], bool], loop: bool = False, duration_s: Optional[float] = None) -> int:
    started = clock.now_ms()
    n = 0
    for gap, obs in replay_observations(records, dev, clock, loop=loop):
        if should_stop():
            break
        clock.sleep(gap / 1000.0)
        if duration_s is not None and clock.now_ms() - started >= duration_s * 1000.0:
            break
        obs["ms"], obs["at"] = int(clock.now_ms()), clock.wall_ms()
        sink(obs)
        n += 1
    return n
