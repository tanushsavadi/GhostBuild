"""Small, persistent decision policy around the existing assistant and task engine.

No domain scripts and no generated physical actions. User facts require a quote
from an accepted turn; model assumptions remain explicitly inferred.
"""

from __future__ import annotations

import re
import time
import uuid
from typing import Literal

from pydantic import BaseModel, Field

Decision = Literal[
    "ASK_QUESTION",
    "IDENTIFY_PRODUCT",
    "RESEARCH",
    "START_GUIDE",
    "CONTINUE_GUIDE",
    "SHOW_VISUAL",
    "EXPLAIN",
    "TROUBLESHOOT",
    "REQUEST_CONFIRMATION",
    "ESCALATE_OR_STOP",
]


class TaskFact(BaseModel):
    field: Literal[
        "product",
        "model",
        "variant",
        "symptom",
        "observation",
        "tool",
        "material",
        "configuration",
        "experience",
        "attempted",
        "safety",
        "branch",
    ]
    value: str = Field(max_length=240)
    origin: Literal["user", "inferred", "document"] = "inferred"
    quote: str = Field(default="", max_length=300)
    confidence: float = Field(default=0.5, ge=0, le=1)


class TaskProfile(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    goal: str = ""
    mode: str = "build"
    revision: int = 0
    phase: str = "intake"
    facts: list[TaskFact] = Field(default_factory=list)
    observations: list[str] = Field(default_factory=list)
    critical_unknowns: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    branch: str = ""
    confidence: float = 0
    pending_question: str = ""
    asked: list[str] = Field(default_factory=list)
    decisions: list[dict] = Field(default_factory=list)
    started_at: float = Field(default_factory=time.time)
    first_useful_at: float | None = None
    unnecessary_questions: int = 0
    confirmation_pending: str = ""

    def observe(self, text: str, *, revise: bool = True):
        self.observations.append(text)
        self.observations = self.observations[-40:]
        if revise and correction(text):
            # Do not let an old model/configuration masquerade as current fact.
            self.revision += 1
            self.facts = [
                f
                for f in self.facts
                if f.field
                not in ("product", "model", "variant", "configuration", "branch")
            ]
            self.sources = []
            self.branch = ""

    def merge(self, facts: list[TaskFact]):
        accepted = "\n".join(self.observations).casefold()
        for fact in facts:
            f = fact.model_copy()
            if f.origin != "inferred":
                # A model cannot declare a reference verified, or manufacture a user quote.
                f.origin = (
                    "user" if f.quote and f.quote.casefold() in accepted else "inferred"
                )
            if f.origin == "user":
                f.confidence = 1
                if f.field in (
                    "product",
                    "model",
                    "variant",
                    "configuration",
                    "experience",
                    "branch",
                ):
                    self.facts = [old for old in self.facts if old.field != f.field]
            if not any(
                old.field == f.field and old.value == f.value and old.origin == f.origin
                for old in self.facts
            ):
                self.facts.append(f)
        self.facts = self.facts[-80:]

    def record(self, decision: Decision, reason: str):
        now = time.time()
        self.decisions.append(
            {
                "decision": decision,
                "reason": reason,
                "at": now,
                "revision": self.revision,
                "critical_unknowns": list(self.critical_unknowns),
            }
        )
        self.decisions = self.decisions[-60:]
        if (
            decision
            in (
                "START_GUIDE",
                "CONTINUE_GUIDE",
                "SHOW_VISUAL",
                "EXPLAIN",
                "TROUBLESHOOT",
            )
            and self.first_useful_at is None
        ):
            self.first_useful_at = now

    def research_key(self) -> str:
        """Prefetched sources belong to one task, revision and named identity; naming the exact model means a new search."""
        ident = "|".join(f.value.casefold() for f in self.facts if f.origin == "user" and f.field in ("model", "variant"))
        return f"{self.id}:{self.revision}" + (f":{ident}" if ident else "")

    def signature(self):
        return {
            "goal": self.goal,
            "mode": self.mode,
            "revision": self.revision,
            "facts": [f.model_dump() for f in self.facts],
            "branch": self.branch,
            "critical_unknowns": self.critical_unknowns,
            "sources": self.sources,
        }

    def metrics(self):
        return {
            "questions": len(self.asked),
            "unnecessary_questions": self.unnecessary_questions,
            "time_to_first_useful_action_s": round(
                self.first_useful_at - self.started_at, 3
            )
            if self.first_useful_at
            else None,
        }


def correction(text: str) -> bool:
    return bool(
        re.search(
            r"\b(actually[, ]+(?:it'?s|it is|i have|mine|my|the model|this is)|correction|different model|wrong model|mine looks different|not the same|instead of|i meant)\b",
            text,
            re.IGNORECASE,
        )
    )


def new_goal(text: str) -> bool:
    t = text.strip().lower()
    return bool(
        re.search(
            r"\b(new (?:task|goal)|change (?:the )?task|forget (?:that|this)|start over)\b",
            t,
        )
        or re.match(
            r"^(?:(?:actually|now|instead|please)[, ]+)*(?:(?:i (?:want|need|would like) to|i(?: need|'d like| would like| want) (?:some )?help(?: with)?|"
            r"(?:can|could) you help me(?: with)?|help me(?: with)?)\s+)?"
            r"(?:build(?:ing)?|assembl(?:e|ing)|fix(?:ing)?|repair(?:ing)?|mak(?:e|ing)|fold(?:ing)?|set(?:ting)? up|install(?:ing)?)\b",
            t,
        )
    )


_SWITCH_VERB = r"(?:build|assemble|fix|repair|make|fold|set up|install|put together)"


def task_switch(text: str) -> bool:
    """While a guide is open: only an explicit change of task, never a question that starts with a verb ("fix it how?")."""
    t = text.strip().lower()
    return bool(
        re.search(
            r"\b(?:new (?:task|goal|project)|different (?:task|project)|something else|change (?:the )?task|"
            r"switch (?:tasks?|to (?:a |another |the )?(?:task|project|guide))|start over|forget (?:that|this)(?: task)?)\b",
            t,
        )
        or re.match(
            r"^(?:(?:actually|ok|okay|wait|now|so|instead)[, ]+)+(?:i (?:want|need|would like) to|help me|let'?s)\s+"
            + _SWITCH_VERB
            + r"\s+(?:a|an|my|some)\b",
            t,
        )
        or re.search(r"\b(?:i (?:want|need) to|help me|let'?s)\s+" + _SWITCH_VERB + r"\b.*\binstead\b", t)
    )


def identity_correction(text: str) -> bool:
    """While a guide is open: the person says the product/model itself is wrong, not just "actually, ..."."""
    return bool(
        re.search(
            r"\b(?:wrong|different|another) (?:model|product|version|article|item|one|kind|type|size)\b|\bmine (?:looks|is) different\b|"
            r"\bnot the same (?:model|product|one|kind|version)\b|\b(?:that|this|it)(?:'?s| is) not (?:my|the right|the same) (?:model|product|one|kind|version|thing)\b|"
            r"\bi (?:actually )?(?:have|bought|own) (?:a|an|the) [^.?!]{1,40}\b(?:model|version)\b[^.?!]*\b(?:instead|not)\b",
            text,
            re.IGNORECASE,
        )
    )


_REVISE = re.compile(r"\b(?:actually|wait|sorry|correction|i was wrong|i meant|turns out|just checked|checked again|on second thought|"
                     r"instead|not anymore|now it|too|also|as well|i misspoke|scratch that|my mistake)\b", re.I)
_HEDGE = re.compile(r"\b(?:i think|i guess|maybe|probably|might be|could be|possibly|not sure|not certain|seems?|looks like it)\b", re.I)


def revises(text: str) -> bool:
    """The person is changing something they said before (not just answering)."""
    return bool(_REVISE.search(text or "") or re.search(
        r"\b(?:it['’]?s|it is|mine is|i have)\b[^.?!]{1,80},?\s+not\s+(?:a |an |the )?\w+",
        text or "", re.I,
    ))


def hedged(text: str) -> bool:
    """A statement offered without certainty: confirm before acting on it."""
    return bool(_HEDGE.search(text or "")) or uncertain(text)


def uncertain(text: str) -> bool:
    return bool(
        re.search(
            r"\b(don't know|do not know|not sure|unsure|no idea|can't tell|cannot tell)\b",
            text,
            re.IGNORECASE,
        )
    )


def question_key(reply) -> str:
    text = reply.question_key or reply.say
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def same_topic(a: str, b: str) -> bool:
    """Two question keys ask about the same thing: one narrows or rewords the other."""
    ta, tb = set(a.split()), set(b.split())
    if not ta or not tb:
        return False
    return ta <= tb or tb <= ta or len(ta & tb) >= 0.6 * len(ta | tb)


def identified(task: TaskProfile) -> bool:
    """The person named the exact model or variant themselves (a quoted user fact, never an inference)."""
    return any(f.origin == "user" and f.field in ("model", "variant") for f in task.facts)


def decide(reply, task: TaskProfile, *, ready_exact: bool) -> Decision:
    if reply.action == "decline" or reply.decision == "ESCALATE_OR_STOP":
        return "ESCALATE_OR_STOP"
    if reply.decision in ("EXPLAIN", "SHOW_VISUAL"):
        return reply.decision
    asking = reply.decision in ("REQUEST_CONFIRMATION", "IDENTIFY_PRODUCT") or (
        reply.action == "ask"
        or task.critical_unknowns
        or not (reply.context_sufficient or ready_exact)
    )
    key = question_key(reply)
    # A reworded question counts as a repeat once its topic (the broadest earlier key it narrows) was asked twice.
    core = min((k for k in task.asked if same_topic(k, key)), key=len, default="")
    repeated = asking and (key in task.asked or (bool(core) and sum(same_topic(k, core) for k in task.asked) >= 2))
    if repeated and identified(task):
        # Asking the same thing again will not resolve it. With the exact model known, the official source is the
        # authority: a guide that covers each documented option and asks at the step where it matters.
        task.unnecessary_questions += 1
        return "START_GUIDE" if ready_exact else "RESEARCH"
    if reply.decision in ("REQUEST_CONFIRMATION", "IDENTIFY_PRODUCT"):
        return reply.decision
    if asking:
        if repeated:
            task.unnecessary_questions += 1
            return "EXPLAIN" if reply.identification_help else "ESCALATE_OR_STOP"
        return "ASK_QUESTION"
    return "START_GUIDE" if ready_exact else "RESEARCH"
