"""Envelope validation, draft writing and the importer CLI. No network."""

from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from knowledge.importer import (
    MAX_ENVELOPE_BYTES,
    drafts_dir,
    main,
    validate_envelope,
    write_draft,
)
from knowledge.validate import REPO_ROOT

EXAMPLE = REPO_ROOT / "contracts" / "examples" / "card_camera_lens.json"
SOURCE_TEXT = (
    "The camera module connects through the CSI ribbon cable.\n"
    "If the image is black,   check that the lens   cap is removed."
)
QUOTE = "check that the lens cap is removed"


def make_envelope(*, quote: str | None = QUOTE) -> dict:
    card = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    card["provenance"] = "WEB TUTORIAL"
    card["sources"][0]["file"] = None
    for guide in card["guides"]:  # the contract example uses '=' in a fallback cue, which the house rules reject
        for view in guide["views"]:
            view["fallback"] = {"line1": "CHECK LENS COVER", "line2": "SEE PICTURE"}
    card["tests"][0]["checks"][0]["cites"] = [
        {"source": "picam_docs", "loc": "troubleshooting", "quote": quote, "url": "https://example.com/doc#lens"}
    ]
    return {
        "run_id": "run-001",
        "request": "camera view is black",
        "card": card,
        "source_texts": {"picam_docs": SOURCE_TEXT},
        "research": {
            "sources": [{"id": "picam_docs", "kind": "doc", "url": "https://example.com/doc", "used_for": "lens cap"}],
            "video_notes": [],
            "visual_references": [{"view": "where", "url": "https://example.com/img.png", "description": "lens"}],
            "uncertainties": [],
        },
    }


def errors_of(envelope) -> list[str]:
    result = validate_envelope(envelope, REPO_ROOT)
    assert result["ok"] == (result["errors"] == [])
    return result["errors"]


def test_valid_envelope_accepted_with_whitespace_normalised_quote():
    assert errors_of(make_envelope()) == []


def test_null_quote_needs_no_source_text():
    env = make_envelope(quote=None)
    env["source_texts"] = {}
    assert errors_of(env) == []


def test_shipped_camera_card_shape_is_accepted_after_stripping_repo_files():
    card = json.loads((REPO_ROOT / "knowledge" / "cards" / "camera_lens.json").read_text(encoding="utf-8"))
    for source in card["sources"]:
        source["file"] = None
    card["provenance"] = "MANUFACTURER DOC"
    env = make_envelope(quote=None)
    env["card"] = card
    assert errors_of(env) == []


def test_bad_glyph_rejected():
    env = make_envelope()
    env["card"]["tests"][0]["fact"]["line1"] = "CAMERA VIEW LOST!"
    assert any("characters not allowed" in e for e in errors_of(env))


def test_diagnosis_word_rejected():
    env = make_envelope()
    env["card"]["tests"][0]["fact"]["line2"] = "LENS IS COVERED"
    assert any("diagnosis" in e for e in errors_of(env))


def test_overlong_cue_rejected_by_schema():
    env = make_envelope()
    env["card"]["tests"][0]["fact"]["line1"] = "X" * 40
    assert any(e.startswith("card: [") for e in errors_of(env))


def test_unknown_signal_rejected():
    env = make_envelope()
    env["card"]["tests"][0]["fail_when"][0]["signal"] = "camera.nonexistent"
    assert any("unknown signal 'camera.nonexistent'" in e for e in errors_of(env))


def test_unknown_guide_id_rejected():
    env = make_envelope()
    env["card"]["tests"][0]["checks"][0]["guide_id"] = "missing_guide"
    assert any("missing_guide" in e for e in errors_of(env))


def test_fabricated_quote_rejected():
    env = make_envelope(quote="The camera always works perfectly.")
    assert any("not found verbatim" in e for e in errors_of(env))


def test_quote_is_case_sensitive():
    env = make_envelope(quote=QUOTE.upper())
    assert any("not found verbatim" in e for e in errors_of(env))


def test_quote_with_missing_source_text_rejected():
    env = make_envelope()
    env["source_texts"] = {}
    assert any("has no text" in e for e in errors_of(env))


def test_empty_quote_rejected():
    env = make_envelope(quote="   ")
    assert any("quote is empty" in e for e in errors_of(env))


def test_draft_cannot_claim_human_review():
    env = make_envelope()
    env["card"]["provenance"] = "AI-EXTRACTED · HUMAN-REVIEWED"
    assert any("cannot claim" in e for e in errors_of(env))


def test_non_http_urls_rejected():
    env = make_envelope()
    env["card"]["sources"][0]["url"] = "javascript:alert(1)"
    env["card"]["tests"][0]["checks"][0]["cites"][0]["url"] = "file:///etc/passwd"
    env["card"]["guides"][0]["views"][0]["reference_url"] = "ftp://x/y"
    env["research"]["sources"][0]["url"] = "data:text/html,x"
    errors = errors_of(env)
    assert sum("must be http(s)" in e for e in errors) == 4, errors


def test_source_file_and_image_traversal_rejected():
    env = make_envelope()
    env["card"]["sources"][0]["file"] = "docs/PIVOT_GHOSTBUILD.md"
    env["card"]["guides"][0]["views"][0]["image"] = "../../etc/passwd"
    env["card"]["guides"][0]["views"][0]["phone_image"] = "/abs/path.png"
    errors = errors_of(env)
    assert any("file must be null" in e for e in errors)
    assert sum("unsafe path" in e for e in errors) == 2, errors


@pytest.mark.parametrize("bad", ["../evil", "a/b", "Upper", "x" * 80, "", "a b", ".hidden"])
def test_traversal_or_unsafe_card_id_rejected(bad):
    env = make_envelope()
    env["card"]["card_id"] = bad
    assert any("card.card_id" in e for e in errors_of(env))


def test_unsafe_source_id_rejected():
    env = make_envelope(quote=None)
    env["card"]["sources"][0]["id"] = "../x"
    assert any("id must match" in e for e in errors_of(env))


def test_oversize_rejected():
    env = make_envelope()
    env["source_texts"]["picam_docs"] = "x" * (MAX_ENVELOPE_BYTES + 1)
    assert any("exceeds" in e for e in errors_of(env))


@pytest.mark.parametrize(
    "mutate,needle",
    [
        (lambda e: e.pop("run_id"), "run_id"),
        (lambda e: e.pop("request"), "request"),
        (lambda e: e.update(card="x"), "card"),
        (lambda e: e.pop("source_texts"), "source_texts"),
        (lambda e: e.update(source_texts={"a": 1}), "source_texts"),
        (lambda e: e.pop("research"), "research"),
        (lambda e: e["research"].update(sources="no"), "research.sources"),
        (lambda e: e["research"].update(uncertainties={}), "uncertainties"),
    ],
)
def test_envelope_shape_rejected(mutate, needle):
    env = make_envelope()
    mutate(env)
    assert any(needle in e for e in errors_of(env))


@pytest.mark.parametrize("junk", [None, [], "text", 3])
def test_non_object_envelope_rejected(junk):
    assert errors_of(junk)


def test_write_draft_layout_and_id():
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        now = datetime(2026, 10, 17, 21, 5, 9, tzinfo=timezone.utc)
        env = make_envelope()
        draft_id = write_draft(env, tmp, now=now)
        assert draft_id == "camera_lens-20261017T210509"
        base = drafts_dir(tmp) / draft_id
        assert json.loads((base / "envelope.json").read_text(encoding="utf-8")) == env
        assert json.loads((base / "card.json").read_text(encoding="utf-8")) == env["card"]
        assert write_draft(env, tmp, now=now) == "camera_lens-20261017T210509-2"
        assert not (Path(tmp) / "knowledge" / "cards").exists()


def test_write_draft_refuses_invalid():
    import tempfile

    env = make_envelope(quote="invented sentence")
    with tempfile.TemporaryDirectory() as tmp, pytest.raises(ValueError):
        write_draft(env, tmp)


def test_cli_writes_draft(tmp_path, capsys):
    f = tmp_path / "env.json"
    f.write_text(json.dumps(make_envelope()), encoding="utf-8")
    assert main([str(f), "--root", str(tmp_path / "root")]) == 0
    out = capsys.readouterr().out
    assert "OK: draft camera_lens-" in out
    assert len(list(drafts_dir(tmp_path / "root").iterdir())) == 1


def test_cli_rejects_invalid_and_unreadable(tmp_path, capsys):
    env = make_envelope(quote="made up")
    f = tmp_path / "env.json"
    f.write_text(json.dumps(env), encoding="utf-8")
    assert main([str(f), "--root", str(tmp_path / "root")]) == 1
    assert "FAILED" in capsys.readouterr().out
    assert not drafts_dir(tmp_path / "root").exists()
    assert main([str(tmp_path / "missing.json"), "--root", str(tmp_path)]) == 1
    junk = tmp_path / "junk.json"
    junk.write_text("{not json", encoding="utf-8")
    assert main([str(junk), "--root", str(tmp_path)]) == 1


def test_cli_rejects_oversize_file(tmp_path, capsys):
    f = tmp_path / "big.json"
    f.write_text(" " * (MAX_ENVELOPE_BYTES + 10), encoding="utf-8")
    assert main([str(f), "--root", str(tmp_path)]) == 1


def test_validation_does_not_mutate_input():
    env = make_envelope()
    before = copy.deepcopy(env)
    validate_envelope(env, REPO_ROOT)
    assert env == before
