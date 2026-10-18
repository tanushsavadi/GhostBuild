#!/usr/bin/env python3
"""Render the SCHEMATIC stand-in sources for the paper_cup guides (assets/sources/cup_fold_half, cup_pinch).

Generic flat drawings of a square sheet of paper seen as a diamond, and of the triangle it becomes after the first fold.
They follow ONLY the sentences of the cited tutorial (https://origami.me/cup/, steps 1 and 2) and show no photo, no
hands and no paper texture. The exact position of the step-2 pinch is NOT drawn. Replace them with real photos
(assets/README.md). Deterministic; run: uv run python assets/tools/make_standin_paper_cup.py
"""
from pathlib import Path

from PIL import Image, ImageDraw

W, H, S = 1600, 800, 2
ROOT = Path(__file__).resolve().parents[1] / "sources"
PAPER, EDGE, TABLE = (178, 184, 196), (235, 238, 245), (20, 24, 32)
CX, CY, HD = 800, 330, 250  # diamond centre and half-diagonal
TOP, RIGHT, BOTTOM, LEFT = (CX, CY - HD), (CX + HD, CY), (CX, CY + HD), (CX - HD, CY)


def canvas():
    img = Image.new("RGB", (W * S, H * S), TABLE)
    return img, ImageDraw.Draw(img)


def poly(d, pts, fill=PAPER, outline=EDGE, width=7):
    pts = [(x * S, y * S) for x, y in pts]
    d.polygon(pts, fill=fill)
    d.line(pts + [pts[0]], fill=outline, width=width * S, joint="curve")


def dashed(d, a, b, dash=22, gap=16, color=(40, 50, 70), width=6):
    (x0, y0), (x1, y1) = a, b
    length = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
    n = int(length // (dash + gap)) + 1
    for i in range(n):
        t0, t1 = i * (dash + gap) / length, min(1.0, (i * (dash + gap) + dash) / length)
        d.line([((x0 + (x1 - x0) * t0) * S, (y0 + (y1 - y0) * t0) * S), ((x0 + (x1 - x0) * t1) * S, (y0 + (y1 - y0) * t1) * S)],
               fill=color, width=width * S)


def save(img, folder, name):
    out = ROOT / folder
    out.mkdir(parents=True, exist_ok=True)
    img.resize((W, H), Image.LANCZOS).save(out / name)


def diamond(fold_line: bool):
    img, d = canvas()
    poly(d, [TOP, RIGHT, BOTTOM, LEFT])
    if fold_line:
        dashed(d, LEFT, RIGHT)
    return img


def triangle():
    img, d = canvas()
    poly(d, [TOP, RIGHT, LEFT])
    return img


if __name__ == "__main__":
    save(diamond(False), "cup_fold_half", "where.src.png")
    save(diamond(True), "cup_fold_half", "how.src.png")
    save(triangle(), "cup_fold_half", "correct.src.png")
    save(triangle(), "cup_pinch", "where.src.png")
    save(triangle(), "cup_pinch", "how.src.png")
    print("wrote 5 schematic sources to", ROOT)
