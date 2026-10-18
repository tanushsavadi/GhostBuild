"""Procedure store + validator. Approved procedures live in knowledge/procedures/ (committed);
agent deliveries land as drafts in var/drafts/ until a person approves them."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from contracts.models import JigProfile, Procedure

ROOT = Path(__file__).resolve().parents[2]
APPROVED_DIR = ROOT / "knowledge" / "procedures"
COMPILED_DIR = APPROVED_DIR / "compiled"
JIG_DIR = ROOT / "knowledge" / "jigs"
DRAFT_DIR = ROOT / "var" / "drafts"


def load_profiles(jig_dir: Path = JIG_DIR) -> dict[str, JigProfile]:
    out = {}
    for f in sorted(jig_dir.glob("*.json")):
        p = JigProfile.model_validate_json(f.read_text())
        out[p.id] = p
    return out


def validate(payload: object, profiles: dict[str, JigProfile]) -> tuple[Procedure | None, list[str]]:
    """Schema + cross-file checks. Error strings are written for the Creao agent to fix its output."""
    try:
        proc = Procedure.model_validate(payload)
    except ValidationError as exc:
        return None, [f"{'.'.join(str(x) for x in e['loc'])}: {e['msg']}" for e in exc.errors()]
    errors: list[str] = []
    if proc.jig_profile:
        prof = profiles.get(proc.jig_profile)
        if prof is None:
            errors.append(f"jig_profile {proc.jig_profile!r} is unknown; known: {sorted(profiles)} (or omit it)")
        else:
            for i, s in enumerate(proc.steps):
                if s.check.jig_check and s.check.jig_check not in prof.checks:
                    errors.append(f"steps.{i}.check.jig_check {s.check.jig_check!r} not in {sorted(prof.checks)}")
                for fid in s.check.faults:
                    if fid not in prof.faults:
                        errors.append(f"steps.{i}.check.faults {fid!r} not in {sorted(prof.faults)}")
    return (proc if not errors else None), errors


class Store:
    def __init__(self, profiles: dict[str, JigProfile]) -> None:
        self.profiles = profiles
        DRAFT_DIR.mkdir(parents=True, exist_ok=True)

    def _read(self, d: Path) -> dict[str, Procedure]:
        out = {}
        for f in sorted(d.glob("*.json")):
            try:
                p = Procedure.model_validate_json(f.read_text())
                out[p.id] = p
            except ValidationError:
                continue
        return out

    def approved(self) -> dict[str, Procedure]:
        procs = {**self._read(APPROVED_DIR), **(self._read(COMPILED_DIR) if COMPILED_DIR.exists() else {})}
        return {k: v for k, v in procs.items() if v.review.status == "approved"}

    def drafts(self) -> dict[str, Procedure]:
        return self._read(DRAFT_DIR)

    def get(self, pid: str) -> Procedure | None:
        return self.approved().get(pid) or self.drafts().get(pid)

    def save_draft(self, proc: Procedure) -> Procedure:
        # Whatever the agent claims, a delivery is an unreviewed agent draft.
        proc = proc.model_copy(update={"origin": "agent_compiled", "review": proc.review.model_copy(
            update={"status": "draft", "reviewer": None})})
        (DRAFT_DIR / f"{proc.id}.json").write_text(proc.model_dump_json(indent=2, by_alias=True))
        return proc

    def approve(self, pid: str, reviewer: str) -> Procedure:
        draft = self.drafts().get(pid)
        if draft is None:
            raise KeyError(pid)
        proc = draft.model_copy(update={"review": draft.review.model_copy(
            update={"status": "approved", "reviewer": reviewer})})
        COMPILED_DIR.mkdir(parents=True, exist_ok=True)
        (COMPILED_DIR / f"{pid}.json").write_text(proc.model_dump_json(indent=2, by_alias=True))
        (DRAFT_DIR / f"{pid}.json").unlink(missing_ok=True)
        return proc


def dump(proc: Procedure) -> dict:
    return json.loads(proc.model_dump_json(by_alias=True))
