"""Data shapes the assistant exchanges with a brain (an LLM) and keeps per session. Pure data: no IO, no engine, no HUD."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .adaptive import Decision, TaskFact

Experience = Literal["unknown", "first_time", "some", "experienced"]
MAX_FACTS = 8


class Profile(BaseModel):
    """What we know about the wearer for THIS session. Built from their own words; never guessed, never shared beyond the prompt."""

    experience: Experience = "unknown"
    facts: list[str] = Field(
        default_factory=list,
        description="short statements the wearer made: 'has a breadboard', 'Pi 4', 'no soldering iron'",
    )

    def merged(self, update: "Profile") -> "Profile":
        facts = list(self.facts)
        for f in update.facts:
            f = " ".join(f.split())[:120]
            if f and f.lower() not in {x.lower() for x in facts}:
                facts.append(f)
        return Profile(
            experience=update.experience
            if update.experience != "unknown"
            else self.experience,
            facts=facts[-MAX_FACTS:],
        )

    def describe(self) -> str:
        level = {
            "first_time": "a first-timer (explain plainly, define terms, warn about common mistakes)",
            "some": "has some experience (brief explanations are fine)",
            "experienced": "experienced (be concise, skip basics)",
            "unknown": "experience level not known yet",
        }[self.experience]
        return f"Experience: {level}." + (
            " Known: " + "; ".join(self.facts) + "." if self.facts else ""
        )


class IntakeReply(BaseModel):
    """One conversational turn before a guide exists: ask the next question, start the guide, or decline."""

    action: Literal["ask", "start", "decline"]
    say: str = Field(
        description="what to say to the person, 1-2 short plain sentences (shown on the phone, spoken in earbuds)"
    )
    cue1: str = Field(
        default="",
        description="glasses line 1: at most 24 characters, ALL CAPS, the question in a few words",
    )
    cue2: str = Field(
        default="", description="glasses line 2: at most 26 characters, ALL CAPS"
    )
    quick_replies: list[str] = Field(
        default_factory=list,
        description="up to 4 short tap-to-answer options, only for 'ask'",
    )
    goal: str = Field(
        default="",
        description="for 'start': the task as one clear sentence including every specific the person gave",
    )
    library_id: str = Field(
        default="",
        description="for 'start': the exact id of a ready guide that fits, else empty",
    )
    decision: Decision | None = None
    context_sufficient: bool = False
    facts: list[TaskFact] = Field(default_factory=list)
    critical_unknowns: list[str] = Field(default_factory=list)
    question_key: str = ''
    question_reason: str = ''
    identification_help: str = ''
    branch: str = ''
    confidence: float = Field(default=0.5, ge=0, le=1)
    profile: Profile = Field(
        default_factory=Profile,
        description="what this turn taught you about the person",
    )


class StepReply(BaseModel):
    """One answer about the step the wearer is on."""

    answer: str = Field(
        description="the full answer, plain language, at most ~45 words; for the phone and earbuds"
    )
    cue1: str = Field(
        default="", description="glasses line 1: at most 24 characters, ALL CAPS"
    )
    cue2: str = Field(
        default="", description="glasses line 2: at most 26 characters, ALL CAPS"
    )
    grounding: Literal["guide", "general", "unsure"] = Field(
        description="guide = the guide's own text covers it; general = standard well-established knowledge beyond the guide; unsure = cannot answer reliably"
    )
    follow_up: str = Field(
        default="",
        description="ONE short clarifying question if a good answer needs it, else empty",
    )
    quick_replies: list[str] = Field(
        default_factory=list,
        description="up to 4 short tap-to-answer options for the follow-up",
    )
    add_note: bool = Field(
        default=False,
        description="true if this answer adds lasting help for THIS step and should be kept on it",
    )
    note_title: str = Field(default="", description="a 3-6 word title for the note")
    decision: Decision = 'EXPLAIN'
    facts: list[TaskFact] = Field(default_factory=list)
    critical_unknowns: list[str] = Field(default_factory=list)
    branch: str = ''



class Message(BaseModel):
    id: str = ""
    task_id: str = ""
    card_id: str = ""
    step_id: str = ""
    cached: bool = False
    role: Literal["user", "assistant", "system"]
    text: str
    at: int = 0
    kind: Literal["intake", "step", "info"] = "info"
    quick_replies: list[str] = Field(default_factory=list)
    speak: bool = False  # the phone speaks it (earbuds) when spoken replies are on
    grounding: str = ""


class Note(BaseModel):
    """Extra help kept on one step of one guide for this session (what the wearer asked and what they were told)."""

    card_id: str = ""
    step_id: str
    title: str
    question: str
    answer: str
    grounding: str = "general"
    at: int = 0


# ---------------------------------------------------------------------------- wire schemas (what the model is asked to emit)
# The structured-output grammar rejects the reply models above as "Schema is too complex" (optional fields, nested
# defaults, numeric bounds, nullable enums). The model fills these flat, all-required shapes instead; AnthropicBrain
# converts them to IntakeReply / StepReply, so the rest of the code is unchanged.
FactField = Literal["product", "model", "variant", "symptom", "observation", "tool", "material", "configuration",
                    "experience", "attempted", "safety", "branch"]


class FactWire(BaseModel):
    field: FactField
    value: str
    origin: Literal["user", "inferred"]
    quote: str = Field(description="exact words from the person for a user fact, else empty")


class IntakeWire(BaseModel):
    action: Literal["ask", "start", "decline"]
    decision: Decision
    say: str
    cue1: str
    cue2: str
    quick_replies: list[str]
    goal: str
    library_id: str
    context_sufficient: bool
    facts: list[FactWire]
    critical_unknowns: list[str]
    question_key: str
    question_reason: str
    identification_help: str
    branch: str
    experience: Experience
    profile_facts: list[str]

    def reply(self) -> IntakeReply:
        d = self.model_dump()
        d["profile"] = {"experience": d.pop("experience"), "facts": d.pop("profile_facts")}
        d["facts"] = [{**f, "value": f["value"][:240], "quote": f["quote"][:300]} for f in d["facts"]]
        return IntakeReply.model_validate(d)


class StepWire(BaseModel):
    answer: str
    cue1: str
    cue2: str
    grounding: Literal["guide", "general", "unsure"]
    follow_up: str
    quick_replies: list[str]
    add_note: bool
    note_title: str
    decision: Decision
    facts: list[FactWire]
    critical_unknowns: list[str]
    branch: str

    def reply(self) -> StepReply:
        d = self.model_dump()
        d["facts"] = [{**f, "value": f["value"][:240], "quote": f["quote"][:300]} for f in d["facts"]]
        return StepReply.model_validate(d)
