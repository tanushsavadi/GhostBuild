# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow>=10"]
# ///
"""Draw the Even Hub store icon: an open palm, greyscale only (colour is rejected).

Writes g2/store/icon_foreground.png (white palm on transparent), icon_background.png
(plain dark grey) and icon_preview.png (both combined), all 512x512. These are
uploaded in the Even Hub portal; they are not part of the .ehpk.

Run (from the repo root):  uv run tools/build_store_assets.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "g2" / "store"
S = 512
K = 4  # draw 4x, then shrink for smooth edges
WHITE, BG = 235, 38


def palm() -> Image.Image:
    big = S * K
    img = Image.new("LA", (big, big), (0, 0))
    d = ImageDraw.Draw(img)
    u = big / 512  # one unit = one pixel of the final icon
    w = int(16 * u)

    def rr(x0, y0, x1, y1, r):
        d.rounded_rectangle([x0 * u, y0 * u, x1 * u, y1 * u], radius=r * u, outline=(WHITE, 255), width=w)

    # palm, then four fingers standing on it (open palm facing out)
    rr(150, 250, 362, 430, 70)
    for x, top in ((158, 112), (208, 84), (258, 92), (308, 128)):
        rr(x, top, x + 46, 280, 23)
    # thumb, angled out to the side
    thumb = Image.new("LA", (big, big), (0, 0))
    td = ImageDraw.Draw(thumb)
    # drawn upright with its base inside the palm's left edge, then tilted out
    td.rounded_rectangle([140 * u, 216 * u, 188 * u, 372 * u], radius=24 * u, outline=(WHITE, 255), width=w)
    thumb = thumb.rotate(38, center=(170 * u, 372 * u))
    img.alpha_composite(thumb) if img.mode == "RGBA" else img.paste(thumb, (0, 0), thumb)
    # the palm outline hides the lower finger ends: clear their insides
    d.rounded_rectangle([166 * u, 266 * u, 346 * u, 414 * u], radius=54 * u, fill=(0, 0))
    return img.resize((S, S), Image.LANCZOS)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    fg = palm()
    fg.save(OUT / "icon_foreground.png")
    bg = Image.new("L", (S, S), BG)
    bg.save(OUT / "icon_background.png")
    preview = bg.convert("LA")
    preview.paste(fg, (0, 0), fg)
    preview.convert("L").save(OUT / "icon_preview.png")
    print(f"wrote icon_foreground.png, icon_background.png, icon_preview.png to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
