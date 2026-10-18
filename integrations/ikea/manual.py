"""Turn an official assembly-manual PDF into step-level pictures and facts. Uses poppler (pdftotext -bbox, pdftoppm) and Pillow.

What is measured from the PDF itself: where each numbered step starts (a large bold number at the left margin), which printed quantities
("2x") and part numbers sit inside each step's band, and the page images. What is NOT guessed: the words describing a step (authored in
steps.json by someone who looked at the drawing; every part number and quantity there is cross-checked against this PDF text)."""

from __future__ import annotations

import html as htmllib
import io
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter, ImageOps

G2_W, G2_H = 288, 144
LEVELS = 16
PAGE_FOOTER_PT = 795.0


@dataclass
class Word:
    x0: float
    y0: float
    x1: float
    y1: float
    text: str


@dataclass
class Band:
    page: int
    step: int
    y0: float
    y1: float
    qty: list[Word] = field(default_factory=list)
    ids: list[Word] = field(default_factory=list)


def pdf_words(pdf: Path) -> dict[int, list[Word]]:
    out = subprocess.run(["pdftotext", "-bbox", str(pdf), "-"], capture_output=True, text=True, check=True).stdout
    pages: dict[int, list[Word]] = {}
    for n, pg in enumerate(out.split("<page ")[1:], start=1):
        pages[n] = [Word(float(a), float(b), float(c), float(d), htmllib.unescape(t))
                    for a, b, c, d, t in re.findall(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</word>', pg)]
    return pages


def step_bands(pages: dict[int, list[Word]]) -> dict[int, list[Band]]:
    """Per page: the numbered steps (large digits at the left margin) and the part words inside each step's vertical band."""
    res: dict[int, list[Band]] = {}
    for pn, words in pages.items():
        nums = sorted((w for w in words if re.fullmatch(r"\d{1,2}", w.text) and (w.y1 - w.y0) > 30 and w.x0 < 120), key=lambda w: w.y0)
        bands: list[Band] = []
        for i, s in enumerate(nums):
            y0 = max(20.0, s.y0 - 18)
            y1 = PAGE_FOOTER_PT if i + 1 == len(nums) else nums[i + 1].y0 - 18
            b = Band(pn, int(s.text), y0, y1)
            for w in words:
                if y0 <= w.y0 < y1:
                    if re.fullmatch(r"\d+x", w.text):
                        b.qty.append(w)
                    elif re.fullmatch(r"\d{5,8}", w.text):
                        b.ids.append(w)
            bands.append(b)
        res[pn] = bands
    return res


def occurrences(bands: dict[int, list[Band]]) -> dict[int, list[Band]]:
    """step number -> its bands in page order (a step the manual repeats for a second configuration appears twice)."""
    occ: dict[int, list[Band]] = {}
    for pn in sorted(bands):
        for b in bands[pn]:
            occ.setdefault(b.step, []).append(b)
    return occ


def render_page(pdf: Path, page: int, dpi: int) -> Image.Image:
    png = subprocess.run(["pdftoppm", "-r", str(dpi), "-f", str(page), "-l", str(page), "-png", str(pdf)], capture_output=True, check=True).stdout
    return Image.open(io.BytesIO(png)).convert("L")


def crop_pt(img: Image.Image, dpi: int, box: tuple[float, float, float, float]) -> Image.Image:
    k = dpi / 72.0
    x0, y0, x1, y1 = (int(round(v * k)) for v in box)
    return img.crop((max(0, x0), max(0, y0), min(img.width, x1), min(img.height, y1)))


def trim_ink(img: Image.Image, pad: int = 10, thresh: int = 200) -> Image.Image:
    """Crop to the drawn lines (whitespace removed) with a small margin."""
    bw = img.point(lambda v: 255 if v < thresh else 0)
    box = bw.getbbox()
    if box is None:
        return img
    x0, y0, x1, y1 = box
    return img.crop((max(0, x0 - pad), max(0, y0 - pad), min(img.width, x1 + pad), min(img.height, y1 + pad)))


def parts_box(b: Band, margin: float = 60.0) -> tuple[float, float, float, float] | None:
    """Region around the printed quantities and part numbers of a step (the zoomed parts/fasteners detail), clamped to the step's band."""
    ws = [*b.qty, *b.ids]
    if not ws:
        return None
    x0, y0 = min(w.x0 for w in ws) - margin, min(w.y0 for w in ws) - margin
    x1, y1 = max(w.x1 for w in ws) + margin, max(w.y1 for w in ws) + margin
    x0, x1 = max(15.0, x0), min(580.0, x1)
    y0, y1 = max(b.y0, y0), min(b.y1, y1)
    w, h = x1 - x0, y1 - y0
    if w < 170:  # never a sliver: widen around the centre
        cx = (x0 + x1) / 2
        x0, x1 = max(15.0, cx - 85), min(580.0, cx + 85)
    if h < 110:
        cy = (y0 + y1) / 2
        y0, y1 = max(b.y0, cy - 55), min(b.y1, cy + 55)
    return (x0, y0, x1, y1)


# ----------------------------------------------------------------------------------------------- images
def g2_image(crop: Image.Image) -> Image.Image:
    """Line art for the monochrome glasses: fit to 288x144 on black, lines bright and thickened so they survive 4-bit and the downscale.

    The G2 shows black as transparent and white as light, so the manual's black-on-white drawing is inverted. Lines are dilated at 3x
    resolution before the shrink, otherwise a 1 px manual line fades to a grey blur at 288 px wide."""
    S = 3
    tw, th = G2_W * S, G2_H * S
    c = trim_ink(crop)
    r = min(tw / c.width, th / c.height)
    nw, nh = max(1, int(c.width * r)), max(1, int(c.height * r))
    big = c.resize((nw, nh), Image.LANCZOS)
    ink = ImageOps.invert(big).point(lambda v: 0 if v < 40 else min(255, int((v - 40) * 1.6)))
    thick = max(3, int(S * 1.7)) | 1
    ink = ink.filter(ImageFilter.MaxFilter(thick))
    canvas = Image.new("L", (tw, th), 0)
    canvas.paste(ink, ((tw - nw) // 2, (th - nh) // 2))
    small = canvas.resize((G2_W, G2_H), Image.BOX)
    small = ImageOps.autocontrast(small, cutoff=1)
    return small.point(lambda v: (v * (LEVELS - 1) + 127) // 255 * 17)  # exactly the 16 gray4 levels (multiples of 17)


def phone_image(crop: Image.Image, max_w: int = 1280, max_h: int = 800) -> Image.Image:
    c = trim_ink(crop, pad=14)
    r = min(1.0, max_w / c.width, max_h / c.height)
    if r < 1.0:
        c = c.resize((int(c.width * r), int(c.height * r)), Image.LANCZOS)
    return c


def png(img: Image.Image, palette: bool = False) -> bytes:
    b = io.BytesIO()
    if palette:
        img = img.convert("L").quantize(colors=16, method=Image.Quantize.MEDIANCUT)
    img.save(b, format="PNG", optimize=True)
    return b.getvalue()


# ----------------------------------------------------------------------------------------------- cross-checks
def page_text_ids(pages: dict[int, list[Word]], page: int) -> set[str]:
    """Every digit word on a page (pdftotext sometimes splits a rotated number; a >=5 digit prefix of an id counts as seen)."""
    return {w.text for w in pages.get(page, []) if re.fullmatch(r"\d{4,8}", w.text)}


def id_seen(pid: str, seen: set[str]) -> bool:
    return pid in seen or any(pid.startswith(s) and len(s) >= 5 for s in seen)
