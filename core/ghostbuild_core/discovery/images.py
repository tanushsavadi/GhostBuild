"""Local cached product photographs, including a bounded monochrome display copy."""

import io
from functools import lru_cache
from pathlib import Path
from PIL import Image, ImageOps


@lru_cache(maxsize=160)
def _read(path, mono, mtime):
    with Image.open(path) as source:
        im = source.convert("L" if mono else "RGB")
        if mono:
            im = ImageOps.contain(im, (288, 144))
            bg = Image.new("L", (288, 144), 0)
            im = ImageOps.invert(im)
            bg.paste(im, ((288 - im.width) // 2, (144 - im.height) // 2))
            im = bg.point(lambda v: round(v / 17) * 17)
        else:
            im.thumbnail((1000, 800))
        out = io.BytesIO()
        im.save(out, format="PNG")
        return out.getvalue()


def photo(root, rec, mono=False):
    if not rec.local_image:
        return None
    root = Path(root).resolve()
    p = (root / rec.local_image).resolve()
    if root not in p.parents or not p.is_file():
        return None
    try:
        return _read(str(p), mono, p.stat().st_mtime_ns)
    except (OSError, ValueError):
        return None


def shortlist(root, records, selected=0, offset=0):
    """Three genuine photos per page, with names and a selection border, in one bounded image.

    Layout labels are authored UI; photographs are the cached official product images.
    The cue supplies the selected product's name when a photo cannot be loaded.
    """
    from PIL import ImageDraw, ImageFont
    import unicodedata

    if not records:
        return None
    sheet = Image.new("L", (288, 144), 0)
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default(size=10)
    count = len(records)
    slot = 288 // count
    loaded = False
    for i, rec in enumerate(records):
        data = photo(root, rec, True)
        x = i * slot
        if data:
            with Image.open(io.BytesIO(data)) as im:
                # Remove the padding of the individual display copy, keep its actual photo.
                bounds = im.getbbox()
                if bounds:
                    im = im.crop(bounds)
                thumb = ImageOps.contain(im, (slot - 8, 105))
                sheet.paste(
                    thumb,
                    (x + (slot - thumb.width) // 2, 4 + (105 - thumb.height) // 2),
                )
                loaded = True
        else:
            draw.text((x + 5, 40), "NO PHOTO", font=font, fill=170)
        label = (
            unicodedata.normalize("NFKD", rec.name)
            .encode("ascii", "ignore")
            .decode()
            .upper()
        )
        draw.text(
            (x + 5, 112),
            f"{offset + i + 1} {label}"[: max(9, slot // 6)],
            font=font,
            fill=255,
        )
        color = (
            unicodedata.normalize("NFKD", rec.color)
            .encode("ascii", "ignore")
            .decode()
            .upper()
        )
        draw.text((x + 5, 126), color[: max(9, slot // 6)], font=font, fill=170)
        if i == selected:
            draw.rectangle((x + 1, 0, x + slot - 2, 143), outline=255, width=2)
    if not loaded:
        return None
    sheet = sheet.point(lambda v: round(v / 17) * 17)
    out = io.BytesIO()
    sheet.save(out, format="PNG")
    return out.getvalue()
