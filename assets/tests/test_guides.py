"""Guide image pipeline tests. No network; synthetic sources only (plus the committed outputs)."""
from __future__ import annotations

import copy
import json
import typing
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

import build_guides as bg
from lib import gimage as gi

ROOT = Path(__file__).resolve().parents[2]


# --------------------------------------------------------------------------- helpers
def make_source(path: Path, size=(1000, 500)) -> None:
    img = Image.new("RGB", size, (85, 85, 85))
    d = ImageDraw.Draw(img)
    d.rectangle([600, 300, 699, 349], fill=(255, 255, 255))  # known bright box
    img.save(path)


def view(name="where", **over) -> dict:
    v = {
        "view": name, "step_id": f"g.{name}", "title": name.upper(), "source": f"{name}.png",
        "units": "px", "crop": [550, 275, 750, 375],
        "annotation": {"type": "rect", "x0": 560, "y0": 285, "x1": 590, "y1": 310},
        "provenance": "AUTHORED DEMO METADATA", "depicts": "test", "autocontrast": 0,
        "fallback_cue": {"line1": "CHECK LENS", "line2": ""},
    }
    v.update(over)
    return v


def make_guide(tmp: Path, views=None, placeholder=False, gid="g") -> Path:
    gdir = tmp / "sources" / gid
    gdir.mkdir(parents=True)
    views = views or [view()]
    for v in views:
        if (gdir / v["source"]).suffix and not (gdir / v["source"]).exists():
            make_source(gdir / v["source"])
    (gdir / "annotations.json").write_text(json.dumps(
        {"guide_id": gid, "title": "Test guide", "placeholder": placeholder, "views": views}))
    return gdir


def components(img: Image.Image, level=255) -> int:
    """8-connected components of pixels == level."""
    w, h = img.size
    px = img.load()
    seen = set()
    n = 0
    for y in range(h):
        for x in range(w):
            if px[x, y] == level and (x, y) not in seen:
                n += 1
                stack = [(x, y)]
                seen.add((x, y))
                while stack:
                    cx, cy = stack.pop()
                    for dx in (-1, 0, 1):
                        for dy in (-1, 0, 1):
                            nx, ny = cx + dx, cy + dy
                            if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in seen and px[nx, ny] == level:
                                seen.add((nx, ny))
                                stack.append((nx, ny))
    return n


# --------------------------------------------------------------------------- size / levels
@pytest.mark.parametrize("ann", [
    {"type": "circle", "cx": 580, "cy": 300, "r": 20},
    {"type": "rect", "x0": 560, "y0": 285, "x1": 590, "y1": 310},
    {"type": "arrow", "from": [700, 290], "to": [660, 320]},
])
def test_g2_size_and_exactly_16_levels(tmp_path, ann):
    gdir = make_guide(tmp_path, [view(annotation=ann)])
    man, files = bg.build_guide(gdir, tmp_path / "out", write=False)
    img = Image.open(__import__("io").BytesIO(files["where.png"]))
    assert img.mode == "L"
    assert img.width <= 288 and img.height <= 144
    levels = gi.grey_levels(img)
    assert len(levels) <= 16 and all(v % 17 == 0 for v in levels)
    assert 255 in levels  # annotation at max brightness
    assert man["views"][0]["w"] == img.width and man["views"][0]["bytes"] == len(files["where.png"])


def test_quantize_maps_every_value_onto_16_levels():
    ramp = Image.frombytes("L", (256, 1), bytes(range(256)))
    assert len(gi.grey_levels(gi.quantize16(ramp))) == 16


def test_committed_outputs_obey_g2_contract():
    mans = sorted((ROOT / "knowledge" / "guides").glob("*/manifest.json"))
    assert mans, "run `make guides` first"
    for m in mans:
        man = json.loads(m.read_text())
        for v in man["views"]:
            img = Image.open(ROOT / v["image"])
            assert img.mode == "L" and img.width <= 288 and img.height <= 144
            lv = gi.grey_levels(img)
            assert len(lv) <= 16 and all(x % 17 == 0 for x in lv), (v["image"], lv)
            assert (ROOT / v["phone_image"]).is_file()


# --------------------------------------------------------------------------- determinism / sync
def test_build_is_deterministic(tmp_path):
    gdir = make_guide(tmp_path)
    m1, f1 = bg.build_guide(gdir, tmp_path / "o", write=False)
    m2, f2 = bg.build_guide(gdir, tmp_path / "o", write=False)
    assert f1 == f2 and m1 == m2
    assert m1["views"][0]["sha256"] == gi.sha256_hex(f1["where.png"])


def test_committed_outputs_are_not_stale():
    """What is committed in knowledge/guides must equal a fresh build (otherwise: run `make guides`)."""
    for gdir in sorted((ROOT / "assets" / "sources").iterdir()):
        if not gdir.is_dir():
            continue
        _, files = bg.build_guide(gdir, ROOT / "knowledge" / "guides", write=False)
        for name, data in files.items():
            assert (ROOT / "knowledge" / "guides" / gdir.name / name).read_bytes() == data, f"{gdir.name}/{name} stale"


def test_inventory_in_sync():
    mans = [bg.build_guide(g, ROOT / "knowledge" / "guides", write=False)[0]
            for g in sorted((ROOT / "assets" / "sources").iterdir()) if g.is_dir()]
    assert (ROOT / "assets" / "INVENTORY.md").read_text() == bg.inventory_md(mans, {})


# --------------------------------------------------------------------------- single annotation rule
def test_exactly_one_annotation_component_on_flat_source(tmp_path):
    flat = Image.new("RGB", (1000, 500), (60, 60, 60))
    for ann in ({"type": "circle", "cx": 500, "cy": 250, "r": 120},
                {"type": "rect", "x0": 300, "y0": 100, "x1": 700, "y1": 400},
                {"type": "arrow", "from": [200, 100], "to": [600, 350]}):
        v = gi.parse_guide(make_guide(tmp_path / ann["type"], [view(crop=None, annotation=ann)]) / "annotations.json").views[0]
        assert components(gi.render_g2(flat, v)) == 1, ann["type"]


def test_annotation_list_is_rejected(tmp_path):
    two = [view()["annotation"], view()["annotation"]]
    gdir = make_guide(tmp_path, [view(annotation=two)])
    with pytest.raises(gi.GuideError, match="exactly ONE annotation"):
        gi.parse_guide(gdir / "annotations.json")


@pytest.mark.parametrize("ann,msg", [
    ({"type": "star", "cx": 1}, "circle|arrow|rect"),
    ({"type": "circle", "cx": 1, "cy": 1, "r": 3, "extra": 1}, "exactly keys"),
    ({"type": "arrow", "from": [1, 1]}, "exactly keys"),
])
def test_bad_annotations_rejected(tmp_path, ann, msg):
    gdir = make_guide(tmp_path, [view(annotation=ann)])
    with pytest.raises(gi.GuideError, match=msg):
        gi.parse_guide(gdir / "annotations.json")


def test_annotation_outside_crop_rejected(tmp_path):
    gdir = make_guide(tmp_path, [view(annotation={"type": "circle", "cx": 100, "cy": 100, "r": 10})])
    with pytest.raises(gi.GuideError, match="outside the crop"):
        bg.build_guide(gdir, tmp_path / "o", write=False)


# --------------------------------------------------------------------------- crop correctness
def test_crop_box_fractions_and_pixels():
    spec = gi.parse_guide(make_guide(Path(__import__("tempfile").mkdtemp()), [view(units="frac", crop=[0.55, 0.55, 0.75, 0.75],
        annotation={"type": "circle", "cx": 0.65, "cy": 0.65, "r": 0.01})]) / "annotations.json").views[0]
    assert gi.crop_box_px(spec, (1000, 500)) == (550, 275, 750, 375)


def test_crop_maps_content_to_expected_pixels(tmp_path):
    # crop 200x100 -> x1.44 -> 288x144; the bright 100x50 box lands at x 72..216, y 36..108
    v = gi.parse_guide(make_guide(tmp_path, [view()]) / "annotations.json").views[0]
    src = Image.open(tmp_path / "sources" / "g" / "where.png")
    out = gi.render_g2(src, v)
    assert out.size == (288, 144)
    assert out.getpixel((144, 72)) == 255          # box centre is bright
    assert out.getpixel((40, 72)) == 85            # background level (85 is a multiple of 17)
    assert out.getpixel((230, 120)) == 85
    # whole-bright-region bbox (ignoring the small annotation top-left) matches the mapped box
    bright = out.point(lambda x: 255 if x == 255 else 0).crop((64, 0, 288, 144))
    bx = bright.getbbox()
    assert abs(bx[0] + 64 - 72) <= 2 and abs(bx[2] + 64 - 216) <= 2 and abs(bx[1] - 36) <= 2 and abs(bx[3] - 108) <= 2


def test_letterbox_on_black_preserves_aspect(tmp_path):
    v = gi.parse_guide(make_guide(tmp_path, [view(crop=[500, 250, 800, 450])]) / "annotations.json").views[0]  # 300x200 (3:2)
    src = Image.open(tmp_path / "sources" / "g" / "where.png")
    out = gi.render_g2(src, v)
    assert out.size == (288, 144)
    assert out.getpixel((2, 70)) == 0 and out.getpixel((285, 70)) == 0  # black side bars (scaled 216x144 centred)


# --------------------------------------------------------------------------- errors
def test_missing_source_is_a_clear_error(tmp_path):
    gdir = make_guide(tmp_path)
    (gdir / "where.png").unlink()
    with pytest.raises(gi.MissingSourceError, match="where.png"):
        bg.build_guide(gdir, tmp_path / "o", write=False)


def test_cli_reports_missing_source_and_exits_nonzero(tmp_path, capsys):
    gdir = make_guide(tmp_path)
    (gdir / "where.png").unlink()
    rc = bg.main(["--sources", str(tmp_path / "sources"), "--out", str(tmp_path / "out"), "--inventory", str(tmp_path / "inv.md")])
    assert rc == 1
    assert "source image not found" in capsys.readouterr().err
    assert not (tmp_path / "out" / "g" / "manifest.json").exists()  # nothing partial


def test_validation_errors(tmp_path):
    for bad, msg in [
        (view(provenance="TRUST ME"), "not an EvidenceLabel"),
        (view(caption="X" * 25), "caption"),
        (view(title="T" * 25), "title"),
        (view(view="sideways"), "view must be one of"),
        (view(units="frac", crop=[0, 0, 5, 5]), "within 0..1"),
    ]:
        gdir = make_guide(tmp_path / msg.replace(" ", "_").replace(".", ""), [bad])
        with pytest.raises(gi.GuideError, match=msg):
            gi.parse_guide(gdir / "annotations.json")


# --------------------------------------------------------------------------- placeholder / manifest / contract
def test_placeholder_flag_banner_only_on_phone(tmp_path):
    ph = bg.build_guide(make_guide(tmp_path / "a", placeholder=True), tmp_path / "o", write=False)
    real = bg.build_guide(make_guide(tmp_path / "b", placeholder=False), tmp_path / "o", write=False)
    assert ph[0]["placeholder"] is True and real[0]["placeholder"] is False
    assert ph[1]["where.png"] == real[1]["where.png"]                  # G2 image carries no banner
    assert ph[1]["where.phone.png"] != real[1]["where.phone.png"]      # phone image does
    import io
    top_ph = Image.open(io.BytesIO(ph[1]["where.phone.png"])).getpixel((2, 2))
    assert top_ph == (200, 20, 20)
    assert Image.open(io.BytesIO(real[1]["where.phone.png"])).getpixel((2, 2)) != (200, 20, 20)


def test_labels_match_contract():
    from contracts.models import EvidenceLabel
    assert tuple(typing.get_args(EvidenceLabel)) == gi.EVIDENCE_LABELS


def test_committed_manifest_matches_contract_and_files():
    from contracts.models import Guide
    for mp in sorted((ROOT / "knowledge" / "guides").glob("*/manifest.json")):
        man = json.loads(mp.read_text())
        Guide.model_validate(man["guide"])   # paste-ready for card.guides[]
        for v in man["views"]:
            b = (ROOT / v["image"]).read_bytes()
            assert gi.sha256_hex(b) == v["sha256"] and len(b) == v["bytes"]
            if man["placeholder"]:
                assert v["provenance"] == "AUTHORED DEMO METADATA" and v["placeholder"] is True


def test_camera_lens_standin_is_flagged_placeholder():
    man = json.loads((ROOT / "knowledge/guides/camera_lens/manifest.json").read_text())
    assert [v["view"] for v in man["views"]] == ["where", "how", "correct"]
    assert all(v["placeholder"] and v["provenance"] == "AUTHORED DEMO METADATA" for v in man["views"])


def test_custom_placeholder_banner_text_is_optional_and_validated(tmp_path):
    gdir = make_guide(tmp_path / "a", placeholder=True)
    ann = json.loads((gdir / "annotations.json").read_text())
    ann["banner"] = "SCHEMATIC – REPLACE WITH PHOTO"
    (gdir / "annotations.json").write_text(json.dumps(ann))
    spec = gi.parse_guide(gdir / "annotations.json")
    assert spec.views[0].banner == "SCHEMATIC – REPLACE WITH PHOTO"
    default = bg.build_guide(make_guide(tmp_path / "b", placeholder=True), tmp_path / "o", write=False)
    custom = bg.build_guide(gdir, tmp_path / "o", write=False)
    assert custom[1]["where.png"] == default[1]["where.png"]              # G2 image unchanged
    assert custom[1]["where.phone.png"] != default[1]["where.phone.png"]  # banner text differs on the phone image
    for bad in ("NO DASH HERE", "A – " + "B" * 50, 12):
        ann["banner"] = bad
        (gdir / "annotations.json").write_text(json.dumps(ann))
        with pytest.raises(gi.GuideError, match="banner"):
            gi.parse_guide(gdir / "annotations.json")


def test_paper_cup_standins_are_flagged_schematic_placeholders():
    for gid, views in (("cup_fold_half", ["where", "how", "correct"]), ("cup_pinch", ["where", "how"])):
        man = json.loads((ROOT / f"knowledge/guides/{gid}/manifest.json").read_text())
        spec = gi.parse_guide(ROOT / f"assets/sources/{gid}/annotations.json")
        assert [v["view"] for v in man["views"]] == views
        assert man["placeholder"] is True and spec.views[0].banner == "SCHEMATIC – REPLACE WITH PHOTO"
        assert all(v["placeholder"] and v["provenance"] == "AUTHORED DEMO METADATA" for v in man["views"])
        assert all(v["depicts"].startswith("SCHEMATIC stand-in") for v in man["views"])
