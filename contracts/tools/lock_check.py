"""Contract-lock check (Python half of `make contracts`).

Exports JSON Schema from contracts/models.py and validates every contracts/examples/*.json.
This file only checks; it defines no schema. contracts/models.py (D) must expose:

    SCHEMAS:  dict[str, type[BaseModel]]   # schema name -> model, exported to contracts/schema/<name>.json
    FIXTURES: dict[str, str]               # fnmatch pattern over example filenames -> SCHEMAS key

Exit 0 only if models.py imports, every lock fixture (docs/PIVOT_GHOSTBUILD.md §5.3) exists,
every example maps to exactly one schema, and every example validates.
"""

from __future__ import annotations

import fnmatch
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "contracts"
EXAMPLES = CONTRACTS / "examples"
SCHEMA_DIR = CONTRACTS / "schema"

# docs/PIVOT_GHOSTBUILD.md §5.3. Exact files, plus globs that must match at least one file.
REQUIRED_FILES = ["card_barrier.json"]
REQUIRED_GLOBS = ["observation_*.json", "hud_*.json", "g2_input_*.json", "state_*.json"]


def main() -> int:
    problems: list[str] = []

    if not (CONTRACTS / "models.py").exists():
        print("RED  contracts/models.py does not exist (D authors it by the Sat 17:00 lock per docs/PIVOT_GHOSTBUILD.md §5.3)")
        return 1

    sys.path.insert(0, str(ROOT))
    try:
        from pydantic import BaseModel, ValidationError
        from pydantic.json_schema import models_json_schema

        import contracts.models as models
    except Exception as exc:  # report any import failure as a red lock
        print(f"RED  contracts/models.py failed to import: {exc!r}")
        return 1

    schemas = getattr(models, "SCHEMAS", None)
    fixtures = getattr(models, "FIXTURES", None)
    if not isinstance(schemas, dict) or not schemas:
        problems.append("models.py must define SCHEMAS: dict[str, BaseModel subclass]")
    if not isinstance(fixtures, dict) or not fixtures:
        problems.append("models.py must define FIXTURES: dict[fnmatch pattern, SCHEMAS key]")
    if problems:
        return report(problems)

    for name, model in schemas.items():
        if not (isinstance(model, type) and issubclass(model, BaseModel)):
            problems.append(f"SCHEMAS[{name!r}] is not a pydantic model")
    for pattern, name in fixtures.items():
        if name not in schemas:
            problems.append(f"FIXTURES[{pattern!r}] -> {name!r} is not a SCHEMAS key")
    if problems:
        return report(problems)

    # Export: one standalone schema per message, plus one combined file with shared $defs for TS.
    SCHEMA_DIR.mkdir(exist_ok=True)
    for old in SCHEMA_DIR.glob("*.json"):
        old.unlink()
    for name, model in schemas.items():
        write_json(SCHEMA_DIR / f"{name}.json", model.model_json_schema())
    refs, combined = models_json_schema(
        [(model, "validation") for model in schemas.values()], title="GhostBuildContracts"
    )
    ref = {name: refs[(model, "validation")]["$ref"] for name, model in schemas.items()}
    combined["type"] = "object"
    combined["properties"] = {name: {"$ref": r} for name, r in ref.items()}
    combined["additionalProperties"] = False
    write_json(SCHEMA_DIR / "_all.json", combined)
    write_json(SCHEMA_DIR / "_fixtures.json", {pattern: ref[name] for pattern, name in fixtures.items()})

    # Lock completeness.
    present = sorted(p.name for p in EXAMPLES.glob("*.json")) if EXAMPLES.exists() else []
    for f in REQUIRED_FILES:
        if f not in present:
            problems.append(f"missing lock fixture contracts/examples/{f}")
    for g in REQUIRED_GLOBS:
        if not fnmatch.filter(present, g):
            problems.append(f"missing lock fixture contracts/examples/{g}")

    # Validate every example against exactly one schema.
    checked = 0
    for fname in present:
        matches = [p for p in fixtures if fnmatch.fnmatch(fname, p)]
        if len(matches) != 1:
            problems.append(f"{fname}: matches {len(matches)} FIXTURES patterns (need exactly 1): {matches}")
            continue
        model = schemas[fixtures[matches[0]]]
        try:
            model.model_validate_json((EXAMPLES / fname).read_text())
            checked += 1
        except ValidationError as exc:
            problems.append(f"{fname} -> {model.__name__}: {exc}")

    # Typos in a fixture pass silently unless the model forbids unknown keys.
    lax = [n for n, m in schemas.items() if m.model_config.get("extra") != "forbid"]
    if lax:
        print(f"WARN models without extra='forbid' (misspelled fixture keys go unnoticed): {', '.join(lax)}")

    if problems:
        return report(problems)
    print(f"GREEN python: {len(schemas)} schemas exported, {checked} examples valid")
    return 0


def write_json(path: Path, obj: object) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def report(problems: list[str]) -> int:
    for p in problems:
        print(f"RED  {p}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
