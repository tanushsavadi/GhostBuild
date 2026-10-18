# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow>=10"]
# ///
"""Convert ASL-LEX handshape drawings into G2-ready 4-bit PNGs.

Source: the handshape images used by the ASL-LEX 2.0 visualization
(asl-lex.org, CC BY-NC 4.0), served from aslcdi.website. Each is a 200x200
black line drawing on white.

The G2 lights bright pixels green and shows black as transparent, so each
drawing is inverted (lines bright), optionally thickened so thin strokes
survive downscaling, resized, and quantised to 16 grey levels.

Variants (all 144x144, the image container size the cards use):
  thin  - inverted and resized only
  bold  - strokes thickened before resizing
  bold96 - bold, drawn at 96 px and centred in 144x144

Run (from the repo root):  uv run tools/build_handshapes.py [ids...]
Default ids: the 7 demo-sign handshapes plus the fingerspelling letters that
have a drawing. Use --all for all 58. Also writes blank.png.
Raw downloads are cached in tmp/handshapes_raw/ (git-ignored).
"""

from __future__ import annotations

import argparse
import sys
import urllib.request
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps

BASE_URL = "https://aslcdi.website/images/handshape_images"
DEMO_IDS = ["closed_b", "open_b", "1", "h", "a", "flat_h", "s"]
# Fingerspelling: the letters whose shape ASL-LEX has a drawing for (see g2/src/deck.json).
LETTER_IDS = ["c", "d", "e", "f", "g", "i", "k", "l", "o", "p", "r", "t", "v", "w", "y", "curved_1"]
ALL_IDS = (
    "1 3 4 5 7 8 a baby_o bent_1 bent_l bent_v c closed_b closed_e curved_1 curved_4 curved_5 curved_h curved_l "
    "curved_v d e f flat_1 flat_4 flat_b flat_h flat_horns flat_ily flat_m flat_n flat_o flat_v flatspread_5 g "
    "goody_goody h horns i ily k l o open_8 open_b open_e open_f open_h p r s spread_e spread_open_e stacked_5 t "
    "v w y"
).split()
SIZE = 144

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "tmp" / "handshapes_raw"
OUT_DIR = ROOT / "g2" / "public" / "handshapes"


def fetch(hid: str) -> Path:
    path = RAW_DIR / f"{hid}.png"
    if not path.exists():
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(f"{BASE_URL}/{hid}.png", timeout=20) as res:
            path.write_bytes(res.read())
    return path


def fetch_letter(letter: str) -> Image.Image:
    """M and N have no ASL-LEX drawing; use the public-domain wpclipart
    line drawings from Wikimedia Commons, padded square to match."""
    path = RAW_DIR / f"letter_{letter}.png"
    if not path.exists():
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        url = f"https://commons.wikimedia.org/wiki/Special:FilePath/Sign_language_{letter.upper()}.svg?width=400"
        req = urllib.request.Request(url, headers={"User-Agent": "sign-coach-build/0.1"})
        with urllib.request.urlopen(req, timeout=20) as res:
            path.write_bytes(res.read())
    rgba = Image.open(path).convert("RGBA")
    flat = Image.new("RGBA", rgba.size, "white")
    flat.alpha_composite(rgba)
    grey = flat.convert("L")
    side = max(grey.size)
    square = Image.new("L", (side, side), 255)
    square.paste(grey, ((side - grey.width) // 2, (side - grey.height) // 2))
    return square.resize((200, 200), Image.LANCZOS)  # black lines on white, like ASL-LEX


def quantise(img: Image.Image) -> Image.Image:
    # 16 levels: 0, 17, 34, ... 255, matching the lens's 4-bit greys.
    return img.point(lambda v: round(v / 17) * 17)


def render(raw: Image.Image, bold: bool, draw_size: int) -> Image.Image:
    lit = ImageOps.invert(raw.convert("L"))
    if bold:
        lit = lit.filter(ImageFilter.MaxFilter(5))
    lit = ImageOps.autocontrast(lit.resize((draw_size, draw_size), Image.LANCZOS))
    canvas = Image.new("L", (SIZE, SIZE), 0)
    offset = (SIZE - draw_size) // 2
    canvas.paste(lit, (offset, offset))
    return quantise(canvas)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ids", nargs="*", help="handshape ids (default: the 7 demo handshapes)")
    ap.add_argument("--all", action="store_true", help="convert all 58 handshapes")
    args = ap.parse_args()

    ids = ALL_IDS if args.all else (args.ids or DEMO_IDS + LETTER_IDS)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # Cards without a drawing (e.g. M, N) clear the image container with this.
    Image.new("L", (SIZE, SIZE), 0).save(OUT_DIR / "blank.png", optimize=True)
    for hid in ids:
        raw = Image.open(fetch(hid))
        render(raw, bold=False, draw_size=SIZE).save(OUT_DIR / f"{hid}_thin.png", optimize=True)
        render(raw, bold=True, draw_size=SIZE).save(OUT_DIR / f"{hid}_bold.png", optimize=True)
        render(raw, bold=True, draw_size=96).save(OUT_DIR / f"{hid}_bold96.png", optimize=True)
        print(f"{hid}: thin, bold, bold96")
    for letter in ("m", "n"):
        raw = fetch_letter(letter)
        hid = f"letter_{letter}"
        render(raw, bold=False, draw_size=SIZE).save(OUT_DIR / f"{hid}_thin.png", optimize=True)
        render(raw, bold=True, draw_size=SIZE).save(OUT_DIR / f"{hid}_bold.png", optimize=True)
        render(raw, bold=True, draw_size=96).save(OUT_DIR / f"{hid}_bold96.png", optimize=True)
        print(f"{hid}: thin, bold, bold96 (public domain, wpclipart via Wikimedia Commons)")
    print(f"wrote {len(ids) * 3} PNGs to {OUT_DIR.relative_to(ROOT)}", file=sys.stderr)


if __name__ == "__main__":
    main()
