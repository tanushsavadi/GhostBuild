"""GhostBuild contract v2 (Pi + G2). Single source of truth for every message crossing a lane boundary.

Boundaries:  Pi -> core (Observation) · core -> G2 (HudFrame) · G2 -> core (G2Input)
             core -> phone/tools (State, Health) · knowledge -> core (Card)

Rules (docs/PIVOT_GHOSTBUILD.md §0 "Hardware/UX amendment"):
- Observation carries MEASURED camera facts and COMMANDED LED facts only. Verdicts ("blocked") are core's.
- `camera: null` means camera unavailable. It is never success.
- source tells where data came from; non-live sources are shown as such everywhere.
- Models forbid unknown keys so fixture typos fail the lock.
Additive optional fields are allowed after lock; renames/removals need D + every consumer.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = 2

Source = Literal["pi_live", "replay", "simulated", "manual"]  # manual = no telemetry involved (wearer-confirmed playbook steps)
EvidenceLabel = Literal[
    "MEASURED LIVE",
    "INFERRED",
    "COMMANDED",
    "DETERMINISTIC",
    "HUMAN CONFIRMED",
    "MANUFACTURER DOC",
    "AUTHORED PROJECT SPEC",
    "AI-EXTRACTED · HUMAN-REVIEWED",
    "AUTHORED DEMO METADATA",
    "WEB TUTORIAL",
    "VIDEO TUTORIAL",
    "GITHUB SOURCE",
    "REPLAY",
    "SIMULATED",
]
GuideViewName = Literal["where", "how", "correct"]
# HUD modes mirror the UX amendment: 0 quiet, 1 intervention, 2/3 visual assist (3 = multi-view), 4 ask, 5 verified, 6 error.
HudMode = Literal["quiet", "welcome", "menu", "step", "intervene", "visual", "ask", "verified", "uncertain", "error"]
GoalMode = Literal["fix", "build"]
GoalVia = Literal["g2_menu", "voice", "phone_text"]
Gesture = Literal["press", "swipe_down", "swipe_up", "hold_start", "hold_end"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------- Pi -> core
class CameraObs(Strict):
    """What the Pi measured from the latest frame. Features only; the core decides what they mean."""

    frame_seq: int = Field(ge=0, description="increments once per NEW frame; a stuck value means a frozen feed")
    frame_age_ms: int = Field(ge=0, description="age of the frame when this observation was built")
    mean_luma: float = Field(ge=0, le=255)
    luma_std: float = Field(ge=0, description="contrast; a covered lens is dark AND flat")
    detail: float = Field(ge=0, description="variance of Laplacian (focus/detail); low when covered or defocused")
    motion: float = Field(ge=0, le=1, description="fraction of ROI pixels changed vs the previous frame")
    marker_found: Optional[bool] = Field(default=None, description="fiducial/marker seen in the fixed field of view; null = not evaluated")
    marker_id: Optional[int] = None


class LedObs(Strict):
    """COMMANDED state only. GPIO high is not measured light."""

    commanded_on: bool
    cmd_seq: int = Field(ge=0)
    reason: Optional[str] = Field(default=None, description="e.g. motion_in_roi, manual")


class Observation(Strict):
    v: Literal[2] = 2
    dev: str = Field(min_length=1)
    seq: int = Field(ge=0, description="monotonic per device boot; core drops seq <= last")
    ms: int = Field(ge=0, description="device monotonic ms")
    at: int = Field(ge=0, description="device wall clock, epoch ms (advisory)")
    source: Source
    camera: Optional[CameraObs] = Field(description="null = camera unavailable. Never treated as success.")
    led: Optional[LedObs] = None
    error: Optional[str] = Field(default=None, description="short machine-readable reason when camera is null")


# --------------------------------------------------------------------------- shared small types
class Cue(Strict):
    line1: str = Field(min_length=1, max_length=24)
    line2: str = Field(default="", max_length=26)


class Evidence(Strict):
    at: int = Field(description="core epoch ms")
    text: str
    label: EvidenceLabel
    evidence: dict[str, float | int | str | bool | None] = Field(default_factory=dict)


class Menu(Strict):
    """Onboarding choice. swipe moves `selected`, press confirms (core tracks it; a selection is a goal, never a repair commit)."""

    prompt: str = Field(max_length=24)
    options: list[str] = Field(min_length=2, max_length=4)
    selected: int = Field(ge=0)


class StepRef(Strict):
    """Where the wearer is in a playbook. Rendered as a small counter next to the action line."""

    index: int = Field(ge=0)
    count: int = Field(ge=1)
    step_id: str
    check: Literal["manual", "measured"] = Field(description="manual = the wearer confirms (HUMAN CONFIRMED); measured = evidence verifies it")
    confirmed: bool = False


class ImageRef(Strict):
    guide_id: str
    view: GuideViewName
    index: int = Field(ge=0)
    count: int = Field(ge=1)
    title: str = Field(max_length=24)
    url: str = Field(description="path on core, e.g. /guides/camera_lens/where.png (G2-ready 4-bit grey PNG)")
    w: int = Field(ge=1, le=288)
    h: int = Field(ge=1, le=144)
    sha256: str
    provenance: EvidenceLabel
    step_id: str


class AnswerPage(Strict):
    """One complete readable page of an answer. Swipes page; press returns without completing a step."""

    text: str = Field(min_length=1, max_length=320)
    index: int = Field(ge=0)
    count: int = Field(ge=1)
    grounding: Literal["guide", "general", "unsure", "deterministic"] = "guide"
    label: EvidenceLabel = "INFERRED"


# --------------------------------------------------------------------------- core -> G2
class HudFrame(Strict):
    """The only thing G2 renders. Written by core/ghostbuild_core/hud.py and nothing else."""

    type: Literal["hud"] = "hud"
    v: Literal[2] = 2
    seq: int = Field(ge=0, description="monotonic; unchanged frames are never re-sent")
    mode: HudMode
    cue: Optional[Cue] = Field(default=None, description="null in quiet mode (render blank)")
    image: Optional[ImageRef] = Field(default=None, description="present only in visual mode; cue is the text fallback")
    menu: Optional[Menu] = Field(default=None, description="present only in menu mode; cue is the text fallback")
    step: Optional[StepRef] = Field(default=None, description="present in step mode and in visual mode opened from a step")
    cue_id: Optional[str] = None
    ttl_ms: Optional[int] = Field(default=None, description="plugin clears locally after this as a fallback")
    source: Source
    session_id: Optional[str] = Field(default=None, description="current session; the plugin stores it and sends it in G2Hello on reconnect so the welcome never repeats")
    stale: bool = Field(default=False, description="true if backed by data older than the staleness limit; plugin shows ERROR instead")
    answer: Optional[AnswerPage] = Field(default=None, description="persistent answer page in ask mode; press returns to the same step")

    @model_validator(mode="after")
    def _shape(self) -> "HudFrame":
        if self.mode == "quiet" and self.cue is not None:
            raise ValueError("quiet frames carry no cue")
        if self.mode != "quiet" and self.cue is None:
            raise ValueError("non-quiet frames need a cue (also the text fallback for images)")
        if self.image is not None and self.mode != "visual":
            raise ValueError("image only in visual mode")
        if self.answer is not None and self.mode != "ask":
            raise ValueError("answer page only in ask mode")
        if (self.menu is not None) != (self.mode == "menu"):
            raise ValueError("menu iff mode == menu")
        if self.mode == "step" and self.step is None:
            raise ValueError("step mode needs a step ref")
        return self


# --------------------------------------------------------------------------- G2 -> core
class G2Input(Strict):
    """Double press is handled locally (system exit) and never sent. A press is a recheck/help request, never a commit."""

    type: Literal["g2_input"] = "g2_input"
    v: Literal[2] = 2
    gesture: Gesture
    seq_seen: int = Field(ge=0, description="last hud seq the plugin had rendered")
    surface: Literal["g2", "simulator"] = "g2"


class G2Hello(Strict):
    """First message on every (re)connect. Core replies with the current frame. Welcome shows only when session_id is null/unknown."""

    type: Literal["g2_hello"] = "g2_hello"
    v: Literal[2] = 2
    client_id: str
    session_id: Optional[str] = None
    surface: Literal["g2", "simulator"] = "g2"


# --------------------------------------------------------------------------- goal / session (G2 menu, voice, phone text)
class GoalRequest(Strict):
    v: Literal[2] = 2
    session_id: str
    mode: GoalMode
    via: GoalVia
    text: Optional[str] = Field(default=None, max_length=300, description="free text from voice transcript or phone; null for a bare menu choice")


class GoalResolution(Strict):
    """Never pretends. `unsupported` carries an honest fallback; no diagnostics are invented."""

    v: Literal[2] = 2
    session_id: str
    status: Literal["supported", "unsupported", "ambiguous"]
    mode: GoalMode
    card_id: Optional[str] = None
    task_title: Optional[str] = None
    cue: Cue
    detail: str = Field(description="phone-side explanation: what is supported and what is not")
    alternatives: list[str] = Field(default_factory=list)
    research_queued: bool = Field(default=False, description="true if an unsupported request was saved for an async research run; nothing is available NOW")
    conversing: bool = Field(default=False, description="true while the assistant is talking with the wearer before any guide exists (it asks, then a guide follows); not a refusal")


# --------------------------------------------------------------------------- core -> phone/tools
class Health(Strict):
    ok: bool
    uptime_s: float
    pi_link: Literal["up", "stale", "down"]
    pi_last_seq: Optional[int] = None
    pi_age_ms: Optional[int] = None
    source: Optional[Source] = None
    camera: Literal["ok", "unavailable", "frozen", "unknown"] = "unknown"
    g2_clients: int = Field(ge=0)
    voice: Literal["off", "on"] = "off"


class Session(Strict):
    id: str
    phase: Literal["welcome", "menu", "task"]
    goal: Optional[GoalMode] = None
    card_id: Optional[str] = None
    welcome_shown: bool = False


class PlaybookState(Strict):
    card_id: str
    step_index: int = Field(ge=0)
    step_count: int = Field(ge=1)
    step_id: str
    confirmed: list[str] = Field(default_factory=list, description="HUMAN CONFIRMED step ids")
    verified: list[str] = Field(default_factory=list, description="step ids satisfied by measured evidence")


class State(Strict):
    v: Literal[2] = 2
    session: Session
    engine: Literal["NO_LINK", "HEALTHY", "FAULT", "EXHAUSTED", "AWAIT_FUNC", "PLAYBOOK"]
    card_id: str
    test: Optional[str] = None
    step_id: Optional[str] = None
    check: Optional[int] = None
    help_view: Optional[GuideViewName] = None
    source: Optional[Source] = None
    health: Health
    hud: Optional[HudFrame] = None
    playbook: Optional[PlaybookState] = None
    events: list[Evidence] = Field(default_factory=list)


# --------------------------------------------------------------------------- knowledge -> core
class Predicate(Strict):
    signal: str = Field(description="dotted path into Observation, e.g. camera.mean_luma")
    op: Literal["lt", "gt", "eq", "is_null", "not_null"]
    value: Optional[float | int | bool | str] = None


class Source_(Strict):
    id: str
    kind: EvidenceLabel
    title: str
    url: Optional[str] = None
    file: Optional[str] = None


class Cite(Strict):
    source: str
    loc: str = Field(description="page/section, or a timestamp like t=00:12:34 for video")
    quote: Optional[str] = None
    url: Optional[str] = Field(default=None, description="deep link (e.g. video &t=754s, repo file#L10)")


class GuideView(Strict):
    view: GuideViewName
    step_id: str
    title: str = Field(max_length=24)
    image: str = Field(description="repo path to the G2-ready PNG (<=288x144, 4-bit grey)")
    phone_image: Optional[str] = Field(default=None, description="repo path to the high-res phone asset")
    provenance: EvidenceLabel
    depicts: str
    fallback: Cue
    fov_note: Optional[str] = Field(default=None, description="what part of the Pi's fixed field of view this refers to")
    reference_url: Optional[str] = Field(default=None, description="link to a source image/video frame this view should be recreated from by a human; never auto-used on the glasses")


class Guide(Strict):
    id: str
    title: str
    views: list[GuideView] = Field(min_length=1, max_length=3)


class Check(Strict):
    when: list[Predicate] = Field(default_factory=list)
    action: Cue
    why: str
    cites: list[Cite] = Field(default_factory=list)
    guide_id: Optional[str] = None


class Test(Strict):
    id: str
    fail_when: list[Predicate] = Field(min_length=1, description="ALL must hold for the window to count as failing")
    fail_after_ms: int = Field(ge=0)
    pass_after_ms: int = Field(ge=0)
    fact: Cue
    ok: Cue
    checks: list[Check] = Field(min_length=1)
    offer_help_after_ms: int = Field(default=8000, ge=0, description="gentle PRESS FOR PICTURE offer; once per fault")


class Functional(Strict):
    """Post-repair functional demonstration. Success is a measured camera fact; the LED is only COMMANDED."""

    id: str
    trigger: list[Predicate]
    prompt: Cue
    expect_commanded: Optional[Predicate] = None
    ok: Cue
    within_ms: int = Field(ge=0)


class Faq(Strict):
    q: str = Field(description="how a confused beginner would ASK it out loud, lowercase, e.g. 'which leg is longer'")
    a: Cue


class StepVerify(Strict):
    """Optional evidence check. Without it a step is manual: only the wearer can confirm it (HUMAN CONFIRMED, never VERIFIED)."""

    when: list[Predicate] = Field(min_length=1)
    hold_ms: int = Field(default=1500, ge=0)
    ok: Cue = Field(description="shown once when measured evidence satisfies the step")


class Part(Strict):
    """A part or fastener a step uses, exactly as the source (a manual, a parts list) prints it. Never a guess: qty is null when the source prints none."""

    id: str = Field(min_length=1, max_length=24, description="the part number as printed, e.g. 101344")
    qty: Optional[int] = Field(default=None, ge=1, description="quantity printed for this step; null when the source gives none")
    name: str = Field(default="", max_length=60, description="short common name; descriptive, never a brand claim")
    note: Optional[str] = Field(default=None, max_length=160, description="what the source says about it here, e.g. 'crossed out in this step: do not use'")
    avoid: bool = Field(default=False, description="the source explicitly marks this part as NOT for this step")


class Step(Strict):
    id: str
    title: str = Field(max_length=28)
    cue: Cue = Field(description="the glasses text for this step: one action")
    detail: str = Field(default="", max_length=600, description="phone-only full explanation")
    why: Optional[Cue] = None
    where: Optional[Cue] = None
    warnings: list[str] = Field(default_factory=list)
    faq: list[Faq] = Field(default_factory=list)
    troubleshoot: list[Check] = Field(default_factory=list)
    guide_id: Optional[str] = None
    verify: Optional[StepVerify] = None
    requires: list[str] = Field(default_factory=list)
    instruction: Optional[Cue] = Field(default=None, description="authored plain-language action and method for the main step; exact identifiers stay in parts/detail. Legacy cue is the fallback; preserve safety quantities/values.")
    parts: list[Part] = Field(default_factory=list, description="parts/fasteners this step uses, as the source prints them (assembly manuals, parts lists)")
    cites: list[Cite] = Field(default_factory=list, description="where in a source this step comes from (e.g. manual page); phone shows the link")


class Card(Strict):
    v: Literal[2] = 2
    card_id: str
    title: str
    provenance: EvidenceLabel
    sources: list[Source_]
    tests: list[Test] = Field(default_factory=list)
    steps: list[Step] = Field(default_factory=list, description="a playbook: ordered steps navigated by the wearer; tests (fault mode) and steps may coexist")
    functional: Optional[Functional] = None
    guides: list[Guide] = Field(default_factory=list)
    goal_mode: GoalMode = Field(default="fix", description="fix = repair/diagnose; build = guided supported setup")
    step_image: Optional[GuideViewName] = Field(default=None, description="show this authored guide view with each step by default; navigation and evidence rules are unchanged")
    aliases: list[str] = Field(default_factory=list, description="lowercase phrases the deterministic goal resolver matches, e.g. 'camera', 'inspection station'")

    @model_validator(mode="after")
    def _has_content(self) -> "Card":
        if not self.tests and not self.steps:
            raise ValueError("a card needs tests (fault mode) or steps (playbook)")
        ids = [st.id for st in self.steps]
        if len(ids) != len(set(ids)):
            raise ValueError("step ids must be unique")
        return self


SCHEMAS: dict[str, type[BaseModel]] = {
    "observation": Observation,
    "hud": HudFrame,
    "g2_input": G2Input,
    "g2_hello": G2Hello,
    "goal_request": GoalRequest,
    "goal_resolution": GoalResolution,
    "state": State,
    "health": Health,
    "card": Card,
}

FIXTURES: dict[str, str] = {
    "observation_*.json": "observation",
    "hud_*.json": "hud",
    "g2_input_*.json": "g2_input",
    "g2_hello_*.json": "g2_hello",
    "goal_request_*.json": "goal_request",
    "goal_resolution_*.json": "goal_resolution",
    "state_*.json": "state",
    "health_*.json": "health",
    "card_*.json": "card",
}
