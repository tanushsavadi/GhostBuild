"""Build the two offline MICKE cards and source crops. No generated diagrams or live models."""

from __future__ import annotations
import argparse
import copy
import hashlib
import json
from datetime import date
from pathlib import Path
import tempfile
import urllib.request
from urllib.parse import urlparse
from integrations.ikea.manual import (
    pdf_words,
    step_bands,
    occurrences,
    render_page,
    crop_pt,
    parts_box,
    g2_image,
    phone_image,
    png,
)
from knowledge.validate import validate_cards

ARTICLE = "80213074"
PDF_URL = "https://www.ikea.com/us/en/assembly_instructions/micke-desk-white__AA-476615-12-100.pdf"
PRODUCT_URL = "https://www.ikea.com/us/en/p/micke-desk-white-80213074/"
# Step 31's rotated digits are 10 / 93 / 38; checked against the actual p22 drawing.
# Step 32 reuses those hinges, it does not print their number again.
REUSED = {(32, "109338"): 31}


def printed_id(pid, words):
    """Rejoin adjacent rotated numeric fragments, never arbitrary digits across a page."""
    nums = [w for w in words if w.text.isdigit() and 1 <= len(w.text) <= len(pid)]
    if any(w.text == pid for w in nums):
        return True

    def walk(prefix, last, used):
        if prefix == pid:
            return True
        for i, w in enumerate(nums):
            if i in used or not pid.startswith(prefix + w.text):
                continue
            if last is not None and (
                abs(w.x0 - last.x0) > 28 or abs(w.y0 - last.y0) > 28
            ):
                continue
            if walk(prefix + w.text, w, used | {i}):
                return True
        return False

    return walk("", None, set())


def cross_check(steps, pages, occ, side):
    errors = []
    for st in steps:
        n = st["n"]
        b = occ[n][-1 if side == "right" and n >= 9 else 0]
        for p in st["parts"]:
            pn = occ[REUSED.get((n, p["id"]), n)][
                -1 if side == "right" and n >= 9 else 0
            ].page
            if not printed_id(p["id"], pages[pn]):
                errors.append(f"{side} step {n} page {pn}: part {p['id']} not printed")
            if p.get("qty") and str(p["qty"]) + "x" not in [w.text for w in b.qty]:
                errors.append(f"{side} step {n}: quantity {p['qty']} not printed")
    if errors:
        raise ValueError("\n".join(errors))


def build(pdf: Path, root: Path):
    base = root / "knowledge/products/ikea" / ARTICLE
    steps = json.loads((base / "steps.json").read_text())["steps"]
    pages = pdf_words(pdf)
    occ = occurrences(step_bands(pages))
    assert set(occ) == set(range(1, 36)) and len(pages) == 40
    rendered = {}

    def page(n):
        if n not in rendered:
            rendered[n] = render_page(pdf, n, 150)
        return rendered[n]

    def asset(path, crop):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(png(g2_image(crop)))
        path.with_name(path.stem + ".phone.png").write_bytes(png(phone_image(crop)))

    for side, box in [("left", (37, 36, 290, 198)), ("right", (305, 36, 558, 198))]:
        asset(base / f"config_{side}.png", crop_pt(page(10), 150, box))
    mapping = {}
    for side in ("left", "right"):
        authored = copy.deepcopy(steps)
        # The two configurations genuinely have different printed finishing quantities.
        if side == "right":
            st = authored[34]
            st["parts"][0]["qty"] = 2
            st["parts"][1]["qty"] = 2
            st["cue"][0] = "FIT GROMMETS + 2 COVERS"
            st["title"] = "Fit grommets and covers"
            st["detail"] = (
                "Fit two cable grommets and two round covers as the configuration B diagram shows. Alternate part numbers are printed beside the diagram."
            )
        # These tools are pictured, but no quantity is printed for them at this step.
        for p in authored[23]["parts"]:
            if p["id"] in ("100092", "121030"):
                p["qty"] = None
                p["note"] = "tool shown; quantity not printed for this step"
        cross_check(authored, pages, occ, side)
        card = {
            "v": 2,
            "card_id": f"ikea_{ARTICLE}_cabinet_{side}",
            "title": f"MICKE - cabinet {side}",
            "provenance": "MANUFACTURER DOC",
            "goal_mode": "build",
            "step_image": "where",
            "aliases": [],
            "sources": [
                {
                    "id": "manual",
                    "kind": "MANUFACTURER DOC",
                    "title": "IKEA MICKE AA-476615-12",
                    "url": PDF_URL,
                },
                {
                    "id": "product",
                    "kind": "MANUFACTURER DOC",
                    "title": "MICKE 802.130.74",
                    "url": PRODUCT_URL,
                },
            ],
            "steps": [],
            "guides": [],
        }
        mapping[side] = {}
        for st in authored:
            n = st["n"]
            b = occ[n][-1 if side == "right" and n >= 9 else 0]
            gid = f"ikea{ARTICLE}_" + (f"{side}_" if n >= 9 else "") + f"s{n:02}"
            ref = f"{PDF_URL}#page={b.page}"
            band_box = (23, max(20, b.y0 - 4), 580, min(795, b.y1 + 8))
            pb = parts_box(b, margin=90)
            if pb:
                # Include the closeup circles and their arrows, not only the part digits.
                x0, y0, x1, y1 = pb
                cx = (x0 + x1) / 2
                cy = (y0 + y1) / 2
                pb = (
                    max(15, min(x0, cx - 120)),
                    max(b.y0, min(y0, cy - 80)),
                    min(580, max(x1, cx + 120)),
                    min(b.y1, max(y1, cy + 80)),
                )
            # Rectangles reviewed against this manual's actual diagrams. Keep
            # neighbouring steps and panel fragments out of the fastener closeups.
            if n == 1:
                band_box = (23, 20, 580, 475)
                pb = (25, 180, 225, 435)
            elif n == 14:
                pb = (180, 420, 580, 575) if side == "left" else (320, 500, 580, 735)
            elif n == 24:
                pb = (270, 20, 575, 300) if side == "left" else (25, 20, 330, 300)
            crops = {
                "where": crop_pt(page(b.page), 150, band_box),
                "how": crop_pt(page(b.page), 150, pb or band_box),
            }
            if n == 32:
                crops["correct"] = crop_pt(page(40), 150, (25, 25, 575, 790))
            views = []
            for view, crop in crops.items():
                path = base / "guides" / gid / f"{view}.png"
                asset(path, crop)
                views.append(
                    {
                        "view": view,
                        "step_id": f"s{n:02}.{view}",
                        "title": {
                            "where": "WHERE",
                            "how": "PARTS",
                            "correct": "ADJUST",
                        }[view],
                        "image": str(path.relative_to(root)),
                        "phone_image": str(
                            path.with_name(view + ".phone.png").relative_to(root)
                        ),
                        "provenance": "MANUFACTURER DOC",
                        "depicts": f"Official manual diagram, step {n}, cabinet {side}, page {40 if view == 'correct' else b.page}. Authored text needs human spot-check.",
                        "fallback": {
                            "line1": "SEE THE MANUAL DIAGRAM",
                            "line2": f"PAGE {40 if view == 'correct' else b.page}",
                        },
                        "reference_url": f"{PDF_URL}#page={40 if view == 'correct' else b.page}",
                    }
                )
            card["guides"].append({"id": gid, "title": f"STEP {n}", "views": views})
            card["steps"].append(
                {
                    "id": f"s{n:02}",
                    "title": st["title"],
                    "cue": dict(zip(("line1", "line2"), st["cue"])),
                    "instruction": json.loads((base / "instruction_copy.json").read_text())["steps"][str(n)],
                    "detail": st["detail"],
                    "parts": st["parts"],
                    "warnings": st["warnings"],
                    "where": {
                        "line1": "SEE THE PICTURE",
                        "line2": f"MANUAL PAGE {b.page}",
                    },
                    "guide_id": gid,
                    "cites": [
                        {
                            "source": "manual",
                            "loc": f"Step {n}, page {b.page}",
                            "url": ref,
                        }
                    ],
                }
            )
            mapping[side][str(n)] = {
                "page": b.page,
                "band": band_box,
                "parts": pb,
                "guide_id": gid,
            }
        out = base / "cards" / f"{card['card_id']}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(card, indent=2) + "\n")
    bundle = {
        "v": 1,
        "source": "ikea",
        "article": ARTICLE,
        "name": "MICKE",
        "manual_url": PDF_URL,
        "manual_title": "IKEA MICKE assembly instructions AA-476615-12",
        "config_question": {
            "id": "cabinet_side",
            "prompt": "Which side should the cabinet be on?",
            "short_prompt": "CABINET SIDE?",
            "help": "As seen from the sitter's side. Match the manual pictures below.",
            "options": [
                {
                    "id": s,
                    "label": f"CABINET ON THE {s.upper()}",
                    "image": f"/discovery/assets/ikea/{ARTICLE}/config_{s}.phone.png",
                }
                for s in ("left", "right")
            ],
        },
        "cards": {
            s: f"cards/ikea_{ARTICLE}_cabinet_{s}.json" for s in ("left", "right")
        },
        "evidence": [
            "has a drawer",
            "has a cabinet with a door",
            "has two shelves",
            "has a cable grommet",
        ],
        "built_from": {
            "pdf_sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
            "pages": 40,
            "generated": str(date.today()),
            "authored_text_review": "PENDING HUMAN SPOT-CHECK",
            "mapping": mapping,
        },
    }
    errors = validate_cards(base / "cards", root=root, check_images=True)
    if errors:
        raise ValueError("\n".join(errors))
    (base / "bundle.json").write_text(json.dumps(bundle, indent=2) + "\n")
    return bundle


def cached_pdf(path=None):
    path = (
        path
        or Path(tempfile.gettempdir())
        / "ghostbuild-manuals"
        / "micke-AA-476615-12-100.pdf"
    )
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        request = urllib.request.Request(
            PDF_URL, headers={"User-Agent": "GhostBuild/1.0 manual builder"}
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            if urlparse(response.geturl()).hostname not in ("www.ikea.com", "ikea.com"):
                raise ValueError("Manual redirected outside the official site")
            data = response.read(8_000_001)
            if len(data) > 8_000_000 or not data.startswith(b"%PDF"):
                raise ValueError("Official manual is not a bounded PDF")
        temporary = path.with_suffix(".tmp")
        temporary.write_bytes(data)
        temporary.replace(path)
    return path


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", type=Path)
    ap.add_argument("--root", type=Path, default=Path.cwd())
    a = ap.parse_args()
    b = build(cached_pdf(a.pdf), a.root.resolve())
    print(
        "Built",
        len(b["cards"]),
        "cards, 35 steps each; part ids/printed quantities cross-checked",
    )
