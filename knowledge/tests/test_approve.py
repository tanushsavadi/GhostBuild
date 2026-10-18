"""Approval flow: re-validation, dry run, provenance rewrite, hand-authored protection, review log."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pytest

from knowledge.approve import main as approve
from knowledge.importer import drafts_dir, write_draft
from knowledge.validate import REPO_ROOT, validate_cards

from test_importer import make_envelope


@pytest.fixture
def root(tmp_path) -> Path:
    """A scratch repo root with the real card dir copied in (so we can test overwrite rules safely)."""
    shutil.copytree(REPO_ROOT / "knowledge" / "cards", tmp_path / "knowledge" / "cards")
    shutil.copytree(REPO_ROOT / "knowledge" / "sources", tmp_path / "knowledge" / "sources")
    (tmp_path / "docs").mkdir()
    shutil.copy(REPO_ROOT / "docs" / "PIVOT_GHOSTBUILD.md", tmp_path / "docs" / "PIVOT_GHOSTBUILD.md")
    return tmp_path


def new_draft(root: Path, card_id: str = "lens_demo", **kw) -> str:
    env = make_envelope(**kw)
    env["card"]["card_id"] = card_id
    return write_draft(env, root, now=datetime(2026, 10, 17, 22, 0, 0, tzinfo=timezone.utc))


def test_approve_new_card_end_to_end(root, capsys):
    draft_id = new_draft(root)
    assert approve([draft_id, "--reviewer", "Tanush", "--root", str(root)]) == 0
    out = capsys.readouterr().out
    assert "(new card)" in out and "APPROVED" in out

    card = json.loads((root / "knowledge" / "cards" / "lens_demo.json").read_text(encoding="utf-8"))
    assert card["provenance"] == "AI-EXTRACTED · HUMAN-REVIEWED"
    assert card["sources"][0]["file"] == "knowledge/sources/lens_demo__picam_docs.md"
    assert (root / card["sources"][0]["file"]).is_file()

    # the shared validator (what `make test` runs) accepts the approved card, quote re-checked against the stored file
    assert validate_cards(root / "knowledge" / "cards", root=root) == []

    review = json.loads((drafts_dir(root) / draft_id / "review.json").read_text(encoding="utf-8"))
    assert review["reviewer"] == "Tanush" and review["validator_ok"] is True and review["at"]


def test_draft_provenance_untouched_until_approval(root):
    draft_id = new_draft(root)
    draft_card = json.loads((drafts_dir(root) / draft_id / "card.json").read_text(encoding="utf-8"))
    assert draft_card["provenance"] != "AI-EXTRACTED · HUMAN-REVIEWED"
    assert not (root / "knowledge" / "cards" / "lens_demo.json").exists()


def test_dry_run_writes_nothing(root, capsys):
    draft_id = new_draft(root)
    assert approve([draft_id, "--reviewer", "T", "--dry-run", "--root", str(root)]) == 0
    assert "DRY RUN" in capsys.readouterr().out
    assert not (root / "knowledge" / "cards" / "lens_demo.json").exists()
    assert not (drafts_dir(root) / draft_id / "review.json").exists()


def test_reviewer_is_required(root):
    draft_id = new_draft(root)
    with pytest.raises(SystemExit):
        approve([draft_id, "--root", str(root)])
    assert approve([draft_id, "--reviewer", "  ", "--root", str(root)]) == 1


def test_refuses_when_draft_tampered_after_import(root, capsys):
    draft_id = new_draft(root)
    path = drafts_dir(root) / draft_id / "envelope.json"
    env = json.loads(path.read_text(encoding="utf-8"))
    env["card"]["tests"][0]["checks"][0]["cites"][0]["quote"] = "fabricated after the fact"
    path.write_text(json.dumps(env), encoding="utf-8")
    assert approve([draft_id, "--reviewer", "T", "--root", str(root)]) == 1
    assert "REFUSED" in capsys.readouterr().out
    assert not (root / "knowledge" / "cards" / "lens_demo.json").exists()
    assert not (drafts_dir(root) / draft_id / "review.json").exists()


def test_authored_card_not_overwritten_without_force(root, capsys):
    before = (root / "knowledge" / "cards" / "camera_lens.json").read_text(encoding="utf-8")
    draft_id = new_draft(root, card_id="camera_lens")
    assert approve([draft_id, "--reviewer", "T", "--root", str(root)]) == 1
    out = capsys.readouterr().out
    assert "hand-authored" in out and "--force" in out
    assert "--- knowledge/cards/camera_lens.json (existing)" in out  # the diff is still shown
    assert (root / "knowledge" / "cards" / "camera_lens.json").read_text(encoding="utf-8") == before
    assert not (drafts_dir(root) / draft_id / "review.json").exists()


def test_force_overwrites_authored_card(root):
    draft_id = new_draft(root, card_id="camera_lens")
    assert approve([draft_id, "--reviewer", "T", "--force", "--root", str(root)]) == 0
    card = json.loads((root / "knowledge" / "cards" / "camera_lens.json").read_text(encoding="utf-8"))
    assert card["provenance"] == "AI-EXTRACTED · HUMAN-REVIEWED"


def test_reviewed_card_can_be_replaced_without_force(root):
    first = new_draft(root)
    assert approve([first, "--reviewer", "A", "--root", str(root)]) == 0
    second = write_draft(
        {**make_envelope(quote=None), "card": {**make_envelope(quote=None)["card"], "card_id": "lens_demo"}},
        root,
        now=datetime(2026, 10, 17, 23, 0, 0, tzinfo=timezone.utc),
    )
    assert approve([second, "--reviewer", "B", "--root", str(root)]) == 0


@pytest.mark.parametrize("bad", ["../../etc/passwd", "lens_demo", "x/../y", ""])
def test_bad_or_missing_draft_id(root, bad):
    assert approve([bad, "--reviewer", "T", "--root", str(root)]) == 1


def test_diff_shows_changes_against_existing(root, capsys):
    first = new_draft(root)
    approve([first, "--reviewer", "A", "--root", str(root)])
    capsys.readouterr()
    env = make_envelope()
    env["card"]["card_id"] = "lens_demo"
    env["card"]["title"] = "Changed title"
    second = write_draft(env, root, now=datetime(2026, 10, 17, 23, 30, 0, tzinfo=timezone.utc))
    assert approve([second, "--reviewer", "B", "--dry-run", "--root", str(root)]) == 0
    out = capsys.readouterr().out
    assert '+  "title": "Changed title"' in out
