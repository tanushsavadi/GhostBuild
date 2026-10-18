"""Human approval of a draft card: python -m knowledge.approve <draft_id> --reviewer <name> [--dry-run] [--force]

Re-validates the draft envelope, prints a diff against any existing knowledge/cards/<card_id>.json, then (unless
--dry-run) writes the card with provenance 'AI-EXTRACTED · HUMAN-REVIEWED', stores each source_text as
knowledge/sources/<card_id>__<source_id>.md so the shared validator can re-check every quote, and logs the review in
knowledge/drafts/<draft_id>/review.json. A hand-authored card (provenance 'AUTHORED DEMO METADATA') is never
overwritten without --force. Guide images are not created here; a human adds them (cards fall back to text cues).
"""

from __future__ import annotations

import argparse
import copy
import difflib
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from contracts.models import Card
from knowledge.importer import DRAFT_ID, REVIEWED, drafts_dir, validate_envelope
from knowledge.validate import REPO_ROOT, _check_card

AUTHORED = "AUTHORED DEMO METADATA"


def source_rel_path(card_id: str, source_id: str) -> str:
    return f"knowledge/sources/{card_id}__{source_id}.md"


def build_final_card(envelope: dict) -> tuple[dict, dict[str, str]]:
    """Return (card dict ready for knowledge/cards, {repo-relative path: text}) from a validated envelope."""
    card = copy.deepcopy(envelope["card"])
    card["provenance"] = REVIEWED
    files: dict[str, str] = {}
    for source in card["sources"]:
        text = envelope["source_texts"].get(source["id"])
        if text is not None:
            rel = source_rel_path(card["card_id"], source["id"])
            source["file"] = rel
            files[rel] = text
    return card, files


def _final_errors(card: dict, files: dict[str, str]) -> list[str]:
    """Run the shared validator rules (including quote-against-file) on the final card in a scratch root."""
    with tempfile.TemporaryDirectory() as tmp:
        scratch = Path(tmp)
        for rel, text in files.items():
            target = scratch / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        parsed = Card.model_validate(card)
        return _check_card(parsed, Path(f"{parsed.card_id}.json"), scratch, False)


def _pretty(data: dict) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Approve a draft Repair Card into knowledge/cards/.")
    parser.add_argument("draft_id")
    parser.add_argument("--reviewer", required=True, help="name of the human who reviewed the diff")
    parser.add_argument("--dry-run", action="store_true", help="validate and print the diff; write nothing")
    parser.add_argument("--force", action="store_true", help="allow overwriting a hand-authored card")
    parser.add_argument("--root", default=str(REPO_ROOT), help="repo root (default: this checkout)")
    args = parser.parse_args(argv)

    root = Path(args.root)
    reviewer = args.reviewer.strip()
    if not reviewer:
        print("ERROR --reviewer must be a non-empty name")
        return 1
    if not DRAFT_ID.match(args.draft_id):
        print(f"ERROR invalid draft id {args.draft_id!r}")
        return 1
    draft_dir = drafts_dir(root) / args.draft_id
    envelope_path = draft_dir / "envelope.json"
    try:
        envelope = json.loads(envelope_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"ERROR cannot read {envelope_path}: {exc}")
        return 1

    result = validate_envelope(envelope, root)
    if not result["ok"]:
        for error in result["errors"]:
            print(f"ERROR {error}")
        print("REFUSED: draft no longer validates; nothing written")
        return 1

    card, files = build_final_card(envelope)
    errors = _final_errors(card, files)
    if errors:
        for error in errors:
            print(f"ERROR {error}")
        print("REFUSED: approved form of the card does not validate; nothing written")
        return 1

    card_id = card["card_id"]
    target = root / "knowledge" / "cards" / f"{card_id}.json"
    old_text = ""
    existing_provenance = None
    if target.is_file():
        old_text = target.read_text(encoding="utf-8")
        try:
            existing_provenance = json.loads(old_text).get("provenance")
        except ValueError:
            existing_provenance = None
    new_text = _pretty(card)
    diff = list(
        difflib.unified_diff(
            old_text.splitlines(keepends=True),
            new_text.splitlines(keepends=True),
            fromfile=f"knowledge/cards/{card_id}.json (existing)" if old_text else "(new card)",
            tofile=f"knowledge/cards/{card_id}.json (approved draft {args.draft_id})",
        )
    )
    print("".join(diff) if diff else "(no difference from the existing card)")
    for rel in sorted(files):
        print(f"+ source file: {rel} ({len(files[rel])} chars)")

    if existing_provenance == AUTHORED and not args.force:
        print(f"REFUSED: knowledge/cards/{card_id}.json is hand-authored ({AUTHORED}); re-run with --force to overwrite")
        return 1
    if args.dry_run:
        print("DRY RUN: nothing written")
        return 0

    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(new_text, encoding="utf-8")
    review = {
        "reviewer": reviewer,
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "validator_ok": True,
    }
    (draft_dir / "review.json").write_text(json.dumps(review, indent=2) + "\n", encoding="utf-8")
    print(f"APPROVED: wrote {target} (reviewer {reviewer}); run `make test` before committing")
    return 0


if __name__ == "__main__":
    sys.exit(main())
