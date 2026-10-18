"""Validate Repair Cards (knowledge/cards/*.json) against contracts.models.Card and the house rules.

Usage:
    uv run python -m knowledge.validate [cards_dir] [--check-images]

Exit 0 when every card is valid, 1 with readable errors otherwise.

Rules beyond the Card schema:
- Cue text: upper case; only A-Z 0-9 space and . - / ' · plus ● (the status marker used by ok cues).
  Playbook step text (Card.steps) may also use , : ? ! ( ) + = (all plain ASCII, so g2/src/glyphs.ts passes them
  through). The check mark is NOT allowed: the plugin folds it to the letters OK.
- Cue text never reads as a diagnosis: no IS, ARE, BROKEN, DEAD or FAULTY as whole words (steps also: WRONG, BAD,
  DEFECTIVE, DAMAGED).
- Playbooks (Card.steps): unique step ids; `requires` names EARLIER steps; step/troubleshoot guide_id names a guide of the
  card; every verify.when / troubleshoot.when signal exists on Observation; verify may only use ALLOWED_VERIFY_SIGNALS;
  a manual step (no verify) never says VERIFIED or CORRECT; a LED-command verify never says VERIFIED; faq questions are
  lowercase; troubleshoot cites follow the same verbatim-quote rule as fault checks.
- Alias strings are unique per goal_mode across the cards directory (the resolver would be ambiguous otherwise).
- Predicate.signal must be a real path into contracts.models.Observation (e.g. camera.mean_luma).
- Numeric predicate values sit inside the physical range of the signal; op/value shapes match.
- offer_help_after_ms is not earlier than fail_after_ms; functional within_ms is positive.
- Every Check.guide_id names a guide in the same card; aliases are lowercase; file stem == card_id.
- Every Cite.source names a source of the card. A non-null Cite.quote must appear verbatim
  (whitespace-normalised, case-sensitive) in that source's file under knowledge/sources or the repo.
- Source files referenced by a card must exist. With --check-images, GuideView image paths must exist.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import types
import typing
from pathlib import Path

from pydantic import BaseModel, ValidationError

from contracts.models import Card, Check, Cue, Observation, Step

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CARDS_DIR = REPO_ROOT / "knowledge" / "cards"

CUE_GLYPHS = re.compile(r"^[A-Z0-9 .\-/'·●]*$")
# Playbook step text: the same set plus plain-ASCII punctuation. Deliberately no check mark: g2/src/glyphs.ts folds it to "OK".
STEP_GLYPHS = re.compile(r"^[A-Z0-9 .\-/'·●,:?!()+=]*$")
DIAGNOSIS = re.compile(r"\b(IS|ARE|BROKEN|DEAD|FAULTY)\b")
STEP_DIAGNOSIS = re.compile(r"\b(IS|ARE|BROKEN|DEAD|FAULTY|WRONG|BAD|DEFECTIVE|DAMAGED)\b")
MANUAL_FORBIDDEN = re.compile(r"\b(VERIFIED|CORRECT)\b")
# Telemetry a Pi station actually reports (docs/sponsors/CREAO_AGENT_BRIEF.md). A step `verify` may use only these.
ALLOWED_VERIFY_SIGNALS = frozenset(
    {
        "camera.mean_luma",
        "camera.luma_std",
        "camera.detail",
        "camera.motion",
        "camera.frame_seq",
        "camera.frame_age_ms",
        "led.commanded_on",
    }
)

# Physical ranges of Observation signals (contracts/models.py CameraObs). Numeric predicates must fit.
SIGNAL_RANGES: dict[str, tuple[float, float | None]] = {
    "camera.mean_luma": (0, 255),
    "camera.luma_std": (0, None),
    "camera.detail": (0, None),
    "camera.motion": (0, 1),
    "camera.frame_seq": (0, None),
    "camera.frame_age_ms": (0, None),
}


def _model_of(annotation: object) -> type[BaseModel] | None:
    """Return the BaseModel behind an annotation, unwrapping Optional/Union."""
    origin = typing.get_origin(annotation)
    if origin in (typing.Union, types.UnionType):
        for arg in typing.get_args(annotation):
            if arg is type(None):
                continue
            model = _model_of(arg)
            if model is not None:
                return model
        return None
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation
    return None


def resolve_signal(signal: str) -> tuple[str | None, bool]:
    """Walk Observation fields along a dotted path.

    Returns (error, leaf_is_model). error is None when the path exists.
    """
    current: type[BaseModel] = Observation
    parts = signal.split(".")
    for index, part in enumerate(parts):
        fields = current.model_fields
        if part not in fields:
            where = ".".join(parts[:index]) or "Observation"
            return f"no field '{part}' under {where}", False
        annotation = fields[part].annotation
        nested = _model_of(annotation)
        if index == len(parts) - 1:
            return None, nested is not None
        if nested is None:
            return f"'{part}' is a scalar, cannot descend into it", False
        current = nested
    return "empty signal", False


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _iter_cues(card: Card) -> list[tuple[str, Cue, bool]]:
    """(where, cue, is_step_text). Step text may use the wider glyph set and the wider diagnosis word list."""
    cues: list[tuple[str, Cue, bool]] = []
    for ti, test in enumerate(card.tests):
        base = f"tests[{ti}]({test.id})"
        cues.append((f"{base}.fact", test.fact, False))
        cues.append((f"{base}.ok", test.ok, False))
        for ci, check in enumerate(test.checks):
            cues.append((f"{base}.checks[{ci}].action", check.action, False))
    if card.functional is not None:
        cues.append(("functional.prompt", card.functional.prompt, False))
        cues.append(("functional.ok", card.functional.ok, False))
    for gi, guide in enumerate(card.guides):
        for vi, view in enumerate(guide.views):
            cues.append((f"guides[{gi}].views[{vi}].fallback", view.fallback, False))
    for si, step in enumerate(card.steps):
        for where, cue in _step_cues(step, f"steps[{si}]({step.id})"):
            cues.append((where, cue, True))
    return cues


def _step_cues(step: Step, base: str) -> list[tuple[str, Cue]]:
    cues: list[tuple[str, Cue]] = [(f"{base}.cue", step.cue)]
    if step.why is not None:
        cues.append((f"{base}.why", step.why))
    if step.where is not None:
        cues.append((f"{base}.where", step.where))
    for fi, faq in enumerate(step.faq):
        cues.append((f"{base}.faq[{fi}].a", faq.a))
    for ci, check in enumerate(step.troubleshoot):
        cues.append((f"{base}.troubleshoot[{ci}].action", check.action))
    if step.verify is not None:
        cues.append((f"{base}.verify.ok", step.verify.ok))
    return cues


def iter_checks(card: Card) -> list[tuple[str, Check]]:
    """Every Check in the card: fault-test checks and playbook troubleshoot entries."""
    checks: list[tuple[str, Check]] = []
    for ti, test in enumerate(card.tests):
        for ci, check in enumerate(test.checks):
            checks.append((f"tests[{ti}]({test.id}).checks[{ci}]", check))
    for si, step in enumerate(card.steps):
        for ci, check in enumerate(step.troubleshoot):
            checks.append((f"steps[{si}]({step.id}).troubleshoot[{ci}]", check))
    return checks


def _iter_predicates(card: Card) -> list[tuple[str, object]]:
    preds: list[tuple[str, object]] = []
    for ti, test in enumerate(card.tests):
        for pi, pred in enumerate(test.fail_when):
            preds.append((f"tests[{ti}]({test.id}).fail_when[{pi}]", pred))
        for ci, check in enumerate(test.checks):
            for pi, pred in enumerate(check.when):
                preds.append((f"tests[{ti}]({test.id}).checks[{ci}].when[{pi}]", pred))
    if card.functional is not None:
        for pi, pred in enumerate(card.functional.trigger):
            preds.append((f"functional.trigger[{pi}]", pred))
        if card.functional.expect_commanded is not None:
            preds.append(("functional.expect_commanded", card.functional.expect_commanded))
    for si, step in enumerate(card.steps):
        base = f"steps[{si}]({step.id})"
        if step.verify is not None:
            for pi, pred in enumerate(step.verify.when):
                preds.append((f"{base}.verify.when[{pi}]", pred))
        for ci, check in enumerate(step.troubleshoot):
            for pi, pred in enumerate(check.when):
                preds.append((f"{base}.troubleshoot[{ci}].when[{pi}]", pred))
    return preds


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _resolve_repo_path(relative: str, root: Path) -> Path:
    return root / relative


def _check_cue(where: str, cue: Cue, step_text: bool = False) -> list[str]:
    errors: list[str] = []
    glyphs = STEP_GLYPHS if step_text else CUE_GLYPHS
    diagnosis = STEP_DIAGNOSIS if step_text else DIAGNOSIS
    for line_name, text in (("line1", cue.line1), ("line2", cue.line2)):
        if not text:
            continue
        if text != text.upper():
            errors.append(f"{where}.{line_name}: cue must be upper case: {text!r}")
        if not glyphs.match(text):
            bad = sorted({c for c in text if not glyphs.match(c)})
            hint = " (the G2 plugin folds the check mark to the letters OK; write OK or DONE)" if "✓" in bad else ""
            errors.append(f"{where}.{line_name}: characters not allowed on G2 {bad}: {text!r}{hint}")
        found = diagnosis.search(text)
        if found:
            errors.append(
                f"{where}.{line_name}: reads as a diagnosis ({found.group(0)}); use CHECK ... wording: {text!r}"
            )
    return errors


def _check_predicate(where: str, pred: object) -> list[str]:
    errors: list[str] = []
    signal = pred.signal  # type: ignore[attr-defined]
    op = pred.op  # type: ignore[attr-defined]
    value = pred.value  # type: ignore[attr-defined]

    path_error, leaf_is_model = resolve_signal(signal)
    if path_error:
        errors.append(f"{where}: unknown signal {signal!r}: {path_error}")
        return errors

    if op in ("is_null", "not_null"):
        if value is not None:
            errors.append(f"{where}: op {op} takes no value, got {value!r}")
        return errors

    if leaf_is_model:
        errors.append(f"{where}: signal {signal!r} is a group, op {op} needs a scalar signal")
        return errors

    if value is None:
        errors.append(f"{where}: op {op} on {signal!r} needs a value")
        return errors

    if op in ("lt", "gt"):
        if not _is_number(value):
            errors.append(f"{where}: op {op} on {signal!r} needs a number, got {value!r}")
            return errors
        if signal in SIGNAL_RANGES:
            low, high = SIGNAL_RANGES[signal]
            if value < low or (high is not None and value > high):
                upper = "inf" if high is None else high
                errors.append(
                    f"{where}: {signal} threshold {value} outside physical range [{low}, {upper}]"
                )
    return errors


def _check_card(card: Card, path: Path, root: Path, check_images: bool) -> list[str]:
    errors: list[str] = []
    label = path.name

    if path.stem != card.card_id:
        errors.append(f"{label}: file stem must equal card_id {card.card_id!r}")

    for alias in card.aliases:
        if alias != alias.strip().lower() or not alias.strip():
            errors.append(f"{label}: alias must be non-empty lowercase: {alias!r}")

    source_files: dict[str, Path | None] = {}
    for source in card.sources:
        if source.file is not None:
            source_path = _resolve_repo_path(source.file, root)
            if not source_path.is_file():
                errors.append(f"{label}: source {source.id!r} file missing: {source.file}")
            source_files[source.id] = source_path
        else:
            source_files[source.id] = None

    test_ids = [t.id for t in card.tests]
    for dup in sorted({t for t in test_ids if test_ids.count(t) > 1}):
        errors.append(f"{label}: duplicate test id {dup!r}")

    guide_ids = {g.id for g in card.guides}
    for ti, test in enumerate(card.tests):
        if test.offer_help_after_ms < test.fail_after_ms:
            errors.append(
                f"{label}: tests[{ti}]({test.id}) offer_help_after_ms "
                f"({test.offer_help_after_ms}) is earlier than fail_after_ms ({test.fail_after_ms})"
            )
    for where, check in iter_checks(card):
        if check.guide_id is not None and check.guide_id not in guide_ids:
            errors.append(f"{label}: {where} guide_id {check.guide_id!r} is not a guide of this card")
        for cite_index, cite in enumerate(check.cites):
            errors.extend(_check_cite(f"{label}: {where}.cites[{cite_index}]", cite, card, source_files))

    errors.extend(_check_steps(label, card, guide_ids))

    if card.functional is not None and card.functional.within_ms <= 0:
        errors.append(f"{label}: functional within_ms must be positive")

    for where, cue, step_text in _iter_cues(card):
        errors.extend(_check_cue(f"{label}: {where}", cue, step_text))

    for where, pred in _iter_predicates(card):
        errors.extend(_check_predicate(f"{label}: {where}", pred))

    for gi, guide in enumerate(card.guides):
        for vi, view in enumerate(guide.views):
            if not check_images:
                continue
            for field_name in ("image", "phone_image"):
                rel = getattr(view, field_name)
                if rel is None:
                    continue
                if not _resolve_repo_path(rel, root).is_file():
                    errors.append(
                        f"{label}: guides[{gi}].views[{vi}].{field_name} missing: {rel}"
                    )

    return errors


def _check_steps(label: str, card: Card, guide_ids: set[str]) -> list[str]:
    """Playbook rules that need the whole card (cue glyphs and predicates are checked by the shared loops)."""
    errors: list[str] = []
    seen: list[str] = []
    for si, step in enumerate(card.steps):
        base = f"{label}: steps[{si}]({step.id})"
        if step.id in seen:
            errors.append(f"{base}: duplicate step id {step.id!r}")
        for req in step.requires:
            if req == step.id:
                errors.append(f"{base}: requires itself")
            elif req not in seen:
                later = req in {s.id for s in card.steps}
                errors.append(
                    f"{base}: requires {req!r}, which is "
                    + ("a LATER step; requires must name earlier steps" if later else "not a step of this card")
                )
        seen.append(step.id)
        if step.guide_id is not None and step.guide_id not in guide_ids:
            errors.append(f"{base}: guide_id {step.guide_id!r} is not a guide of this card")
        for fi, faq in enumerate(step.faq):
            if not faq.q.strip() or faq.q != faq.q.lower():
                errors.append(f"{base}.faq[{fi}].q: must be non-empty lowercase, as a person would ask it aloud: {faq.q!r}")

        if step.verify is None:
            for where, cue in _step_cues(step, base):
                for line_name, text in (("line1", cue.line1), ("line2", cue.line2)):
                    found = MANUAL_FORBIDDEN.search(text)
                    if found:
                        errors.append(
                            f"{where}.{line_name}: a manual step (no verify) is HUMAN CONFIRMED, never {found.group(0)}: {text!r}"
                        )
        else:
            signals = [p.signal for p in step.verify.when]
            for pi, signal in enumerate(signals):
                if signal not in ALLOWED_VERIFY_SIGNALS:
                    errors.append(
                        f"{base}.verify.when[{pi}]: signal {signal!r} is not an allowed telemetry signal "
                        f"({', '.join(sorted(ALLOWED_VERIFY_SIGNALS))})"
                    )
            if any(sig.startswith("led.") for sig in signals):
                ok = step.verify.ok
                for line_name, text in (("line1", ok.line1), ("line2", ok.line2)):
                    if re.search(r"\b(VERIFIED|CONFIRMED|CORRECT)\b", text):
                        errors.append(
                            f"{base}.verify.ok.{line_name}: an LED command is COMMANDED, not measured light; "
                            f"do not say VERIFIED/CONFIRMED/CORRECT: {text!r}"
                        )
    return errors


def _check_cite(where: str, cite, card: Card, source_files: dict[str, Path | None]) -> list[str]:
    errors: list[str] = []
    if cite.source not in source_files:
        errors.append(f"{where}: source {cite.source!r} is not in this card's sources")
        return errors
    if cite.quote is None:
        return errors
    source_path = source_files[cite.source]
    if source_path is None:
        errors.append(f"{where}: quote given but source {cite.source!r} has no file to check it against")
        return errors
    if not source_path.is_file():
        return errors  # already reported as a missing source file
    haystack = _normalise(source_path.read_text(encoding="utf-8"))
    if _normalise(cite.quote) not in haystack:
        errors.append(f"{where}: quote not found verbatim in {source_path.name}: {cite.quote!r}")
    return errors


def _check_alias_clashes(parsed: list[tuple[Path, Card]]) -> list[str]:
    """The goal resolver matches aliases by substring; the same alias on two cards of one goal_mode makes it ambiguous."""
    owners: dict[tuple[str, str], str] = {}
    errors: list[str] = []
    for path, card in parsed:
        for alias in {a.strip().lower() for a in card.aliases if a.strip()}:
            key = (card.goal_mode, alias)
            if key in owners and owners[key] != card.card_id:
                errors.append(
                    f"{path.name}: alias {alias!r} is also an alias of {owners[key]!r} (same goal_mode {card.goal_mode}); "
                    "the resolver would be ambiguous"
                )
            else:
                owners[key] = card.card_id
    return errors


def validate_cards(
    cards_dir: Path = DEFAULT_CARDS_DIR,
    *,
    root: Path = REPO_ROOT,
    check_images: bool = False,
) -> list[str]:
    """Return a list of readable error strings. Empty means every card is valid."""
    errors: list[str] = []
    parsed: list[tuple[Path, Card]] = []
    paths = sorted(Path(cards_dir).glob("*.json"))
    if not paths:
        errors.append(f"{cards_dir}: no card files found")
    for path in paths:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{path.name}: not readable JSON: {exc}")
            continue
        try:
            card = Card.model_validate(raw)
        except ValidationError as exc:
            for item in exc.errors():
                loc = ".".join(str(part) for part in item["loc"]) or "(root)"
                errors.append(f"{path.name}: [{loc}] {item['msg']}")
            continue
        errors.extend(_check_card(card, path, root, check_images))
        parsed.append((path, card))
    errors.extend(_check_alias_clashes(parsed))
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate GhostBuild Repair Cards.")
    parser.add_argument("cards_dir", nargs="?", default=str(DEFAULT_CARDS_DIR))
    parser.add_argument(
        "--check-images",
        action="store_true",
        help="also require GuideView image paths to exist (off by default; guide images come from another lane)",
    )
    args = parser.parse_args(argv)

    cards_dir = Path(args.cards_dir)
    if not cards_dir.is_absolute():
        cards_dir = Path.cwd() / cards_dir
    errors = validate_cards(cards_dir, check_images=args.check_images)
    if errors:
        for error in errors:
            print(f"ERROR {error}")
        print(f"FAILED: {len(errors)} error(s) in {cards_dir}")
        return 1
    count = len(list(cards_dir.glob("*.json")))
    print(f"OK: {count} card(s) valid in {cards_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
