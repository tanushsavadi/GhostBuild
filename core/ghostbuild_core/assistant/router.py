"""Plain command or real question? Pure decision, no engine side effects.

The deterministic engine is fast, free and exactly right for navigation and for the card's own FAQ/checks. It is wrong for a real question
("how do I identify the three servo wires") because 'how do I' alone replays the current step. So: commands and FAQ stay deterministic;
anything with specific content goes to the assistant when one is available."""

from __future__ import annotations

import re
from typing import Literal, Optional, Protocol

from .. import intent as intent_mod

Route = Literal["deterministic", "assistant", "notes"]

# words that carry no subject by themselves (kept in sync with the playbook's own deictic list)
CONVERSATIONAL = frozenset(
    "where why how there here that this these those it does should would could please tell explain show look like correct matter important "
    "reason part thing go connect do step done finish when more simply again exactly really need suppos wait hold hey okay well actually "
    "sorry um umm uh er hmm ok just now right confused lost sure can you mean closer bigger picture photo image what which who "
    "know understand help stuck".split()
)

_NOTES = re.compile(r"\b(what did you (say|tell)|remind me|what was that|say that again|repeat (that|the (tip|note|advice))|your (tip|note|advice) (again|for this))\b")
_PURE = frozenset(("next", "back", "status", "picture", "repeat", "goto"))


class _Playbook(Protocol):  # the slice of PlaybookEngine the router needs
    @property
    def step(self): ...

    def specific_terms(self, text: str) -> set[str]: ...

    def checks_remaining(self) -> int: ...


def specific_terms(text: str, extra_generic: frozenset[str] = frozenset()) -> set[str]:
    return {t for t in intent_mod._content(text) if t not in CONVERSATIONAL and t not in extra_generic}


def route(text: str, pb: _Playbook, *, assistant_available: bool, has_notes: bool = False) -> Route:
    if not assistant_available:
        return "deterministic"
    t = intent_mod.normalize(text)
    if intent_mod.returns_to_step(text):
        return "deterministic"
    if has_notes and _NOTES.search(t):
        return "notes"
    intent = intent_mod.classify_playbook(text, pb.step.faq)
    if intent in _PURE or intent == "faq":
        return "deterministic"
    if intent == "parts":  # printed identifiers/quantities answer selection; explanations need an answer
        if re.search(r"\b(?:what does|how does|how do|why|explain|what is (?:a|an))\b", t):
            return "assistant"
        return "deterministic" if pb.step.parts else "assistant"
    if intent == "troubleshoot":
        return "deterministic" if pb.checks_remaining() > 0 else "assistant"
    if not pb.specific_terms(text):  # "where is that", "show me how", "why do I do this"
        return "deterministic"
    return "assistant"
