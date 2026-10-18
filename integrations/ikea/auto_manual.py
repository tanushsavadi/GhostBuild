"""Any IKEA assembly manual -> a per-step guide like the prepared MICKE bundle, built on demand.

Measured from the PDF (same helpers as tools/build_manual.py): where each numbered step is, its printed quantities and part
numbers, and the official drawing cropped to that step ("where") and to its parts closeup ("how"). The short glasses line per step
is written by one vision call that looks at those crops; it is AI-written and NOT human-reviewed, and says so. Without that call
each step still gets its own official picture, its number and the printed quantities; nothing is invented.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import re
from pathlib import Path
from typing import Callable, Optional

from .manual import Band, crop_pt, g2_image, occurrences, parts_box, pdf_words, phone_image, png, render_page, step_bands

log = logging.getLogger("ghostbuild.ikea.auto_manual")
DPI = 150
REVIEW = "Pictures: official manual crops. Step text: AI-written from those pictures, not human-reviewed. Check each picture."


def download(url: str, dest: Path, timeout: float = 30.0) -> Path:
    if dest.is_file() and dest.stat().st_size > 1000:
        return dest
    import httpx

    r = httpx.get(url, timeout=timeout, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0 GhostBuild"})
    r.raise_for_status()
    if not r.content.startswith(b"%PDF"):
        raise ValueError("not a PDF")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(r.content)
    return dest


def printed_parts(b: Band) -> list[dict]:
    """Pair each printed quantity ("2x") with the part number printed nearest to it in the same step."""
    out, used = [], set()
    for q in b.qty:
        near = sorted((abs(i.x0 - q.x0) + abs(i.y0 - q.y0), k) for k, i in enumerate(b.ids) if k not in used)
        if near and near[0][0] < 120:
            used.add(near[0][1])
            out.append({"id": b.ids[near[0][1]].text, "qty": int(q.text[:-1]) or None})
    out += [{"id": i.text, "qty": None} for k, i in enumerate(b.ids) if k not in used]
    return [p for p in out if p["qty"] is None or p["qty"] >= 1][:8]


def _boxes(b: Band):
    band = (23, max(20, b.y0 - 4), 580, min(795, b.y1 + 8))
    pb = parts_box(b, margin=90)
    if pb:  # include the closeup circles and arrows around the printed numbers, as the prepared bundle does
        x0, y0, x1, y1 = pb
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        pb = (max(15, min(x0, cx - 120)), max(b.y0, min(y0, cy - 80)), min(580, max(x1, cx + 120)), min(b.y1, max(y1, cy + 80)))
    return band, pb


def describe_steps(crops: dict[int, bytes], name: str, parts: dict[int, list[dict]]) -> dict[int, dict]:
    """One vision call: a short action per step, from the official drawing only."""
    from pydantic import BaseModel

    from knowledge.compile import MODEL, _client

    class StepText(BaseModel):
        n: int
        line1: str
        line2: str
        title: str
        detail: str

    class Steps(BaseModel):
        steps: list[StepText]

    content: list[dict] = [{"type": "text", "text": (
        f"These are the numbered steps of the official IKEA assembly manual for {name}. For EACH step write what the drawing shows "
        "the person doing, for smart-glasses captions: line1 at most 22 characters, line2 at most 24, ALL CAPS, everyday words "
        "(for example FIT 4 WOODEN DOWELS / INTO THE SIDE PANEL). Keep printed quantities. title: 2-5 words. detail: one or two "
        "plain sentences. Only describe what is drawn; if a step is unclear, say MATCH THE PICTURE. Never name a screw or part "
        "that is not drawn, never add safety claims the manual does not draw.")}]
    for n, data in sorted(crops.items()):
        printed = ", ".join(f"{p['qty']}x {p['id']}" if p["qty"] else p["id"] for p in parts.get(n, [])) or "none printed"
        content += [{"type": "text", "text": f"STEP {n} (printed parts: {printed})"},
                    {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": base64.standard_b64encode(data).decode()}}]
    resp = _client().messages.parse(model=MODEL, max_tokens=8000, messages=[{"role": "user", "content": content}],
                                    output_format=Steps, output_config={"effort": "low"})
    if resp.parsed_output is None:
        raise RuntimeError(f"step text stopped: {getattr(resp, 'stop_reason', '?')}")
    return {s.n: s.model_dump() for s in resp.parsed_output.steps}


def _cap(s: str, n: int) -> str:
    s = re.sub(r"\s+", " ", (s or "").upper()).strip()
    return s if len(s) <= n else s[:n].rsplit(" ", 1)[0]


def build_card(*, article: str, name: str, pdf_url: str, product_url: str, root: Path, pdf: Optional[Path] = None,
               describe: Optional[Callable[..., dict]] = describe_steps) -> Optional[dict]:
    """A per-step card for this manual, or None when it has no recognisable numbered steps (the caller falls back)."""
    cid = f"ikea_{article}_steps"
    base = root / "knowledge" / "live" / "compiled_cards" / cid
    pdf = pdf or download(pdf_url, root / "knowledge" / "live" / "manuals" / f"{article}.pdf")
    pages = pdf_words(pdf)
    occ = occurrences(step_bands(pages))
    nums = sorted(occ)
    if len(nums) < 3 or nums[0] != 1:
        return None
    layouts = any(len(v) > 1 for k, v in occ.items() if k > 1)
    rendered: dict[int, object] = {}

    def page(n):
        if n not in rendered:
            rendered[n] = render_page(pdf, n, DPI)
        return rendered[n]

    crops, parts, views_of = {}, {}, {}
    for n in nums:
        b = occ[n][0]
        band, pb = _boxes(b)
        gid = f"{cid}_s{n:02}"
        views = []
        for view, box in (("where", band), ("how", pb)):
            if box is None:
                continue
            crop = crop_pt(page(b.page), DPI, box)
            path = base / "guides" / gid / f"{view}.png"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(png(g2_image(crop)))
            path.with_name(f"{view}.phone.png").write_bytes(png(phone_image(crop)))
            if view == "where":
                small = crop.copy()
                small.thumbnail((900, 700))
                crops[n] = png(small)
            views.append({"view": view, "step_id": f"s{n:02}.{view}", "title": "WHERE" if view == "where" else "PARTS",
                          "image": str(path.relative_to(root)), "phone_image": str(path.with_name(f"{view}.phone.png").relative_to(root)),
                          "provenance": "MANUFACTURER DOC", "depicts": f"Official manual drawing, step {n}, page {b.page}.",
                          "fallback": {"line1": "SEE THE MANUAL DRAWING", "line2": f"PAGE {b.page}"},
                          "reference_url": f"{pdf_url}#page={b.page}"})
        views_of[n] = (gid, views, b.page)
        parts[n] = printed_parts(b)
    texts: dict[int, dict] = {}
    if describe is not None:
        try:
            texts = describe(crops, name, parts)
        except Exception as exc:  # the official pictures and printed numbers still make a usable guide
            log.warning("step text unavailable: %s", exc)
    steps, guides = [], []
    for n in nums:
        gid, views, pg = views_of[n]
        t = texts.get(n) or {}
        printed = " ".join(f"{p['qty']}x {p['id']}" for p in parts[n] if p["qty"])
        line1 = _cap(t.get("line1", ""), 24) or f"STEP {n}: SEE PICTURE"
        line2 = _cap(t.get("line2", ""), 26) or _cap(printed, 26) or f"MANUAL PAGE {pg}"
        detail = (t.get("detail") or f"Do step {n} exactly as the manual drawing shows (page {pg}).").strip()
        if layouts:
            detail += " This manual shows two layouts; these pictures follow the first one."
        guides.append({"id": gid, "title": f"STEP {n}", "views": views})
        steps.append({
            "id": f"s{n:02}", "title": (t.get("title") or f"Step {n}")[:60], "cue": {"line1": line1, "line2": line2},
            "detail": detail[:600], "parts": [{"id": p["id"], "qty": p["qty"], "name": "", "note": None, "avoid": False} for p in parts[n]],
            "where": {"line1": "SEE THE PICTURE", "line2": f"MANUAL PAGE {pg}"}, "guide_id": gid,
            "cites": [{"source": "manual", "loc": f"Step {n}, page {pg}", "url": f"{pdf_url}#page={pg}"}],
        })
    card = {
        "v": 2, "card_id": cid, "title": f"{name} - assembly", "provenance": "MANUFACTURER DOC", "goal_mode": "build",
        "step_image": "where", "aliases": [name.lower()], "review": REVIEW,
        "sources": [{"id": "manual", "kind": "MANUFACTURER DOC", "title": f"IKEA {name} assembly instructions", "url": pdf_url},
                    {"id": "product", "kind": "MANUFACTURER DOC", "title": f"{name} {article}", "url": product_url}],
        "steps": steps, "guides": guides,
    }
    from contracts.models import Card

    Card.model_validate(card)
    (base / "card.json").write_text(json.dumps(card, indent=2, ensure_ascii=False))
    return card
