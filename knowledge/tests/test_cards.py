"""Validator tests: the shipped cards pass; deliberately broken copies fail with a readable reason."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from knowledge.validate import DEFAULT_CARDS_DIR, REPO_ROOT, main, validate_cards

CAMERA = DEFAULT_CARDS_DIR / "camera_lens.json"
SETUP = DEFAULT_CARDS_DIR / "setup_station.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_card(tmp_path: Path, data: dict, name: str = "camera_lens.json") -> Path:
    cards = tmp_path / "cards"
    cards.mkdir(exist_ok=True)
    (cards / name).write_text(json.dumps(data), encoding="utf-8")
    return cards


def _errors_for(tmp_path: Path, data: dict, name: str = "camera_lens.json") -> list[str]:
    cards = _write_card(tmp_path, data, name)
    return validate_cards(cards, root=REPO_ROOT)


def test_shipped_cards_are_valid():
    assert validate_cards(DEFAULT_CARDS_DIR, root=REPO_ROOT) == []


def test_each_shipped_card_validates_alone(tmp_path: Path):
    for path in (CAMERA, SETUP):
        cards = tmp_path / path.stem
        cards.mkdir()
        (cards / path.name).write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        assert validate_cards(cards, root=REPO_ROOT) == [], path.name


def test_cli_exit_zero_on_shipped_cards(capsys):
    assert main([str(DEFAULT_CARDS_DIR)]) == 0
    assert "OK: 2 card(s) valid" in capsys.readouterr().out


def test_bad_glyph_rejected(tmp_path: Path):
    data = _load(CAMERA)
    data["tests"][0]["fact"]["line1"] = "CAMERA VIEW LOST!"
    errors = _errors_for(tmp_path, data)
    assert any("characters not allowed" in e and "'!'" in e for e in errors), errors


def test_lowercase_cue_rejected(tmp_path: Path):
    data = _load(CAMERA)
    data["tests"][0]["fact"]["line2"] = "Check camera lens"
    errors = _errors_for(tmp_path, data)
    assert any("upper case" in e for e in errors), errors


def test_diagnosis_phrasing_rejected(tmp_path: Path):
    data = _load(CAMERA)
    data["tests"][0]["fact"]["line2"] = "LENS IS COVERED"
    errors = _errors_for(tmp_path, data)
    assert any("diagnosis" in e and "IS" in e for e in errors), errors


def test_unknown_signal_rejected(tmp_path: Path):
    data = _load(CAMERA)
    data["tests"][0]["fail_when"][0]["signal"] = "camera.nonexistent"
    errors = _errors_for(tmp_path, data)
    assert any("unknown signal 'camera.nonexistent'" in e for e in errors), errors


def test_signal_through_scalar_rejected(tmp_path: Path):
    data = _load(CAMERA)
    data["functional"]["trigger"][0]["signal"] = "camera.motion.deep"
    errors = _errors_for(tmp_path, data)
    assert any("unknown signal 'camera.motion.deep'" in e or "scalar" in e for e in errors), errors


def test_threshold_outside_physical_range_rejected(tmp_path: Path):
    data = _load(CAMERA)
    data["tests"][0]["fail_when"][0]["value"] = 300
    errors = _errors_for(tmp_path, data)
    assert any("outside physical range" in e for e in errors), errors


def test_fabricated_quote_rejected(tmp_path: Path):
    data = _load(CAMERA)
    data["tests"][0]["checks"][0]["cites"] = [
        {"source": "picam_docs", "loc": "invented", "quote": "The camera always works perfectly."}
    ]
    errors = _errors_for(tmp_path, data)
    assert any("not found verbatim" in e for e in errors), errors


def test_real_quote_accepted_whitespace_normalised(tmp_path: Path):
    sources = REPO_ROOT / "knowledge" / "sources" / "picam_docs.md"
    sentence = " ".join(sources.read_text(encoding="utf-8").split()[:6])
    data = _load(CAMERA)
    data["tests"][0]["checks"][0]["cites"] = [
        {"source": "picam_docs", "loc": "notes", "quote": sentence.replace(" ", "  ")}
    ]
    assert _errors_for(tmp_path, data) == []


def test_quote_is_case_sensitive(tmp_path: Path):
    sources = REPO_ROOT / "knowledge" / "sources" / "picam_docs.md"
    first_words = " ".join(sources.read_text(encoding="utf-8").split()[:4])
    data = _load(CAMERA)
    data["tests"][0]["checks"][0]["cites"] = [
        {"source": "picam_docs", "loc": "notes", "quote": first_words.lower()}
    ]
    errors = _errors_for(tmp_path, data)
    assert any("not found verbatim" in e for e in errors), errors


def test_cite_to_unknown_source_rejected(tmp_path: Path):
    data = _load(CAMERA)
    data["tests"][0]["checks"][0]["cites"] = [{"source": "nope", "loc": "x", "quote": None}]
    errors = _errors_for(tmp_path, data)
    assert any("not in this card's sources" in e for e in errors), errors


def test_unknown_guide_id_rejected(tmp_path: Path):
    data = _load(CAMERA)
    data["tests"][0]["checks"][0]["guide_id"] = "missing_guide"
    errors = _errors_for(tmp_path, data)
    assert any("missing_guide" in e for e in errors), errors


def test_help_offer_before_fault_rejected(tmp_path: Path):
    data = _load(CAMERA)
    data["tests"][0]["offer_help_after_ms"] = 100
    errors = _errors_for(tmp_path, data)
    assert any("offer_help_after_ms" in e and "earlier" in e for e in errors), errors


def test_image_paths_only_checked_on_request(tmp_path: Path):
    data = _load(CAMERA)
    assert _errors_for(tmp_path, data) == []
    data["guides"][0]["views"][0]["image"] = "knowledge/guides/camera_lens/nope.png"
    cards = _write_card(tmp_path, data)
    errors = validate_cards(cards, root=REPO_ROOT, check_images=True)
    assert any("missing" in e and "nope.png" in e for e in errors), errors


def test_file_stem_must_match_card_id(tmp_path: Path):
    data = _load(CAMERA)
    errors = _errors_for(tmp_path, data, name="renamed.json")
    assert any("file stem must equal card_id" in e for e in errors), errors


def test_cli_exit_one_with_errors(tmp_path: Path, capsys):
    data = copy.deepcopy(_load(CAMERA))
    data["tests"][0]["fact"]["line1"] = "CAMERA VIEW LOST!"
    cards = _write_card(tmp_path, data)
    assert main([str(cards)]) == 1
    out = capsys.readouterr().out
    assert "ERROR" in out and "FAILED" in out


@pytest.mark.parametrize("path", [CAMERA, SETUP])
def test_shipped_card_has_authored_provenance(path: Path):
    card = _load(path)
    assert card["provenance"] == "AUTHORED DEMO METADATA"
