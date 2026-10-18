"""Answer engine: answers free questions only from the current procedure. No model, no invented values.

Scores the question against the FAQ entries authored in the procedure (current step first, then the rest)
and falls back to the step's `why` / `where` lines. Below threshold -> None, and the caller shows ASK A MENTOR.
"""

from __future__ import annotations

import re

from contracts.models import Procedure

STOP = {
    "a", "an", "the", "is", "are", "does", "do", "did", "i", "it", "its", "to", "of", "in", "on", "my", "me",
    "this", "that", "should", "can", "you", "be", "for", "with", "and", "or", "am", "so", "now", "here", "there",
}
THRESHOLD = 0.5
OTHER_STEP_THRESHOLD = 0.75


def tokens(text: str) -> set[str]:
    out = set()
    for w in re.sub(r"[^a-z0-9 ]+", " ", text.lower().replace("'", "")).split():
        if w in STOP:
            continue
        if len(w) > 4 and w.endswith("er"):
            w = w[:-2]
        elif len(w) > 3 and w.endswith("s"):
            w = w[:-1]
        out.add(w)
    return out


def dice(a: set[str], b: set[str]) -> float:
    return 2 * len(a & b) / (len(a) + len(b)) if a and b else 0.0


def answer(question: str, proc: Procedure, idx: int) -> str | None:
    q = tokens(question)
    if not q:
        return None
    step = proc.steps[idx]
    best = max(((dice(q, tokens(f.q)), f.a) for f in step.faq), default=(0.0, None))
    if best[0] >= THRESHOLD:
        return best[1]
    if "why" in q and step.why:
        return step.why
    if q & {"where", "row", "go", "put", "place"} and step.where:
        return step.where
    others = [(dice(q, tokens(f.q)), f.a) for i, s in enumerate(proc.steps) if i != idx for f in s.faq]
    best = max(others, default=(0.0, None))
    return best[1] if best[0] >= OTHER_STEP_THRESHOLD else None
