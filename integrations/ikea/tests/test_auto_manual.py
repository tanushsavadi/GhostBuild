"""On-demand per-step guide from an IKEA manual (auto_manual.py). Synthetic PDFs; no network, no model calls."""

import shutil
from pathlib import Path

import pytest

fitz = pytest.importorskip("fitz")
pytestmark = pytest.mark.skipif(shutil.which("pdftotext") is None, reason="poppler (pdftotext) not installed")

from contracts.models import Card
from integrations.ikea.auto_manual import build_card


def manual(path: Path, steps: int) -> Path:
    doc = fitz.open()
    for n in range(1, steps + 1):
        page = doc.new_page(width=595, height=842)
        page.insert_text((40, 120), str(n), fontsize=48)          # the big step number at the left margin
        page.insert_text((300, 200), "2x", fontsize=12)
        page.insert_text((300, 216), "1015" + f"{n:02}", fontsize=12)
        page.draw_rect(fitz.Rect(150, 250, 450, 500), width=3)     # the drawing
    doc.save(path)
    return path


def test_every_numbered_step_gets_its_own_official_picture_and_printed_parts(tmp_path):
    pdf = manual(tmp_path / "m.pdf", 4)
    seen = {}

    def describe(crops, name, parts):
        seen.update(crops)
        return {n: {"line1": f"fit part {n}", "line2": "into the panel", "title": f"Fit part {n}", "detail": "As drawn."} for n in crops}

    card = Card.model_validate(build_card(article="1", name="TEST", pdf_url="https://x/m.pdf", product_url="https://x/p",
                                          root=tmp_path, pdf=pdf, describe=describe))
    assert [s.id for s in card.steps] == ["s01", "s02", "s03", "s04"] and sorted(seen) == [1, 2, 3, 4]
    assert card.steps[1].cue.line1 == "FIT PART 2" and card.steps[1].parts[0].id == "101502" and card.steps[1].parts[0].qty == 2
    assert all((tmp_path / v.image).is_file() for g in card.guides for v in g.views)
    assert card.review and "not human-reviewed" in card.review
    assert card.steps[0].cites[0].url.endswith("#page=1")


def test_without_step_text_each_step_still_has_its_picture_and_numbers(tmp_path):
    pdf = manual(tmp_path / "m.pdf", 3)

    def broken(*a):
        raise RuntimeError("no model")

    card = Card.model_validate(build_card(article="2", name="TEST", pdf_url="https://x/m.pdf", product_url="https://x/p",
                                          root=tmp_path, pdf=pdf, describe=broken))
    assert card.steps[0].cue.line1 == "STEP 1: SEE PICTURE" and card.steps[0].cue.line2 == "2X 101501"


def test_a_manual_without_numbered_steps_falls_back(tmp_path):
    doc = fitz.open()
    doc.new_page().insert_text((300, 300), "hello", fontsize=12)
    doc.save(tmp_path / "plain.pdf")
    assert build_card(article="3", name="T", pdf_url="https://x", product_url="https://x", root=tmp_path,
                      pdf=tmp_path / "plain.pdf", describe=None) is None
