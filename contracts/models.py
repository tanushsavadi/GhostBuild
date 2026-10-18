"""GhostBuild v2 shared contracts (D owns). `make contracts` exports these to contracts/schema/ and contracts/ts/.

One procedure file drives everything; nothing about any specific build is hardcoded in core.
Device facts live in knowledge/jigs/*.json (jig profiles) and knowledge/procedures/*.json.
Keep this file device-agnostic (`make lint-generic`).
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

HUD_MAX = 28
# Glyphs the HUD may carry. B confirms `· ● → °` on physical G2 in the glyph test; drop any that fail here.
HUD_GLYPHS = re.compile(r"^[A-Z0-9 ·●→°+\-/'.,:?!()%&#=]*$")
SLUG = r"^[a-z0-9][a-z0-9_-]{0,63}$"


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


def hud_text(v: str) -> str:
    if not v or v != v.strip():
        raise ValueError("HUD text must be non-empty with no leading/trailing spaces")
    if len(v) > HUD_MAX:
        raise ValueError(f"HUD text {v!r} is {len(v)} chars (max {HUD_MAX})")
    if not HUD_GLYPHS.match(v):
        bad = sorted({c for c in v if not HUD_GLYPHS.match(c)})
        raise ValueError(f"HUD text {v!r} must be uppercase and use only HUD glyphs; bad: {bad}")
    return v


# --- procedure (Creao agent output, authored files) ------------------------------------------------


class Source(Strict):
    title: str
    url: str | None = None
    label: Literal[
        "MANUFACTURER DOC", "AUTHORED PROJECT SPEC", "WEB TUTORIAL", "AUTHORED DEMO METADATA"
    ] = "AUTHORED DEMO METADATA"


class Review(Strict):
    status: Literal["draft", "approved", "rejected"] = "draft"
    reviewer: str | None = None
    notes: str | None = None


class Part(Strict):
    id: str = Field(pattern=SLUG)
    name: str
    qty: int = Field(default=1, ge=1)


class Faq(Strict):
    q: str = Field(description="An example question in the user's words")
    a: str = Field(description="The HUD answer (<= 28 chars, uppercase)")

    _a = field_validator("a")(hud_text)


class Troubleshoot(Strict):
    symptom: str
    checks: list[str] = Field(min_length=1, description="HUD lines, most likely cause first")

    @field_validator("checks")
    @classmethod
    def _checks(cls, v: list[str]) -> list[str]:
        return [hud_text(c) for c in v]


class Check(Strict):
    type: Literal["jig", "user_confirm"]
    jig_check: str | None = Field(default=None, description="A check id from the procedure's jig profile")
    faults: dict[str, str] = Field(
        default_factory=dict, description="Jig fault id -> HUD line, watched while this step is active"
    )

    @field_validator("faults")
    @classmethod
    def _faults(cls, v: dict[str, str]) -> dict[str, str]:
        return {k: hud_text(t) for k, t in v.items()}

    @model_validator(mode="after")
    def _shape(self) -> Check:
        if self.type == "jig" and not self.jig_check:
            raise ValueError("check.type 'jig' needs jig_check")
        if self.type == "user_confirm" and self.jig_check:
            raise ValueError("check.type 'user_confirm' must not set jig_check")
        return self


class Step(Strict):
    id: str = Field(pattern=SLUG)
    hud: str = Field(description="One action, <= 28 chars, uppercase")
    detail: str = Field(default="", max_length=400, description="Longer text for the phone/mirror, never the HUD")
    why: str | None = Field(default=None, description="HUD line answering 'why this step?'")
    where: str | None = Field(default=None, description="HUD line answering 'where does it go?'")
    parts: list[str] = Field(default_factory=list)
    requires: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    check: Check
    troubleshoot: list[Troubleshoot] = Field(default_factory=list)
    faq: list[Faq] = Field(default_factory=list)

    _hud = field_validator("hud")(hud_text)

    @field_validator("why", "where")
    @classmethod
    def _opt_hud(cls, v: str | None) -> str | None:
        return None if v is None else hud_text(v)

    @field_validator("warnings")
    @classmethod
    def _warnings(cls, v: list[str]) -> list[str]:
        return [hud_text(w) for w in v]


class Procedure(Strict):
    v: Literal[1] = 1
    id: str = Field(pattern=SLUG)
    title: str = Field(max_length=80)
    domain: str = Field(description="Free text, e.g. electronics, paper folding, toy building")
    origin: Literal["authored", "agent_compiled"]
    source: Source
    review: Review
    jig_profile: str | None = Field(default=None, description="knowledge/jigs/<id>.json; required for jig checks")
    parts: list[Part] = Field(default_factory=list)
    steps: list[Step] = Field(min_length=1, max_length=30)

    @model_validator(mode="after")
    def _refs(self) -> Procedure:
        errors: list[str] = []
        part_ids = {p.id for p in self.parts}
        if len(part_ids) != len(self.parts):
            errors.append("duplicate part ids")
        seen: set[str] = set()
        for s in self.steps:
            if s.id in seen:
                errors.append(f"duplicate step id {s.id!r}")
            for r in s.requires:
                if r not in seen:
                    errors.append(f"step {s.id!r} requires {r!r}, which is not an earlier step")
            for p in s.parts:
                if p not in part_ids:
                    errors.append(f"step {s.id!r} uses unknown part {p!r}")
            if (s.check.type == "jig" or s.check.faults) and not self.jig_profile:
                errors.append(f"step {s.id!r} uses the jig but the procedure has no jig_profile")
            seen.add(s.id)
        if errors:
            raise ValueError("; ".join(errors))
        return self


# --- jig profile (device facts, knowledge/jigs/) -------------------------------------------------


class Predicate(Strict):
    field: str
    eq: str | int | bool | None = None
    in_: list[str | int | bool] | None = Field(default=None, alias="in")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    @model_validator(mode="after")
    def _one(self) -> Predicate:
        if (self.eq is None) == (self.in_ is None):
            raise ValueError("predicate needs exactly one of eq / in")
        return self


class JigProfile(Strict):
    id: str = Field(pattern=SLUG)
    title: str
    fields: dict[str, list[str | int | bool]] = Field(description="Observation field -> allowed values")
    checks: dict[str, list[Predicate]] = Field(description="Check id -> all-of predicates (pass = VERIFIED)")
    faults: dict[str, list[Predicate]] = Field(default_factory=dict, description="Fault id -> all-of predicates")
    edge_checks: list[str] = Field(
        default_factory=list, description="Checks that verify only on a fail->pass change seen while the step is active"
    )
    notes: str = ""

    @model_validator(mode="after")
    def _known(self) -> JigProfile:
        bad = [c for c in self.edge_checks if c not in self.checks]
        if bad:
            raise ValueError(f"edge_checks not in checks: {bad}")
        return self


# --- live messages ---------------------------------------------------------------------------------


class JigObservation(Strict):
    """Jig adapter -> core (ws role=jig), ~5 Hz. Firmware reports a state only after 3 matching readings."""

    type: Literal["jig"] = "jig"
    v: Literal[1] = 1
    dev: str
    seq: int = Field(ge=0)
    ms: int = Field(ge=0)
    fields: dict[str, str | int | bool]


class HudFrame(Strict):
    """Core -> G2. Written only by core/ghostbuild_core/hud.py. The plugin shows `lines` joined by newlines."""

    type: Literal["hud"] = "hud"
    seq: int = Field(ge=0)
    kind: Literal[
        "idle", "step", "checking", "verified", "confirmed", "fault", "answer",
        "troubleshoot", "complete", "clear", "status", "offline",
    ]
    lines: list[str] = Field(max_length=4)
    ttl_ms: int | None = Field(default=None, description="Plugin clears locally after this, as a fallback")
    procedure_id: str | None = None
    step_index: int | None = None
    step_total: int | None = None
    mode: Literal["VERIFIED", "GUIDED"] | None = None
    source: Literal["live", "simulated", "replay"] = "live"


class G2Input(Strict):
    """G2 -> core. Double-tap (exit dialog) is handled in the plugin."""

    type: Literal["g2_input"] = "g2_input"
    kind: Literal["voice", "tap", "menu", "swipe_up", "swipe_down"]
    text: str | None = Field(default=None, description="Speech-to-text transcript or menu item label")
    seq_seen: int | None = None


class Completion(Strict):
    step_id: str
    how: Literal["verified", "confirmed"]
    at: float


class Event(Strict):
    at: float
    text: str
    label: Literal["MEASURED LIVE", "USER CONFIRMED", "DETERMINISTIC", "SIMULATED", "REPLAY", "AGENT"]


class JigStatus(Strict):
    link: Literal["up", "down", "disabled"]
    source: Literal["live", "simulated", "replay"] | None = None
    fields: dict[str, str | int | bool] = Field(default_factory=dict)
    age_ms: int | None = None


class State(Strict):
    """GET /state for the mirror and review pages."""

    engine: Literal["IDLE", "STEP", "COMPLETE"]
    procedure_id: str | None = None
    procedure_title: str | None = None
    step_index: int | None = None
    step_total: int | None = None
    completed: list[Completion] = Field(default_factory=list)
    jig: JigStatus
    hud: HudFrame | None = None
    events: list[Event] = Field(default_factory=list)


class AgentDelivery(Strict):
    """Creao agent -> POST /agent/webhook (and the body of POST /procedures/validate)."""

    run_id: str | None = None
    request: str | None = Field(default=None, description="What the user asked to build")
    procedure: Procedure


class ValidateResult(Strict):
    ok: bool
    errors: list[str] = Field(default_factory=list)


SCHEMAS: dict[str, type[BaseModel]] = {
    "procedure": Procedure,
    "jig_profile": JigProfile,
    "jig_observation": JigObservation,
    "hud": HudFrame,
    "g2_input": G2Input,
    "state": State,
    "agent_delivery": AgentDelivery,
    "validate_result": ValidateResult,
}

FIXTURES: dict[str, str] = {
    "procedure_*.json": "procedure",
    "jig_profile_*.json": "jig_profile",
    "jig_obs_*.json": "jig_observation",
    "hud_*.json": "hud",
    "g2_input_*.json": "g2_input",
    "state_*.json": "state",
    "agent_delivery_*.json": "agent_delivery",
    "validate_result_*.json": "validate_result",
}
