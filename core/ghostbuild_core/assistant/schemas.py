"""Data shapes the assistant exchanges with a brain (an LLM) and keeps per session. Pure data: no IO, no engine, no HUD."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Experience = Literal["unknown", "first_time", "some", "experienced"]
MAX_FACTS = 8


class Profile(BaseModel):
    """What we know about the wearer for THIS session. Built from their own words; never guessed, never shared beyond the prompt."""

    experience: Experience = "unknown"
    facts: list[str] = Field(default_factory=list, description="short statements the wearer made: 'has a breadboard', 'Pi 4', 'no soldering iron'")

    def merged(self, update: "Profile") -> "Profile":
        facts = list(self.facts)
        for f in update.facts:
            f = " ".join(f.split())[:120]
            if f and f.lower() not in {x.lower() for x in facts}:
                facts.append(f)
        return Profile(experience=update.experience if update.experience != "unknown" else self.experience, facts=facts[-MAX_FACTS:])

    def describe(self) -> str:
        level = {"first_time": "a first-timer (explain plainly, define terms, warn about common mistakes)",
                 "some": "has some experience (brief explanations are fine)",
                 "experienced": "experienced (be concise, skip basics)",
                 "unknown": "experience level not known yet"}[self.experience]
        return f"Experience: {level}." + (" Known: " + "; ".join(self.facts) + "." if self.facts else "")


class IntakeReply(BaseModel):
    """One conversational turn before a guide exists: ask the next question, start the guide, or decline."""

    action: Literal["ask", "start", "decline"]
    say: str = Field(description="what to say to the person, 1-2 short plain sentences (shown on the phone, spoken in earbuds)")
    cue1: str = Field(default="", description="glasses line 1: at most 24 characters, ALL CAPS, the question in a few words")
    cue2: str = Field(default="", description="glasses line 2: at most 26 characters, ALL CAPS")
    quick_replies: list[str] = Field(default_factory=list, description="up to 4 short tap-to-answer options, only for 'ask'")
    goal: str = Field(default="", description="for 'start': the task as one clear sentence including every specific the person gave")
    library_id: str = Field(default="", description="for 'start': the exact id of a ready guide that fits, else empty")
    profile: Profile = Field(default_factory=Profile, description="what this turn taught you about the person")


class StepReply(BaseModel):
    """One answer about the step the wearer is on."""

    answer: str = Field(description="the full answer, plain language, at most ~45 words; for the phone and earbuds")
    cue1: str = Field(default="", description="glasses line 1: at most 24 characters, ALL CAPS")
    cue2: str = Field(default="", description="glasses line 2: at most 26 characters, ALL CAPS")
    grounding: Literal["guide", "general", "unsure"] = Field(description="guide = the guide's own text covers it; general = standard well-established knowledge beyond the guide; unsure = cannot answer reliably")
    follow_up: str = Field(default="", description="ONE short clarifying question if a good answer needs it, else empty")
    quick_replies: list[str] = Field(default_factory=list, description="up to 4 short tap-to-answer options for the follow-up")
    add_note: bool = Field(default=False, description="true if this answer adds lasting help for THIS step and should be kept on it")
    note_title: str = Field(default="", description="a 3-6 word title for the note")


class Message(BaseModel):
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
