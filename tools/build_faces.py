# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow>=10"]
# ///
"""Draw the small face pictures shown at the top right of a card.

A face combines ASL grammar and the sentence's emotion:
  brows: flat | down (what/where/who... questions) | up (yes/no questions, surprise)
  mouth: flat | smile | frown | open
  shake: 0 | 1 (left-right arrows: a "no" head shake)
Written as g2/public/faces/face_<brows>_<mouth>_<shake>.png, 64x64, bright
lines on black (lit on the lens), 16 grey levels; plus face_blank.png.

Run (from the repo root):  uv run tools/build_faces.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "g2" / "public" / "faces"
SIZE = 64
S = 4  # draw 4x larger, then shrink: smoother lines
W = 3 * S  # line width


def face(brows: str, mouth: str, shake: bool) -> Image.Image:
    big = SIZE * S
    img = Image.new("L", (big, big), 0)
    d = ImageDraw.Draw(img)
    cx = big // 2
    r = 22 * S
    d.ellipse([cx - r, cx - r, cx + r, cx + r], outline=255, width=W)  # head
    # eyes
    for ex in (cx - 8 * S, cx + 8 * S):
        d.ellipse([ex - 2 * S, cx - 4 * S, ex + 2 * S, cx], fill=255)
    # brows
    by = cx - 9 * S
    for side in (-1, 1):
        inner, outer = cx + side * 3 * S, cx + side * 13 * S
        if brows == "down":  # furrowed: inner ends low
            d.line([inner, by + 2 * S, outer, by - 3 * S], fill=255, width=W)
        elif brows == "up":  # raised and arched, clear of the head outline
            d.arc([min(inner, outer), by - 3 * S, max(inner, outer), by + 5 * S], 190, 350, fill=255, width=W)
        else:
            d.line([inner, by, outer, by], fill=255, width=W)
    # mouth
    my = cx + 9 * S
    if mouth == "smile":
        d.arc([cx - 9 * S, my - 8 * S, cx + 9 * S, my + 4 * S], 20, 160, fill=255, width=W)
    elif mouth == "frown":
        d.arc([cx - 8 * S, my - 1 * S, cx + 8 * S, my + 9 * S], 200, 340, fill=255, width=W)
    elif mouth == "open":
        d.ellipse([cx - 4 * S, my - 3 * S, cx + 4 * S, my + 5 * S], outline=255, width=W)
    else:
        d.line([cx - 7 * S, my, cx + 7 * S, my], fill=255, width=W)
    if shake:  # arrows either side of the head: shake it
        for side in (-1, 1):
            x0 = cx + side * (r + 3 * S)
            tip = x0 + side * 6 * S
            d.line([x0, cx, tip, cx], fill=255, width=W)
            d.line([tip, cx, tip - side * 3 * S, cx - 3 * S], fill=255, width=W)
            d.line([tip, cx, tip - side * 3 * S, cx + 3 * S], fill=255, width=W)
    small = img.resize((SIZE, SIZE), Image.LANCZOS)
    return small.point(lambda v: round(v / 17) * 17)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    n = 0
    for brows in ("flat", "down", "up"):
        for mouth in ("flat", "smile", "frown", "open"):
            for shake in (0, 1):
                face(brows, mouth, bool(shake)).save(OUT / f"face_{brows}_{mouth}_{shake}.png", optimize=True)
                n += 1
    Image.new("L", (SIZE, SIZE), 0).save(OUT / "face_blank.png", optimize=True)
    print(f"wrote {n + 1} faces to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
