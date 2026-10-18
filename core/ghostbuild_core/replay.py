"""Replay a recorded JSONL session log through the engine (source forced to "replay").

    python -m ghostbuild_core.replay logs/session-....jsonl [--card knowledge/cards/camera_lens.json]

Public API (the harness a sponsor engineer can extend):
    frames = replay(lines_or_path, card)   # -> list[HudFrame]
Accepted line shapes: {"kind":"observation","t":<core ms>,"obs":{...}} (session log),
{"kind":"input","input":{...g2_input...}}, or a bare Observation object (timed by obs.ms).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable, Optional, Union

from contracts.models import Card, G2Input, HudFrame, Observation

from .clock import ManualClock
from .engine import Engine

STEP_MS = 100


def _records(lines: Iterable[str]) -> list[tuple[int, str, object]]:
    out: list[tuple[int, str, object]] = []
    for raw in lines:
        raw = raw.strip()
        if not raw:
            continue
        try:
            rec = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if rec.get("kind") == "observation" and "obs" in rec:
            if rec.get("accepted") is False:
                continue
            obs = Observation.model_validate(rec["obs"])
            out.append((int(rec["t"]) if rec.get("t") is not None else obs.ms, "obs", obs))
        elif rec.get("kind") == "input" and "input" in rec:
            gi = G2Input.model_validate(rec["input"])
            out.append((int(rec["t"]) if rec.get("t") is not None else -1, "input", gi))
        elif rec.get("type") is None and "dev" in rec and "seq" in rec:
            obs = Observation.model_validate(rec)
            out.append((obs.ms, "obs", obs))
    # keep file order but make time monotonic (inputs without a timestamp inherit the previous time)
    fixed: list[tuple[int, str, object]] = []
    last = 0
    for t, k, v in out:
        t = last if t < 0 else t
        last = max(last, t)
        fixed.append((last, k, v))
    return fixed


def replay(source: Union[str, Path, Iterable[str]], card: Card, *, asset_root: Path | str | None = None, tail_ms: int = 4000) -> list[HudFrame]:
    if isinstance(source, (str, Path)):
        lines: Iterable[str] = Path(source).read_text().splitlines()
    else:
        lines = source
    recs = _records(lines)
    clock = ManualClock()
    eng = Engine(card, clock, asset_root=asset_root, force_source="replay")
    if recs:
        clock.set(recs[0][0] - 1)
        eng._started = clock.now_ms()  # noqa: SLF001 - replay starts the link grace at the first record
    for t, kind, item in recs:
        while clock.now_ms() + STEP_MS < t:
            clock.advance(STEP_MS)
            eng.tick()
        clock.set(max(clock.now_ms(), t))
        if kind == "obs":
            eng.ingest(item)  # type: ignore[arg-type]
        else:
            eng.handle_input(item)  # type: ignore[arg-type]
        eng.tick()
    for _ in range(tail_ms // STEP_MS):
        clock.advance(STEP_MS)
        eng.tick()
    return eng.frames


def _fmt(f: HudFrame) -> str:
    cue = f"{f.cue.line1} / {f.cue.line2}" if f.cue else "(blank)"
    img = f" [image {f.image.view}]" if f.image else ""
    return f"seq {f.seq:3d} {f.mode:9s} src={f.source:9s} {cue}{img}"


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m ghostbuild_core.replay")
    ap.add_argument("log", help="session JSONL recorded by core (or raw observation lines)")
    ap.add_argument("--card", default=None, help="card JSON (default: first valid card in knowledge/cards, else the contract example)")
    ap.add_argument("--root", default=".", help="repo root for guide images")
    args = ap.parse_args(argv)
    if args.card:
        card = Card.model_validate_json(Path(args.card).read_text())
    else:
        from .cards import load_cards

        found = load_cards(Path(args.root) / "knowledge" / "cards") or load_cards(Path(args.root) / "contracts" / "examples")
        if not found:
            print("no Repair Card found; pass --card", file=sys.stderr)
            return 2
        card = found[0]
    frames = replay(args.log, card, asset_root=args.root)
    print(f"REPLAY (not live) {args.log}: {len(frames)} frame(s)")
    for f in frames:
        print(_fmt(f))
    return 0


if __name__ == "__main__":
    sys.exit(main())
