"""Apply a recorded review to a compiled card: rebuild a step picture without the AI highlight, swap in the menu-path
diagram, or drop a picture that does not match the card's exact model. Every change is appended to card.review."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from .compile import IMAGES_DIR, REPO_ROOT, _diagram_guide, StepWire
from .sources import SourceDoc


def _rebuild_whole(root: Path, guide_id: str, caption: str) -> dict:
    sys.path.insert(0, str(REPO_ROOT / "assets"))
    import build_guides as bg

    src = root / IMAGES_DIR / "src" / guide_id
    spec = json.loads((src / "annotations.json").read_text())
    for v in spec["views"]:
        v["crop"] = [0, 0, 1, 1]
        v["annotation"] = {"type": "rect", "x0": 0.01, "y0": 0.01, "x1": 0.99, "y1": 0.99}
        v["caption"] = caption[:22]
        v["depicts"] = v["depicts"].split(" Source picture from")[0].split(". ")[0] + ". Whole source picture, no highlight."
    (src / "annotations.json").write_text(json.dumps(spec, indent=2))
    manifest, _ = bg.build_guide(src, root / IMAGES_DIR / "guides", write=True)
    g = manifest["guide"]
    for v in g["views"]:
        for k in ("image", "phone_image"):
            v[k] = v[k].replace("knowledge/guides/", IMAGES_DIR + "/guides/", 1)
    return g


def apply(card_path: Path, actions: list[tuple[str, str, str]], note: str, root: Path = REPO_ROOT) -> dict:
    card = json.loads(card_path.read_text())
    steps = {s["id"]: s for s in card["steps"]}
    for step_id, action, arg in actions:
        st = steps[step_id]
        old = st.get("guide_id")
        if action == "drop":
            st["guide_id"] = None
        elif action == "whole":
            g = _rebuild_whole(root, old, arg)
            card["guides"] = [x for x in card["guides"] if x["id"] != old] + [g]
        elif action == "diagram":
            w = StepWire(id=st["id"], kind=st["kind"], title=st["title"], line1=st["cue"]["line1"], line2=st["cue"]["line2"], detail=st["detail"],
                         expected="", tools=[], risk=st["risk"], warnings=[], choices=[], next="", source=0, quote=st["cites"][0]["quote"], image=-1, expected_image=-1)
            doc = SourceDoc(url=st["cites"][0]["url"], title="", kind="MANUFACTURER DOC")
            g = _diagram_guide(root, card["card_id"], w, doc)
            if g:
                card["guides"] = [x for x in card["guides"] if x["id"] != old and x["id"] != g["id"]] + [g]
                st["guide_id"] = g["id"]
        if old and all(s.get("guide_id") != old for s in card["steps"]):
            card["guides"] = [x for x in card["guides"] if x["id"] != old]
    card["review"] = (card.get("review", "") + " " + note).strip()[:400]
    from contracts.models import Card

    Card.model_validate(card)
    card_path.write_text(json.dumps(card, indent=2, ensure_ascii=False) + "\n")
    return card
