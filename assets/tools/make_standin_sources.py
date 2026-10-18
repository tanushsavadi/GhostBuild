#!/usr/bin/env python3
"""Render the SCHEMATIC stand-in sources for guide `camera_lens` (assets/sources/camera_lens/*.src.png).

These are generic cartoon-style schematics of "a small camera module on a stand with a removable cover".
They are NOT a photo of the team's rig and show NO connectors, pins or board features of any real product.
Replace them with real photos (assets/README.md). Deterministic; run: uv run python assets/tools/make_standin_sources.py
"""
from pathlib import Path

from PIL import Image, ImageDraw

W, H, S = 1600, 800, 2  # final size, supersample factor
OUT = Path(__file__).resolve().parents[1] / "sources" / "camera_lens"
LENS = (800, 295)


def rr(d, box, r, fill, outline=None, width=0):
    d.rounded_rectangle([c * S for c in box], r * S, fill=fill, outline=outline, width=width * S)


def circ(d, c, r, fill, outline=None, width=0):
    d.ellipse([(c[0] - r) * S, (c[1] - r) * S, (c[0] + r) * S, (c[1] + r) * S], fill=fill, outline=outline, width=width * S)


def scene(cover: bool, inset: bool) -> Image.Image:
    img = Image.new("RGB", (W * S, H * S), (18, 22, 30))
    d = ImageDraw.Draw(img)
    for y in range(H):  # soft wall gradient
        t = y / H
        d.rectangle([0, y * S, W * S, (y + 1) * S], fill=(int(16 + 14 * t), int(20 + 14 * t), int(28 + 14 * t)))
    d.rectangle([0, 650 * S, W * S, H * S], fill=(44, 50, 60))  # table
    d.rectangle([0, 650 * S, W * S, 662 * S], fill=(70, 76, 88))
    rr(d, (560, 598, 1040, 652), 14, (96, 104, 116))  # stand base
    rr(d, (766, 400, 834, 610), 10, (110, 118, 130))  # stand post
    rr(d, (640, 170, 960, 420), 26, (150, 162, 180), (225, 232, 240), 8)  # generic module body
    circ(d, LENS, 98, (28, 36, 48))  # lens barrel
    circ(d, LENS, 70, (86, 102, 124))
    circ(d, LENS, 44, (10, 12, 18))
    circ(d, (LENS[0] - 14, LENS[1] - 16), 10, (235, 240, 250))  # glint
    if cover:  # removable cover cap with a pull tab
        rr(d, (690, 188, 910, 402), 36, (236, 200, 110), (255, 245, 210), 8)
        rr(d, (890, 275, 1000, 315), 16, (236, 200, 110), (255, 245, 210), 8)
    if inset:  # what the camera now sees: a bright generic scene (no markers)
        rr(d, (1060, 110, 1340, 330), 18, (250, 250, 250), (250, 250, 250), 8)
        d.rectangle([1070 * S, 120 * S, 1330 * S, 320 * S], fill=(214, 232, 250))
        d.polygon([(1070 * S, 320 * S), (1150 * S, 230 * S), (1230 * S, 290 * S), (1290 * S, 215 * S), (1330 * S, 260 * S), (1330 * S, 320 * S)], fill=(92, 110, 96))
        circ(d, (1270, 165), 24, (255, 250, 210))
        for p0, p1 in (((900, 262), (1060, 150)), ((900, 328), (1060, 290))):
            d.line([(p0[0] * S, p0[1] * S), (p1[0] * S, p1[1] * S)], fill=(200, 210, 225), width=5 * S)
    return img.resize((W, H), Image.LANCZOS)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    scene(False, False).save(OUT / "where.src.png")
    scene(True, False).save(OUT / "how.src.png")
    scene(False, True).save(OUT / "correct.src.png")
    print("wrote 3 schematic sources to", OUT)
