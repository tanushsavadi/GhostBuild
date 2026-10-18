"""Source-to-action compiler: official pages -> a validated, cited, branching Card the existing runtime plays.

COLD PATH ONLY (build time, or one asynchronous research job). Never on navigation, pictures or answers.

    sources (knowledge/sources.py) -> Claude structured output (flat wire schema) -> verbatim-quote + graph validation
    -> one repair round if needed -> each step's own source picture cropped/highlighted (optional vision pass) and
    rendered by the shared guide builder -> contracts.models.Card -> cached card.json

Rules the validator enforces (not just the prompt): every step quotes its source verbatim; routes point at real steps;
pictures come only from the cited pages; nothing is labelled human-reviewed.

CLI:  python -m knowledge.compile --goal "..." --url URL [--url URL ...] --out knowledge/compiled/<id> [--review "..."]
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field

from .sources import SourceDoc, fetch, fetch_image, quote_in

log = logging.getLogger("ghostbuild.compile")
REPO_ROOT = Path(__file__).resolve().parents[1]
MODEL = os.environ.get("GB_COMPILE_MODEL", "claude-opus-5-5")
IMAGES_DIR = "knowledge/live/compiled"  # third-party pictures stay local (gitignored), never in the public repo
View = Literal["where", "how", "correct"]


# ---------------------------------------------------------------------------- wire schemas (flat, all required)
class ChoiceWire(BaseModel):
    id: str
    label: str = Field(description="ALL CAPS, at most 26 characters")
    say: list[str] = Field(description="2-5 lowercase phrases a person might say for this answer")
    next: str = Field(description="id of the step this answer leads to")
    records: str = Field(description="the observation this answer records, plain words")


class StepWire(BaseModel):
    id: str = Field(description="short snake_case id, unique")
    kind: Literal["action", "question", "outcome", "stop"]
    title: str = Field(description="at most 28 characters")
    line1: str = Field(description="glasses line 1: ALL CAPS, at most 24 characters, the action in plain words")
    line2: str = Field(description="glasses line 2: ALL CAPS, at most 26 characters, method or object")
    detail: str = Field(description="phone text: the full instruction from the source, at most 600 characters")
    expected: str = Field(description="how the person can tell it worked, from the source; empty if the source says nothing")
    tools: list[str]
    risk: Literal["low", "caution", "hazard"]
    warnings: list[str] = Field(description="safety notes from the source for this step")
    choices: list[ChoiceWire] = Field(description="question steps only: 2-4 answers; empty otherwise")
    next: str = Field(description="for an action step that must jump (end of a branch): the id to continue with; else empty")
    source: int = Field(description="index of the source this step comes from")
    quote: str = Field(description="a VERBATIM sentence or phrase (12+ characters) from that source supporting this step")
    image: int = Field(description="index of a picture from that same source that shows this step, or -1")
    expected_image: int = Field(description="index of a picture from that source showing the finished/correct state, or -1")


class GraphWire(BaseModel):
    title: str = Field(description="short task title, at most 28 characters (shown on the glasses)")
    task_kind: Literal["assembly", "diagnosis", "repair", "configuration", "identification"]
    goal_mode: Literal["build", "fix"]
    aliases: list[str] = Field(description="4-10 lowercase phrases people use for this task")
    uncovered: list[str] = Field(description="what the sources do not cover or leave uncertain")
    steps: list[StepWire]


class CropWire(BaseModel):
    crop: list[float] = Field(description="[x0,y0,x1,y1] fractions 0..1 of the region worth showing on a tiny monochrome display")
    highlight: list[float] = Field(description="[x0,y0,x1,y1] fractions 0..1 of the one thing to point at, inside crop")
    caption: str = Field(description="ALL CAPS, at most 22 characters, what the highlight marks")
    depicts: str = Field(description="one sentence: what the picture actually shows")
    usable: bool = Field(description="false if the picture does not show what the step describes")


SYSTEM = """You compile trusted documentation into a step-by-step guide for smart glasses (2 short lines per screen) and a phone.
You get numbered SOURCES (text blocks) and numbered PICTURES per source. Use ONLY what the sources say.
- Every step carries `source` and a VERBATIM `quote` copied exactly from that source's text (12+ characters). No quote, no step.
- Never invent screw locations, part numbers, connector orientations, settings names, values, compatibility or finished states.
- Diagnosis: start with the ONE question whose answer changes the path (kind=question, 2-4 choices, each `next` an existing step id).
  Order safe, non-destructive checks first. End each branch with kind=outcome (what to do if solved / what it suggests, without
  claiming a cause) or kind=stop (stop safely / contact the manufacturer or a professional, when the source says so or the next
  action would be risky). An action that ends a branch sets `next` to jump; otherwise the following step in the list follows.
- Repair/assembly: mostly sequential; use a question only where the source branches (configurations, variants, "if X, then Y").
  If the person might not know the answer (e.g. a part type), add a choice like "NOT SURE" that leads to the source's own way to tell.
- risk=hazard for steps the source warns can injure or damage (heat, mains power, batteries, sharp tools, data loss); caution for minor risk.
- line1/line2: everyday words a first-timer understands, keep quantities and units. Exact names go in detail.
- expected: what the source says the correct result looks/sounds/feels like. Pick pictures only from the step's own source.
- Keep 5-14 steps. List in `uncovered` what is missing or uncertain."""


def _client():
    import anthropic

    return anthropic.Anthropic(timeout=180, max_retries=1)


def _render_sources(docs: list[SourceDoc]) -> str:
    out = []
    for si, d in enumerate(docs):
        out.append(f"=== SOURCE {si}: {d.title} | {d.url} | {d.kind}")
        out += [f"[{si}.{b.i}] {b.text}" for b in d.blocks if len(b.text) > 25 or b.kind == "h"]
        if d.images:
            out.append(f"--- PICTURES of source {si} (index: alt text | text just before it)")
            out += [f"(pic {img.i}) {img.alt or '-'} | {img.near[:140]}" for img in d.images]
    return "\n".join(out)


def _ask(client, system: str, user: str, model_cls, max_tokens=16000):
    resp = client.messages.parse(model=MODEL, max_tokens=max_tokens, system=system, messages=[{"role": "user", "content": user}],
                                 output_format=model_cls, output_config={"effort": "medium"})
    if getattr(resp, "stop_reason", "") in ("refusal", "max_tokens") or resp.parsed_output is None:
        raise RuntimeError(f"compile model stopped: {getattr(resp, 'stop_reason', '?')}")
    return resp.parsed_output, resp.usage


def validate_graph(g: GraphWire, docs: list[SourceDoc]) -> list[str]:
    errs, ids = [], [s.id for s in g.steps]
    if len(ids) != len(set(ids)):
        errs.append("step ids must be unique")
    if len(g.steps) < 3:
        errs.append("fewer than 3 steps")
    if len(g.title) > 28:
        errs.append("title longer than 28 characters")
    known = set(ids)
    for s in g.steps:
        if not 0 <= s.source < len(docs):
            errs.append(f"{s.id}: source {s.source} does not exist")
            continue
        if not quote_in(s.quote, docs[s.source]):
            errs.append(f"{s.id}: quote is not verbatim in source {s.source}: {s.quote[:80]!r}")
        for pic in (s.image, s.expected_image):
            if pic != -1 and not 0 <= pic < len(docs[s.source].images):
                errs.append(f"{s.id}: picture {pic} is not in source {s.source}")
        if len(s.line1) > 24 or len(s.line2) > 26 or len(s.title) > 28 or any(len(c.label) > 26 for c in s.choices):
            errs.append(f"{s.id}: glasses text too long (line1<=24, line2<=26, title<=28, choice labels<=26 characters); rewrite shorter, whole words")
        if s.kind == "question" and not 2 <= len(s.choices) <= 4:
            errs.append(f"{s.id}: a question needs 2-4 choices")
        for t in [c.next for c in s.choices] + ([s.next] if s.next else []):
            if t not in known:
                errs.append(f"{s.id}: route to unknown step {t!r}")
    return errs


def compile_graph(goal: str, docs: list[SourceDoc], *, context: str = "", client=None) -> tuple[GraphWire, dict]:
    client = client or _client()
    user = f"TASK: {goal}\n" + (f"WHAT THE PERSON ALREADY SAID (respect it; skip questions it answers): {context}\n" if context else "") + "\n" + _render_sources(docs)
    t0 = time.monotonic()
    g, usage = _ask(client, SYSTEM, user, GraphWire)
    errs, rounds = validate_graph(g, docs), 1
    if errs:  # one repair round: the model sees exactly what failed
        g, usage = _ask(client, SYSTEM, user + "\n\nYOUR PREVIOUS GUIDE FAILED VALIDATION. Fix exactly these problems, keep everything else:\n- " + "\n- ".join(errs[:30]) + "\n\nPREVIOUS GUIDE:\n" + g.model_dump_json(), GraphWire)
        errs, rounds = validate_graph(g, docs), 2
    stats = {"compile_s": round(time.monotonic() - t0, 2), "rounds": rounds, "errors": errs, "model": MODEL,
             "output_tokens": getattr(usage, "output_tokens", None)}
    if errs:
        # Unverifiable steps are dropped only when the route stays intact; otherwise the whole guide is refused.
        bad = {e.split(":")[0] for e in errs if "quote is not verbatim" in e}
        refs = {c.next for s in g.steps for c in s.choices} | {s.next for s in g.steps if s.next}
        if bad and not (bad & refs) and all("quote is not verbatim" in e for e in errs) and len(g.steps) - len(bad) >= 3:
            g = g.model_copy(update={"steps": [s for s in g.steps if s.id not in bad]})
            stats["dropped_unverified_steps"] = sorted(bad)
            stats["errors"] = validate_graph(g, docs)
        if stats["errors"]:
            raise ValueError("compiled guide failed validation: " + "; ".join(stats["errors"][:6]))
    return g, stats


# ---------------------------------------------------------------------------- pictures
def _img_media(data: bytes) -> str:
    from PIL import Image

    fmt = (Image.open(io.BytesIO(data)).format or "PNG").lower()
    return {"jpeg": "image/jpeg", "jpg": "image/jpeg", "png": "image/png", "webp": "image/webp", "gif": "image/gif"}.get(fmt, "image/png")


def plan_crop(client, data: bytes, step: StepWire) -> Optional[CropWire]:
    """Vision pass (cold path): where in the source's own picture is the thing this step is about?"""
    from PIL import Image

    im = Image.open(io.BytesIO(data)).convert("RGB")
    im.thumbnail((1400, 1400))
    buf = io.BytesIO()
    im.save(buf, "PNG")
    content = [{"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": base64.standard_b64encode(buf.getvalue()).decode()}},
               {"type": "text", "text": f"Step: {step.title}. {step.detail}\nChoose the crop and the single highlight for a 288x144 monochrome display. Use only what is visible; if the picture does not show the step, set usable=false."}]
    try:
        resp = client.messages.parse(model=MODEL, max_tokens=2000, messages=[{"role": "user", "content": content}],
                                     output_format=CropWire, output_config={"effort": "low"})
        c = resp.parsed_output
    except Exception:
        log.exception("crop planning failed; using the whole picture")
        return None
    ok = c is not None and len(c.crop) == 4 and len(c.highlight) == 4 and all(0 <= v <= 1 for v in c.crop + c.highlight)
    return c if ok and c.crop[2] > c.crop[0] and c.crop[3] > c.crop[1] else None


def _guide_for(root: Path, card_id: str, s: StepWire, doc: SourceDoc, client, vision: bool) -> tuple[Optional[dict], list[str]]:
    sys.path.insert(0, str(REPO_ROOT / "assets"))
    import build_guides as bg  # the same renderer as `make guides` and the CREAO diagrams

    gid = re.sub(r"[^a-z0-9_]", "_", f"{card_id}_{s.id}".lower())[:60]
    src_dir = root / IMAGES_DIR / "src" / gid
    src_dir.mkdir(parents=True, exist_ok=True)
    views, notes = [], []
    for view, pic in (("where", s.image), ("correct", s.expected_image)):
        if pic == -1 or (view == "correct" and pic == s.image):
            continue
        img = doc.images[pic]
        try:
            data = fetch_image(img.src, root)
            from PIL import Image

            Image.open(io.BytesIO(data)).load()
        except Exception as e:
            notes.append(f"{s.id}: picture {pic} unavailable ({type(e).__name__})")
            continue
        name = f"{view}.src.{'png' if _img_media(data) == 'image/png' else 'jpg'}"
        (src_dir / name).write_bytes(data)
        # A question compares several things in one picture: show it whole rather than point at one answer.
        c = plan_crop(client, data, s) if vision and s.kind != "question" else None
        if c is not None and not c.usable:
            notes.append(f"{s.id}: vision check says picture {pic} does not show this step; not used")
            continue
        crop = c.crop if c else [0, 0, 1, 1]
        hl = c.highlight if c else [0.02, 0.02, 0.98, 0.98]
        # the highlight is drawn in source fractions; keep it inside the crop
        hl = [max(hl[0], crop[0]), max(hl[1], crop[1]), min(hl[2], crop[2]), min(hl[3], crop[3])]
        if hl[2] <= hl[0] or hl[3] <= hl[1]:
            hl = [crop[0] + 0.01, crop[1] + 0.01, crop[2] - 0.01, crop[3] - 0.01]
        caption = re.sub(r"[^A-Z0-9 .:/+-]", "", (c.caption if c else ("RESULT" if view == "correct" else "COMPARE WITH YOURS" if s.kind == "question" else s.line1)).upper())[:22]
        views.append({
            "view": view, "step_id": f"{gid}.{view}", "title": ("RESULT" if view == "correct" else s.title.upper())[:24], "source": name,
            "crop": crop, "annotation": {"type": "rect", "x0": hl[0], "y0": hl[1], "x1": hl[2], "y1": hl[3]}, "caption": caption,
            "provenance": doc.kind, "asset_kind": "photograph" if _img_media(data) == "image/jpeg" else "unspecified",
            "depicts": ((c.depicts + " ") if c else "") + f"Source picture from {doc.title} ({'cropped and highlighted by AI vision' if c else 'whole picture'}); a real reference, not your hardware.",
            "fallback_cue": {"line1": s.line1[:24], "line2": "PICTURE ON YOUR PHONE"},
            "reference_url": doc.url,
        })
    if not views:
        return None, notes
    (src_dir / "annotations.json").write_text(json.dumps({"guide_id": gid, "title": s.title[:60], "units": "frac", "views": views}, indent=2))
    out = root / IMAGES_DIR / "guides"
    manifest, _ = bg.build_guide(src_dir, out, write=True)
    guide = manifest["guide"]
    for v in guide["views"]:
        for k in ("image", "phone_image"):
            v[k] = v[k].replace("knowledge/guides/", IMAGES_DIR + "/guides/", 1)
    return guide, notes


def menu_path(text: str) -> list[str]:
    """'choose Apple menu > System Settings, then click Displays in the sidebar' -> [Apple menu, System Settings, Displays]."""
    m = re.search(r"([A-Z][\w’' -]{1,30}(?:\s*>\s*[A-Z][\w’'., -]{1,40})+)", text)
    if not m:
        return []
    parts = [p.strip(" .,") for p in re.split(r"\s*>\s*", m.group(1))]
    lead = re.split(r"(?i)\b(?:choose|click|select|open|in|from|the)\s+", parts[0])
    parts[0] = lead[-1].strip() or parts[0]
    parts[-1] = re.split(r",| then | and ", parts[-1])[0].strip(" .,")
    end = text.find(parts[-1], m.start()) + len(parts[-1])
    tail = text[end:]
    for c in re.findall(r"\b(?:[Cc]lick|[Cc]hoose|[Ss]elect) ([A-Z][\w’' ]{1,28}?)(?: in the sidebar| on the right| pop-up|[,.;]| then)", tail)[:2]:
        parts.append(c.strip())
    return [p for p in parts if p][:5]


def path_diagram(parts: list[str]) -> bytes:
    """A plain drawing of a settings path: boxes and arrows, the last box highlighted. Drawn by GhostBuild from the source's words."""
    from PIL import Image, ImageDraw, ImageFont

    W, H = 1152, 576
    im = Image.new("L", (W, H), 0)  # black = transparent on the glasses; only lines and words light up
    d = ImageDraw.Draw(im)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 46)
    except OSError:
        font = ImageFont.load_default()
    rows = [parts[i:i + 2] for i in range(0, len(parts), 2)]
    y = (H - len(rows) * 150) // 2 + 20
    for ri, row in enumerate(rows):
        x = 40
        for ci, label in enumerate(row):
            w = (W - 160) // 2
            last = ri == len(rows) - 1 and ci == len(row) - 1
            d.rounded_rectangle([x, y, x + w, y + 110], radius=22, outline=255, width=10 if last else 4, fill=70 if last else 0)
            label = f"{ri * 2 + ci + 1}. {label}"
            f = font
            for size in (46, 40, 34, 30):  # shrink to fit rather than cut the name the source gives
                try:
                    f = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", size)
                except OSError:
                    break
                if d.textlength(label, font=f) < w - 30:
                    break
            t = label if d.textlength(label, font=f) < w - 30 else label[:22] + "…"
            d.text((x + w / 2, y + 55), t, fill=255, font=f, anchor="mm")
            if not last and ci < len(row) - 1:
                ax = x + w + 8
                d.line([ax, y + 55, ax + 52, y + 55], fill=255, width=8)
                d.polygon([(ax + 64, y + 55), (ax + 44, y + 38), (ax + 44, y + 72)], fill=255)
            x += w + 80
        y += 150
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def _diagram_guide(root: Path, card_id: str, s: StepWire, doc: SourceDoc) -> Optional[dict]:
    parts = menu_path(s.detail) or menu_path(s.quote)
    if len(parts) < 2:
        return None
    sys.path.insert(0, str(REPO_ROOT / "assets"))
    import build_guides as bg

    gid = re.sub(r"[^a-z0-9_]", "_", f"{card_id}_{s.id}".lower())[:60]
    src_dir = root / IMAGES_DIR / "src" / gid
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "where.src.png").write_bytes(path_diagram(parts))
    view = {"view": "where", "step_id": f"{gid}.where", "title": "WHERE TO CLICK", "source": "where.src.png", "crop": [0, 0, 1, 1],
            "annotation": {"type": "rect", "x0": 0.005, "y0": 0.005, "x1": 0.995, "y1": 0.995}, "caption": "", "autocontrast": 0,
            "provenance": "DETERMINISTIC", "asset_kind": "original_diagram",
            "depicts": "GhostBuild drawing of the path the source names (" + " > ".join(parts) + "). Not a screenshot.",
            "fallback_cue": {"line1": " > ".join(parts[-2:]).upper()[:24], "line2": "PATH ON YOUR PHONE"}, "reference_url": doc.url}
    (src_dir / "annotations.json").write_text(json.dumps({"guide_id": gid, "title": s.title[:60], "units": "frac", "views": [view]}, indent=2))
    manifest, _ = bg.build_guide(src_dir, root / IMAGES_DIR / "guides", write=True)
    guide = manifest["guide"]
    for v in guide["views"]:
        for k in ("image", "phone_image"):
            v[k] = v[k].replace("knowledge/guides/", IMAGES_DIR + "/guides/", 1)
    return guide


# ---------------------------------------------------------------------------- card
def _cue(a: str, b: str) -> dict:
    return {"line1": " ".join(a.upper().split())[:24], "line2": " ".join(b.upper().split())[:26]}


def to_card(g: GraphWire, docs: list[SourceDoc], *, root: Path, card_id: str, review: str = "", vision: bool = True, client=None) -> tuple[dict, list[str]]:
    client = client or _client()
    used = sorted({s.source for s in g.steps})
    src_ids = {si: f"src{si}" for si in used}
    steps, guides, notes = [], [], []
    for s in g.steps:
        doc = docs[s.source]
        software_path = s.kind == "action" and len(menu_path(s.detail) or menu_path(s.quote)) >= 3
        guide, n = _guide_for(root, card_id, s, doc, client, vision) if (s.image != -1 or s.expected_image != -1) and not software_path else (None, [])
        notes += n
        if guide is None and s.kind == "action":
            guide = _diagram_guide(root, card_id, s, doc)  # no source picture: a plain drawing of the path the source names
        if guide:
            guides.append(guide)
        steps.append({
            "id": s.id, "title": s.title[:28], "cue": _cue(s.line1, s.line2), "detail": s.detail[:600],
            "warnings": [w[:300] for w in s.warnings][:4], "kind": s.kind, "next": s.next or None, "expected": s.expected[:300],
            "tools": s.tools[:8], "risk": s.risk, "guide_id": guide["id"] if guide else None,
            "choices": [{"id": re.sub(r"[^a-z0-9_]", "_", c.id.lower())[:40] or f"c{i}", "label": " ".join(c.label.upper().split())[:26],
                         "say": [x.lower()[:60] for x in c.say][:6], "next": c.next, "records": c.records[:160]} for i, c in enumerate(s.choices)],
            "cites": [{"source": src_ids[s.source], "loc": "quoted passage", "quote": s.quote[:300], "url": doc.url}],
        })
    order = ["MANUFACTURER DOC", "WEB TUTORIAL"]
    kinds = {docs[i].kind for i in used}
    card = {
        "v": 2, "card_id": card_id, "title": g.title[:60], "provenance": next((k for k in order if k in kinds), "WEB TUTORIAL"),
        "sources": [{"id": src_ids[i], "kind": docs[i].kind, "title": docs[i].title[:120], "url": docs[i].url} for i in used],
        "steps": steps, "guides": guides, "goal_mode": g.goal_mode, "step_image": "where" if guides else None,
        "aliases": sorted({a.lower().strip()[:60] for a in g.aliases if a.strip()})[:12], "task_kind": g.task_kind,
        "review": (review or "AI-compiled from the cited pages; every step's quote checked verbatim by code; not human-reviewed.")[:400],
    }
    from contracts.models import Card

    Card.model_validate(card)  # the same contract every card meets
    return card, notes + [f"uncovered: {u}" for u in g.uncovered]


def compile_task(goal: str, urls: list[str], *, root: Path = REPO_ROOT, card_id: Optional[str] = None, context: str = "",
                 review: str = "", vision: bool = True) -> tuple[dict, dict]:
    t0 = time.monotonic()
    docs = [fetch(u, root) for u in urls]
    fetch_s = round(time.monotonic() - t0, 2)
    client = _client()
    g, stats = compile_graph(goal, docs, context=context, client=client)
    cid = card_id or (re.sub(r"[^a-z0-9]+", "_", g.title.lower()).strip("_")[:40] + "_" + hashlib.sha1((goal + "|".join(urls)).encode()).hexdigest()[:4])
    t1 = time.monotonic()
    card, notes = to_card(g, docs, root=root, card_id=cid, review=review, vision=vision, client=client)
    stats.update(fetch_s=fetch_s, images_s=round(time.monotonic() - t1, 2), total_s=round(time.monotonic() - t0, 2), notes=notes,
                 sources=[{"url": d.url, "title": d.title, "kind": d.kind, "blocks": len(d.blocks), "pictures": len(d.images)} for d in docs])
    return card, stats


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--goal", required=True)
    ap.add_argument("--url", action="append", required=True)
    ap.add_argument("--out", required=True, help="directory for card.json and compile.json")
    ap.add_argument("--card-id")
    ap.add_argument("--review", default="")
    ap.add_argument("--context", default="")
    ap.add_argument("--no-vision", action="store_true")
    a = ap.parse_args(argv)
    logging.basicConfig(level="INFO")
    try:
        from dotenv import load_dotenv

        load_dotenv(REPO_ROOT / ".env", override=False)
    except ImportError:
        pass
    card, stats = compile_task(a.goal, a.url, card_id=a.card_id, review=a.review, context=a.context, vision=not a.no_vision)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "card.json").write_text(json.dumps(card, indent=2, ensure_ascii=False) + "\n")
    (out / "compile.json").write_text(json.dumps(stats, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k: stats[k] for k in ("total_s", "compile_s", "images_s", "rounds", "errors")}, indent=1))
    print(f"{card['card_id']}: {len(card['steps'])} steps, {len(card['guides'])} pictures -> {out / 'card.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
