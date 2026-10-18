"""Import a draft Repair Card envelope (from the research agent) as a DRAFT. Never touches knowledge/cards/.

Usage (no network; the file is whatever a human saved from the agent run):
    uv run python -m knowledge.importer FILE.json [--root DIR]

Envelope shape (docs/sponsors/CREAO_AGENT_BRIEF.md):
    {run_id, request, card, source_texts{source_id: text}, research{sources, video_notes, visual_references, uncertainties}}

validate_envelope applies the same rules knowledge/validate.py applies to shipped cards (schema, glyphs and length,
signals exist, guide ids resolve, no diagnosis words, playbook step rules) plus the draft-only rules: verbatim quotes against the supplied
source_texts, http(s) URLs only, safe ids and paths, 1 MB cap. Nothing here fetches a URL.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from contracts.models import Card
from knowledge.validate import REPO_ROOT, _check_card, _normalise, iter_checks

MAX_ENVELOPE_BYTES = 1_000_000  # 1 MB

SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
SAFE_SOURCE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
DRAFT_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}-\d{8}T\d{6}(?:-\d{1,3})?$")
HTTP_URL = re.compile(r"^https?://[^\s/$.?#][^\s]*$", re.IGNORECASE)
REVIEWED = "AI-EXTRACTED · HUMAN-REVIEWED"
RESEARCH_LISTS = ("sources", "video_notes", "visual_references", "uncertainties")


def drafts_dir(root: Path | str = REPO_ROOT) -> Path:
    return Path(root) / "knowledge" / "drafts"


def is_http_url(value: object) -> bool:
    return isinstance(value, str) and HTTP_URL.match(value) is not None


def safe_relative_path(value: str) -> bool:
    """Repo-relative path with no traversal, no absolute path, no backslash tricks."""
    if not value or value.startswith(("/", "~")) or "\\" in value or "\x00" in value:
        return False
    return all(part not in ("", ".", "..") for part in value.split("/"))


def _shape_errors(envelope: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(envelope, dict):
        return ["envelope: must be a JSON object"]
    for key in ("run_id", "request"):
        if not isinstance(envelope.get(key), str) or not envelope[key].strip():
            errors.append(f"envelope.{key}: required non-empty string")
    if not isinstance(envelope.get("card"), dict):
        errors.append("envelope.card: required object")
    texts = envelope.get("source_texts")
    if not isinstance(texts, dict):
        errors.append("envelope.source_texts: required object {source_id: text}")
    else:
        for key, value in texts.items():
            if not isinstance(key, str) or not isinstance(value, str):
                errors.append(f"envelope.source_texts[{key!r}]: key and value must be strings")
    research = envelope.get("research")
    if not isinstance(research, dict):
        errors.append("envelope.research: required object")
        return errors
    if "sources" not in research:
        errors.append("envelope.research.sources: required list")
    for name in RESEARCH_LISTS:
        if name in research and not isinstance(research[name], list):
            errors.append(f"envelope.research.{name}: must be a list")
    for name in ("sources", "video_notes", "visual_references"):
        items = research.get(name)
        if not isinstance(items, list):
            continue
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                errors.append(f"envelope.research.{name}[{index}]: must be an object")
                continue
            url = item.get("url")
            if url not in (None, "") and not is_http_url(url):
                errors.append(f"envelope.research.{name}[{index}].url: must be http(s): {url!r}")
    return errors


def _card_errors(card_raw: dict, source_texts: dict, root: Path) -> list[str]:
    errors: list[str] = []
    card_id = card_raw.get("card_id")
    if not isinstance(card_id, str) or not SAFE_ID.match(card_id):
        errors.append(f"card.card_id: must match {SAFE_ID.pattern}: {card_id!r}")
        return errors

    try:
        card = Card.model_validate(card_raw)
    except ValidationError as exc:
        for item in exc.errors():
            loc = ".".join(str(part) for part in item["loc"]) or "(root)"
            errors.append(f"card: [{loc}] {item['msg']}")
        return errors

    if card.provenance == REVIEWED:
        errors.append(f"card.provenance: a draft cannot claim {REVIEWED!r}; only knowledge.approve sets it")

    for index, source in enumerate(card.sources):
        where = f"card.sources[{index}]({source.id})"
        if not SAFE_SOURCE_ID.match(source.id):
            errors.append(f"{where}: id must match {SAFE_SOURCE_ID.pattern}")
        if source.file is not None:
            errors.append(f"{where}: file must be null in a draft (approval stores source_texts as the file)")
        if source.url is not None and not is_http_url(source.url):
            errors.append(f"{where}: url must be http(s): {source.url!r}")

    for guide in card.guides:
        for view in guide.views:
            for field_name in ("image", "phone_image"):
                path = getattr(view, field_name)
                if path is not None and not safe_relative_path(path):
                    errors.append(f"card.guides[{guide.id}].{view.view}.{field_name}: unsafe path {path!r}")
            if view.reference_url is not None and not is_http_url(view.reference_url):
                errors.append(f"card.guides[{guide.id}].{view.view}.reference_url: must be http(s): {view.reference_url!r}")

    source_ids = {s.id for s in card.sources}
    for check_where, check in iter_checks(card):
        for ki, cite in enumerate(check.cites):
            where = f"card.{check_where}.cites[{ki}]"
            if cite.url is not None and not is_http_url(cite.url):
                errors.append(f"{where}: url must be http(s): {cite.url!r}")
            if cite.source not in source_ids:
                continue  # reported by the shared house rules below
            if cite.quote is None:
                continue
            text = source_texts.get(cite.source)
            if text is None:
                errors.append(f"{where}: quote given but envelope.source_texts has no text for {cite.source!r}")
                continue
            needle = _normalise(cite.quote)
            if not needle:
                errors.append(f"{where}: quote is empty")
            elif needle not in _normalise(text):
                errors.append(f"{where}: quote not found verbatim in source_texts[{cite.source!r}]: {cite.quote!r}")

    # Shared house rules on a quote-free, file-free copy: the quote check above is the envelope's version of it.
    rules_raw = copy.deepcopy(card_raw)
    for source in rules_raw.get("sources", []):
        source["file"] = None
    for test in rules_raw.get("tests", []):
        for check in test.get("checks", []):
            for cite in check.get("cites", []):
                cite["quote"] = None
    for step in rules_raw.get("steps", []):
        for check in step.get("troubleshoot", []):
            for cite in check.get("cites", []):
                cite["quote"] = None
    rules_card = Card.model_validate(rules_raw)
    errors.extend(_check_card(rules_card, Path(f"{card_id}.json"), root, False))
    return errors


def validate_envelope(envelope: Any, root: Path | str = REPO_ROOT) -> dict:
    """Return {"ok": bool, "errors": [str]}. Never raises on bad input."""
    try:
        size = len(json.dumps(envelope, ensure_ascii=False).encode("utf-8"))
    except (TypeError, ValueError) as exc:
        return {"ok": False, "errors": [f"envelope: not JSON-serialisable: {exc}"]}
    if size > MAX_ENVELOPE_BYTES:
        return {"ok": False, "errors": [f"envelope: {size} bytes exceeds the {MAX_ENVELOPE_BYTES} byte cap"]}
    errors = _shape_errors(envelope)
    if isinstance(envelope, dict) and isinstance(envelope.get("card"), dict) and isinstance(envelope.get("source_texts"), dict):
        errors.extend(_card_errors(envelope["card"], envelope["source_texts"], Path(root)))
    return {"ok": not errors, "errors": errors}


def write_draft(envelope: dict, root: Path | str = REPO_ROOT, now: datetime | None = None) -> str:
    """Validate and store as knowledge/drafts/<draft_id>/{envelope.json,card.json}. Raises ValueError if invalid."""
    result = validate_envelope(envelope, root)
    if not result["ok"]:
        raise ValueError("; ".join(result["errors"][:5]))
    card_id = envelope["card"]["card_id"]
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%S")
    base = drafts_dir(root)
    base.mkdir(parents=True, exist_ok=True)
    draft_id = f"{card_id}-{stamp}"
    suffix = 1
    while True:
        try:
            (base / draft_id).mkdir()
            break
        except FileExistsError:
            suffix += 1
            draft_id = f"{card_id}-{stamp}-{suffix}"
    target = base / draft_id
    (target / "envelope.json").write_text(json.dumps(envelope, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (target / "card.json").write_text(json.dumps(envelope["card"], indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return draft_id


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a research-agent envelope file and store it as a draft.")
    parser.add_argument("file", help="envelope JSON file")
    parser.add_argument("--root", default=str(REPO_ROOT), help="repo root (default: this checkout)")
    args = parser.parse_args(argv)
    path = Path(args.file)
    try:
        if path.stat().st_size > MAX_ENVELOPE_BYTES:
            print(f"ERROR {path}: larger than {MAX_ENVELOPE_BYTES} bytes")
            return 1
        envelope = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"ERROR {path}: not readable JSON: {exc}")
        return 1
    result = validate_envelope(envelope, args.root)
    if not result["ok"]:
        for error in result["errors"]:
            print(f"ERROR {error}")
        print(f"FAILED: {len(result['errors'])} error(s); no draft written")
        return 1
    draft_id = write_draft(envelope, args.root)
    print(f"OK: draft {draft_id} written to {drafts_dir(args.root) / draft_id}")
    print(f"Review it, then: python -m knowledge.approve {draft_id} --reviewer <name> [--dry-run]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
