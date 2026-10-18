"""G2 guide-image pipeline (device-agnostic image maths; no network, no randomness).

Even G2 image facts (SDK ImageContainerProperty / updateImageRawData, design guidelines):
  - image container 20-288 px wide, 20-144 px high; the pushed image MUST match the container size
    (the host answers `imageSizeInvalid` otherwise), so we always emit one fixed canvas (default 288x144).
  - 4-bit greyscale (16 levels); black is "off" (transparent on the waveguide).
  - the host converts the PNG to gray4 itself (`imageToGray4Failed` exists), so we hand it a plain
    8-bit greyscale PNG whose pixel values are ONLY multiples of 17 -> exactly the 16 gray4 levels.

Pipeline (G2):  crop -> grayscale -> autocontrast/contrast/gamma -> resize (fit) -> letterbox on black
                -> quantize to 16 levels -> draw the ONE annotation (aliased, thick, black halo)
                -> optional caption strip -> deterministic PNG.
Annotation is drawn AFTER quantization so it is exactly level 15 (max brightness) with no AA fringe.
The phone version keeps colour, is high-res, anti-aliased, and carries a placeholder banner if needed.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageOps

PIPELINE_VERSION = 1
G2_MAX_W, G2_MAX_H = 288, 144
LEVELS = 16
STEP = 255 // (LEVELS - 1)  # 17 -> 0,17,...,255
PHONE_MAX = (1280, 640)
PLACEHOLDER_BANNER = "SCHEMATIC – REPLACE WITH RIG PHOTO"

# Mirror of contracts.models.EvidenceLabel (a test asserts they stay identical).
EVIDENCE_LABELS = (
    "MEASURED LIVE", "INFERRED", "COMMANDED", "DETERMINISTIC", "HUMAN CONFIRMED", "MANUFACTURER DOC",
    "AUTHORED PROJECT SPEC", "AI-EXTRACTED · HUMAN-REVIEWED", "AUTHORED DEMO METADATA", "WEB TUTORIAL", "VIDEO TUTORIAL", "GITHUB SOURCE", "REPLAY", "SIMULATED",
)
VIEW_NAMES = ("where", "how", "correct")
ANN_FIELDS = {"circle": ("cx", "cy", "r"), "rect": ("x0", "y0", "x1", "y1"), "arrow": ("from", "to")}


class GuideError(Exception):
    """Bad annotations.json or image problem. Message is written for a teammate, not a developer."""


class MissingSourceError(GuideError):
    pass


# --------------------------------------------------------------------------- spec parsing / validation
@dataclass(frozen=True)
class ViewSpec:
    view: str
    step_id: str
    title: str
    source: str
    provenance: str
    depicts: str
    fallback: dict[str, str]
    placeholder: bool
    units: str
    crop: tuple[float, float, float, float] | None
    annotation: dict[str, Any]
    caption: str
    caption_pos: str
    autocontrast: float
    contrast: float
    gamma: float
    canvas: tuple[int, int]
    fov_note: str | None = None
    banner: str = ""  # placeholder banner text for the phone image; "" = the default PLACEHOLDER_BANNER


@dataclass(frozen=True)
class GuideSpec:
    guide_id: str
    title: str
    placeholder: bool
    views: tuple[ViewSpec, ...]


def _req(d: dict, key: str, ctx: str, typ=str):
    if key not in d or d[key] in (None, ""):
        raise GuideError(f"{ctx}: missing required field '{key}'")
    if not isinstance(d[key], typ):
        raise GuideError(f"{ctx}: '{key}' must be {typ.__name__}")
    return d[key]


def _num(v, ctx: str) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise GuideError(f"{ctx}: expected a number, got {v!r}")
    return float(v)


def _banner_text(value: Any, ctx: str) -> str:
    """Optional 'banner' (guide or view level): placeholder banner text, 'LEFT \u2013 RIGHT' with an en dash, <= 48 chars."""
    if value is None:
        return ""
    if not isinstance(value, str) or " \u2013 " not in value or len(value) > 48:
        raise GuideError(f"{ctx}: banner must be a string like 'SCHEMATIC \u2013 REPLACE WITH PHOTO' (en dash, max 48 chars)")
    return value


def parse_guide(path: Path) -> GuideSpec:
    """Load + validate assets/sources/<guide_id>/annotations.json. Raises GuideError with a precise message."""
    path = Path(path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise GuideError(f"{path}: file not found") from None
    except json.JSONDecodeError as e:
        raise GuideError(f"{path}: not valid JSON ({e})") from None
    if not isinstance(raw, dict):
        raise GuideError(f"{path}: top level must be an object")
    ctx = str(path)
    gid = _req(raw, "guide_id", ctx)
    if gid != path.parent.name:
        raise GuideError(f"{ctx}: guide_id '{gid}' must equal its folder name '{path.parent.name}'")
    title = _req(raw, "title", ctx)
    g_placeholder = bool(raw.get("placeholder", False))
    g_units = raw.get("units", "frac")
    views_raw = raw.get("views")
    if not isinstance(views_raw, list) or not 1 <= len(views_raw) <= 3:
        raise GuideError(f"{ctx}: 'views' must be a list of 1-3 views")
    views, seen = [], set()
    for i, v in enumerate(views_raw):
        vc = f"{ctx} views[{i}]"
        if not isinstance(v, dict):
            raise GuideError(f"{vc}: must be an object")
        name = _req(v, "view", vc)
        if name not in VIEW_NAMES:
            raise GuideError(f"{vc}: view must be one of {VIEW_NAMES}, got {name!r}")
        if name in seen:
            raise GuideError(f"{vc}: duplicate view '{name}'")
        seen.add(name)
        vc = f"{ctx} view '{name}'"
        vtitle = _req(v, "title", vc)
        if len(vtitle) > 24:
            raise GuideError(f"{vc}: title is {len(vtitle)} chars, max 24")
        prov = _req(v, "provenance", vc)
        if prov not in EVIDENCE_LABELS:
            raise GuideError(f"{vc}: provenance {prov!r} is not an EvidenceLabel {EVIDENCE_LABELS}")
        fb = _req(v, "fallback_cue", vc, dict)
        l1, l2 = _req(fb, "line1", vc + " fallback_cue"), fb.get("line2", "")
        if len(l1) > 24 or len(l2) > 26:
            raise GuideError(f"{vc}: fallback_cue line1 max 24 chars, line2 max 26 chars")
        caption = v.get("caption", "") or ""
        if len(caption) > 24:
            raise GuideError(f"{vc}: caption is {len(caption)} chars, max 24")
        units = v.get("units", g_units)
        if units not in ("frac", "px"):
            raise GuideError(f"{vc}: units must be 'frac' or 'px'")
        crop = v.get("crop")
        if crop is not None:
            if not (isinstance(crop, list) and len(crop) == 4):
                raise GuideError(f"{vc}: crop must be [x0,y0,x1,y1]")
            crop = tuple(_num(c, vc + " crop") for c in crop)
            if crop[2] <= crop[0] or crop[3] <= crop[1]:
                raise GuideError(f"{vc}: crop must have x1>x0 and y1>y0")
            if units == "frac" and not all(0 <= c <= 1 for c in crop):
                raise GuideError(f"{vc}: with units 'frac' every crop value must be within 0..1")
        ann = v.get("annotation")
        if isinstance(ann, list):
            raise GuideError(f"{vc}: exactly ONE annotation is allowed (got a list); G2 shows one highlight per image")
        if not isinstance(ann, dict) or ann.get("type") not in ANN_FIELDS:
            raise GuideError(f"{vc}: annotation must be one object with type circle|arrow|rect")
        want = set(ANN_FIELDS[ann["type"]]) | {"type"}
        if set(ann) != want:
            raise GuideError(f"{vc}: {ann['type']} annotation needs exactly keys {sorted(want)}, got {sorted(ann)}")
        for k in ANN_FIELDS[ann["type"]]:
            if k in ("from", "to"):
                if not (isinstance(ann[k], list) and len(ann[k]) == 2):
                    raise GuideError(f"{vc}: annotation '{k}' must be [x,y]")
                [_num(c, vc + f" annotation.{k}") for c in ann[k]]
            else:
                _num(ann[k], vc + f" annotation.{k}")
        for k in ("autocontrast", "contrast", "gamma"):
            if k in v:
                _num(v[k], f"{vc} {k}")
        canvas = v.get("g2_size", [G2_MAX_W, G2_MAX_H])
        if not (isinstance(canvas, list) and len(canvas) == 2 and 20 <= canvas[0] <= G2_MAX_W and 20 <= canvas[1] <= G2_MAX_H):
            raise GuideError(f"{vc}: g2_size must be [w,h] with 20<=w<=288, 20<=h<=144")
        pos = v.get("caption_pos", "bottom")
        if pos not in ("bottom", "top"):
            raise GuideError(f"{vc}: caption_pos must be 'bottom' or 'top'")
        views.append(ViewSpec(
            view=name, step_id=_req(v, "step_id", vc), title=vtitle, source=_req(v, "source", vc),
            provenance=prov, depicts=_req(v, "depicts", vc), fallback={"line1": l1, "line2": l2},
            placeholder=bool(v.get("placeholder", g_placeholder)), units=units, crop=crop, annotation=ann,
            caption=caption, caption_pos=pos, autocontrast=float(v.get("autocontrast", 1.0)),
            contrast=float(v.get("contrast", 1.0)), gamma=float(v.get("gamma", 1.0)),
            canvas=(int(canvas[0]), int(canvas[1])), fov_note=v.get("fov_note"),
            banner=_banner_text(v.get("banner", raw.get("banner")), vc),
        ))
    return GuideSpec(gid, title, g_placeholder, tuple(views))


# --------------------------------------------------------------------------- geometry
def crop_box_px(spec: ViewSpec, size: tuple[int, int]) -> tuple[int, int, int, int]:
    """Crop rectangle in source pixels (clamped to the image). No crop -> whole image."""
    w, h = size
    if spec.crop is None:
        return 0, 0, w, h
    x0, y0, x1, y1 = spec.crop
    if spec.units == "frac":
        x0, x1, y0, y1 = x0 * w, x1 * w, y0 * h, y1 * h
    box = (max(0, round(x0)), max(0, round(y0)), min(w, round(x1)), min(h, round(y1)))
    if box[2] - box[0] < 8 or box[3] - box[1] < 8:
        raise GuideError(f"view '{spec.view}': crop {spec.crop} is empty/too small for a {w}x{h} source")
    return box


def _to_px(v: float, extent: int, units: str) -> float:
    return v * extent if units == "frac" else v


def annotation_px(spec: ViewSpec, size: tuple[int, int]) -> dict[str, Any]:
    """Annotation in SOURCE pixel coordinates."""
    w, h = size
    a, u = spec.annotation, spec.units
    t = a["type"]
    if t == "circle":
        return {"type": t, "cx": _to_px(a["cx"], w, u), "cy": _to_px(a["cy"], h, u), "r": _to_px(a["r"], w, u)}
    if t == "rect":
        return {"type": t, "x0": _to_px(a["x0"], w, u), "y0": _to_px(a["y0"], h, u),
                "x1": _to_px(a["x1"], w, u), "y1": _to_px(a["y1"], h, u)}
    return {"type": t, "from": [_to_px(a["from"][0], w, u), _to_px(a["from"][1], h, u)],
            "to": [_to_px(a["to"][0], w, u), _to_px(a["to"][1], h, u)]}


def _anchor(a: dict[str, Any]) -> tuple[float, float]:
    if a["type"] == "circle":
        return a["cx"], a["cy"]
    if a["type"] == "rect":
        return (a["x0"] + a["x1"]) / 2, (a["y0"] + a["y1"]) / 2
    return a["to"][0], a["to"][1]


def _map_annotation(a: dict[str, Any], box, scale: float, off: tuple[float, float]) -> dict[str, Any]:
    def p(x, y):
        return ((x - box[0]) * scale + off[0], (y - box[1]) * scale + off[1])
    t = a["type"]
    if t == "circle":
        cx, cy = p(a["cx"], a["cy"])
        return {"type": t, "cx": cx, "cy": cy, "r": a["r"] * scale}
    if t == "rect":
        x0, y0 = p(a["x0"], a["y0"]); x1, y1 = p(a["x1"], a["y1"])
        return {"type": t, "x0": min(x0, x1), "y0": min(y0, y1), "x1": max(x0, x1), "y1": max(y0, y1)}
    return {"type": t, "from": list(p(*a["from"])), "to": list(p(*a["to"]))}


def check_annotation_in_crop(spec: ViewSpec, size: tuple[int, int]) -> tuple[tuple[int, int, int, int], dict[str, Any]]:
    box = crop_box_px(spec, size)
    ann = annotation_px(spec, size)
    ax, ay = _anchor(ann)
    if not (box[0] <= ax <= box[2] and box[1] <= ay <= box[3]):
        raise GuideError(f"view '{spec.view}': the annotation target ({ax:.0f},{ay:.0f}) lies outside the crop {box}; "
                         "widen the crop or move the annotation")
    return box, ann


# --------------------------------------------------------------------------- drawing
def _draw_annotation(d: ImageDraw.ImageDraw, a: dict[str, Any], line: float, halo: float, fg, bg) -> None:
    """One highlight: halo (bg) under the stroke (fg). Works in whatever pixel space `d` is in."""
    lw, hw = max(1, round(line)), max(1, round(line + 2 * halo))
    t = a["type"]
    if t == "circle":
        box = [a["cx"] - a["r"], a["cy"] - a["r"], a["cx"] + a["r"], a["cy"] + a["r"]]
        d.ellipse(box, outline=bg, width=hw)
        d.ellipse(box, outline=fg, width=lw)
    elif t == "rect":
        box = [a["x0"], a["y0"], a["x1"], a["y1"]]
        d.rectangle(box, outline=bg, width=hw)
        d.rectangle(box, outline=fg, width=lw)
    else:
        (x0, y0), (x1, y1) = a["from"], a["to"]
        ang = math.atan2(y1 - y0, x1 - x0)
        head = max(10.0, line * 4.0)
        bx, by = x1 - math.cos(ang) * head * 0.8, y1 - math.sin(ang) * head * 0.8
        nx, ny = -math.sin(ang), math.cos(ang)
        tri = [(x1, y1), (bx + nx * head * 0.55, by + ny * head * 0.55), (bx - nx * head * 0.55, by - ny * head * 0.55)]
        d.line([(x0, y0), (bx, by)], fill=bg, width=hw)
        d.polygon(tri, fill=bg, outline=bg, width=max(1, round(halo * 2)))
        d.line([(x0, y0), (bx, by)], fill=fg, width=lw)
        d.polygon(tri, fill=fg)


def _font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.load_default(size=size)  # Pillow's bundled font: identical on every machine


def _fit_text(text: str, max_w: int, size: int, aa: bool) -> ImageFont.FreeTypeFont:
    img = Image.new("L", (4, 4))
    d = ImageDraw.Draw(img)
    d.fontmode = "L" if aa else "1"
    while size > 8:
        f = _font(size)
        if d.textlength(text, font=f) <= max_w:
            return f
        size -= 1
    return _font(8)


# --------------------------------------------------------------------------- tone
def tone(img: Image.Image, spec: ViewSpec) -> Image.Image:
    if spec.autocontrast > 0:
        img = ImageOps.autocontrast(img, cutoff=spec.autocontrast)
    if spec.contrast != 1.0:
        from PIL import ImageEnhance
        img = ImageEnhance.Contrast(img).enhance(spec.contrast)
    if spec.gamma != 1.0:
        lut = [round(255 * (i / 255) ** (1 / spec.gamma)) for i in range(256)]
        img = img.point(lut * (len(img.getbands())))
    return img


def quantize16(img: Image.Image) -> Image.Image:
    """Round a greyscale image to exactly the 16 gray4 levels (0,17,..255)."""
    lut = [min(255, round(i / STEP) * STEP) for i in range(256)]
    return img.convert("L").point(lut)


def grey_levels(img: Image.Image) -> list[int]:
    return sorted({v for _, v in (img.convert("L").getcolors(maxcolors=256) or [])})


# --------------------------------------------------------------------------- renderers
def load_source(path: Path) -> Image.Image:
    path = Path(path)
    if not path.is_file():
        raise MissingSourceError(f"source image not found: {path}. Put the photo there (see assets/README.md) "
                                 "or fix 'source' in annotations.json")
    try:
        img = Image.open(path)
        img.load()
    except Exception as e:  # noqa: BLE001 - surface any decoder failure as a teammate-readable error
        raise GuideError(f"cannot read image {path}: {e}") from None
    img = ImageOps.exif_transpose(img)
    return img


def render_g2(src: Image.Image, spec: ViewSpec) -> Image.Image:
    box, ann = check_annotation_in_crop(spec, src.size)
    cw, ch = spec.canvas
    crop = src.convert("L").crop(box)
    crop = tone(crop, spec)
    scale = min(cw / crop.width, ch / crop.height)
    nw, nh = max(1, round(crop.width * scale)), max(1, round(crop.height * scale))
    crop = crop.resize((nw, nh), Image.LANCZOS)
    canvas = Image.new("L", (cw, ch), 0)
    off = ((cw - nw) // 2, (ch - nh) // 2)
    canvas.paste(crop, off)
    canvas = quantize16(canvas)
    mapped = _map_annotation(ann, box, nw / (box[2] - box[0]), off)
    d = ImageDraw.Draw(canvas)
    d.fontmode = "1"
    _draw_annotation(d, mapped, line=5, halo=2, fg=255, bg=0)
    if spec.caption:
        _caption_g2(canvas, spec)
    return canvas


def _caption_g2(canvas: Image.Image, spec: ViewSpec) -> None:
    w, h = canvas.size
    d = ImageDraw.Draw(canvas)
    d.fontmode = "1"
    font = _fit_text(spec.caption, w - 8, 16, aa=False)
    bar = 20
    y0 = h - bar if spec.caption_pos == "bottom" else 0
    d.rectangle([0, y0, w, y0 + bar], fill=0)
    tw = d.textlength(spec.caption, font=font)
    d.text(((w - tw) / 2, y0 + bar / 2), spec.caption, fill=255, font=font, anchor="lm")


def render_phone(src: Image.Image, spec: ViewSpec, placeholder: bool) -> Image.Image:
    """High-res, colour, anti-aliased. The placeholder banner is baked in HERE only (never on the G2 image)."""
    box, ann = check_annotation_in_crop(spec, src.size)
    img = src.convert("RGB").crop(box)
    if spec.autocontrast > 0:
        img = ImageOps.autocontrast(img, cutoff=spec.autocontrast)
    img = tone(img, replace(spec, autocontrast=0.0))
    scale = min(PHONE_MAX[0] / img.width, PHONE_MAX[1] / img.height)
    nw, nh = max(1, round(img.width * scale)), max(1, round(img.height * scale))
    img = img.resize((nw, nh), Image.LANCZOS).convert("RGBA")
    mapped = _map_annotation(ann, box, scale, (0, 0))
    ss = 3
    big = {k: ([c * ss for c in v] if isinstance(v, list) else v * ss if k != "type" else v) for k, v in mapped.items()}
    layer = Image.new("RGBA", (nw * ss, nh * ss), (0, 0, 0, 0))
    _draw_annotation(ImageDraw.Draw(layer), big, line=7 * ss, halo=3 * ss, fg=(255, 230, 0, 255), bg=(0, 0, 0, 255))
    img = Image.alpha_composite(img, layer.resize((nw, nh), Image.LANCZOS))
    d = ImageDraw.Draw(img)
    if spec.caption:
        font = _fit_text(spec.caption, nw - 40, max(18, nh // 14), aa=True)
        bar = font.size + 18
        y0 = nh - bar if spec.caption_pos == "bottom" else 0
        d.rectangle([0, y0, nw, y0 + bar], fill=(0, 0, 0, 255))
        d.text((nw / 2, y0 + bar / 2), spec.caption, fill=(255, 255, 255, 255), font=font, anchor="mm")
    if placeholder:
        _banner(d, nw, nh, spec.caption_pos, spec.banner or PLACEHOLDER_BANNER)
    return img.convert("RGB")


def _banner(d: ImageDraw.ImageDraw, nw: int, nh: int, caption_pos: str, text: str = PLACEHOLDER_BANNER) -> None:
    """Red banner 'SCHEMATIC - REPLACE WITH RIG PHOTO'. The bundled font has no en dash glyph (renders tofu),
    so the dash is drawn as a bar between the two text runs."""
    left, right = text.split(" \u2013 ")
    font = _fit_text(left + " - " + right, nw - 24, max(16, nh // 12), aa=True)
    bar = font.size + 16
    y0 = 0 if caption_pos == "bottom" else nh - bar
    d.rectangle([0, y0, nw, y0 + bar], fill=(200, 20, 20, 255))
    wl, wr, gap = d.textlength(left, font=font), d.textlength(right, font=font), font.size * 1.1
    x = (nw - (wl + gap + wr)) / 2
    cy = y0 + bar / 2
    d.text((x, cy), left, fill=(255, 255, 255, 255), font=font, anchor="lm")
    d.rectangle([x + wl + gap * 0.2, cy - font.size * 0.06, x + wl + gap * 0.8, cy + font.size * 0.06], fill=(255, 255, 255, 255))
    d.text((x + wl + gap, cy), right, fill=(255, 255, 255, 255), font=font, anchor="lm")


# --------------------------------------------------------------------------- output
def png_bytes(img: Image.Image) -> bytes:
    """Deterministic PNG: no metadata, fixed compression."""
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=False, compress_level=9)
    return buf.getvalue()


def sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def diff_bbox(a: Image.Image, b: Image.Image):
    """Bounding box of pixels that differ (None if identical); used by the single-annotation test."""
    return ImageChops.difference(a.convert("L"), b.convert("L")).getbbox()
