"""Guide Studio API (read-only): what a loaded guide is built from, and the exact HUD frames the runtime would send for it.

Nothing here researches, compiles or edits a card. Preview frames come from a PRIVATE PlaybookEngine + Hud on a manual clock,
so hud.py stays the only frame writer and the live session, HUD and cards are never touched.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from contracts.models import Card

from .clock import ManualClock
from .hud import Hud
from .playbook import PlaybookEngine

CARD_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
STEP_GAP_MS = 10_000  # far past every HUD throttle and input guard: each preview frame is a settled screen


def _file_ok(root: Path, rel: Optional[str]) -> bool:
    if not rel:
        return False
    base = root.resolve()
    path = (base / rel).resolve()
    return base in path.parents and path.is_file()


def build_record(root: Path, card_id: str) -> Optional[dict]:
    """Build-time compile record (knowledge/compiled/<id>/compile.json or the live cache), if this guide was compiled."""
    if not CARD_ID.match(card_id):
        return None
    for rel in (f"knowledge/compiled/{card_id}/compile.json", f"knowledge/live/compiled_cards/{card_id}/compile.json"):
        if _file_ok(root, rel):
            try:
                d = json.loads((root / rel).read_text(encoding="utf-8"))
            except (OSError, ValueError):
                return None
            keep = ("compile_s", "fetch_s", "images_s", "total_s", "rounds", "errors", "model", "notes", "sources")
            return {k: d.get(k) for k in keep if k in d}
    return None


def preview(card: Card, asset_root: Path) -> list[dict]:
    """Per step: the frame the glasses get when the step opens, and one frame per guide picture (press cycles them)."""
    clock = ManualClock(0)
    hud = Hud(clock, source="manual", min_gap_ms=0)
    pb = PlaybookEngine(card, clock, hud=hud, asset_root=asset_root)
    guides = {g.id: g for g in card.guides}
    out: list[dict] = []
    for i, st in enumerate(card.steps):
        clock.advance(STEP_GAP_MS)
        pb._go(i)
        pb._refresh(immediate=True)
        step_frame = hud.current.model_dump(mode="json")
        pics: list[dict] = []
        g = guides.get(st.guide_id) if st.guide_id else None
        for k, v in enumerate(g.views if g is not None and g.views else []):
            clock.advance(STEP_GAP_MS)
            pb.view_idx = k
            pb._refresh(immediate=True)
            pics.append({
                "view": v.view, "title": v.title, "provenance": v.provenance, "depicts": v.depicts,
                "reference_url": v.reference_url, "fov_note": v.fov_note,
                "available": _file_ok(asset_root, v.image), "phone_available": _file_ok(asset_root, v.phone_image),
                "g2_url": f"/guides/{g.id}/{v.view}.png", "phone_url": f"/guides/{g.id}/{v.view}.phone.png",
                "frame": hud.current.model_dump(mode="json"),
            })
        pb.view_idx = None
        out.append({"step_id": st.id, "index": i, "frame": step_frame, "pictures": pics})
    pb.detach()
    return out


def mount_studio(app: FastAPI, runtime) -> None:
    def card_or_404(card_id: str) -> Card:
        card = runtime.card_by_id(card_id) if CARD_ID.match(card_id) else None
        if card is None or not card.steps:
            raise HTTPException(404, "unknown guide")
        return card

    @app.get("/studio/guides")
    async def studio_guides() -> JSONResponse:
        startable = {c.card_id for c in runtime.startable_cards()}
        product = set(runtime.discovery.cards) if runtime.discovery is not None else set()
        live = runtime.live.cards

        def row(c: Card) -> dict[str, Any]:
            kinds = [s.kind for s in c.steps]
            return {
                "card_id": c.card_id, "title": c.title, "goal_mode": c.goal_mode, "task_kind": c.task_kind,
                "provenance": c.provenance, "review": c.review, "steps": len(c.steps), "questions": kinds.count("question"),
                "hazards": sum(1 for s in c.steps if s.risk == "hazard"), "endings": kinds.count("outcome") + kinds.count("stop"),
                "quoted": sum(1 for s in c.steps if any(ct.quote for ct in s.cites)),
                "cited": sum(1 for s in c.steps if s.cites), "pictures": sum(len(g.views) for g in c.guides),
                "sources": [s.model_dump(mode="json") for s in c.sources],
                "ai_compiled": c.card_id in live or bool(c.review and "AI-compiled" in c.review),
                "compiled": build_record(runtime.asset_root, c.card_id) is not None,
                "open": "task" if c.card_id in startable else "product" if c.card_id in product else None,
            }

        return JSONResponse({"guides": [row(c) for c in runtime.all_cards() if c.steps], "live": runtime.live.view(),
                             "engine": runtime.live.engine, "active": runtime.active_card.card_id})

    @app.get("/studio/preview/{card_id}")
    async def studio_preview(card_id: str) -> JSONResponse:
        card = card_or_404(card_id)
        return JSONResponse({"card_id": card.card_id, "steps": preview(card, runtime.asset_root),
                             "build": build_record(runtime.asset_root, card.card_id),
                             "note": "Frames produced by the same PlaybookEngine and Hud the runtime uses, on a private HUD. "
                                     "A browser rendering of those frames, not a capture from the glasses."})
