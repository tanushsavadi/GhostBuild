"""Deterministic goal resolver. No LLM, no network: loaded Cards (goal_mode, aliases, title) decide."""

from __future__ import annotations

import re

from contracts.models import Card, Cue, GoalRequest, GoalResolution

_STOP = {
    "a", "an", "the", "my", "of", "to", "is", "it", "its", "and", "or", "in", "on", "for", "with", "this", "that",
    "example", "fixture", "please", "help", "me", "fix", "build", "make", "set", "up", "i", "want", "need",
}


def short_title(title: str, limit: int) -> str:
    t = re.sub(r"\([^)]*\)", " ", title)
    t = re.sub(r"\s+", " ", t).strip().upper()
    if len(t) <= limit:
        return t
    cut = t[:limit].rstrip()
    if " " in cut and t[limit] != " ":
        cut = cut.rsplit(" ", 1)[0]
    return cut


def _tokens(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", s.lower()) if w not in _STOP and len(w) >= 2}


def _score(card: Card, text: str) -> int:
    low = text.lower()
    score = 0
    for a in card.aliases:
        a = a.strip().lower()
        if a and a in low:
            score += 3
    title_tokens = _tokens(re.sub(r"\([^)]*\)", " ", card.title))
    hits = len(title_tokens & _tokens(text))
    if hits >= 2 or (hits >= 1 and len(title_tokens) <= 1):
        score += hits
    return score


def _prefix(mode: str) -> str:
    return "FIX: " if mode == "fix" else "BUILD: "


def task_cue(card: Card, mode: str) -> Cue:
    pre = _prefix(mode)
    return Cue(line1=pre + short_title(card.title, 24 - len(pre)), line2="WATCHING NOW" if mode == "fix" else "FOLLOW THE CUES")


def resolve(req: GoalRequest, cards: list[Card]) -> GoalResolution:
    pool = [c for c in cards if c.goal_mode == req.mode]
    supported_titles = [c.title for c in cards]
    all_list = "; ".join(f"{c.title} ({c.goal_mode})" for c in cards) or "none"

    chosen: list[Card] = []
    text = (req.text or "").strip()
    if not text:
        chosen = pool  # exactly one => supported, several => ambiguous, none => unsupported
    else:
        scored = [(c, _score(c, text)) for c in pool]
        best = max((s for _, s in scored), default=0)
        chosen = [c for c, s in scored if s == best and s > 0]

    if len(chosen) == 1:
        c = chosen[0]
        cue = task_cue(c, req.mode)
        return GoalResolution(
            session_id=req.session_id,
            status="supported",
            mode=req.mode,
            card_id=c.card_id,
            task_title=c.title,
            cue=cue,
            detail=f"Supported: {c.title}. GhostBuild watches the Pi camera view and LED and shows one cue only when a test fails.",
            alternatives=[],
        )
    if len(chosen) > 1:
        return GoalResolution(
            session_id=req.session_id,
            status="ambiguous",
            mode=req.mode,
            cue=Cue(line1="WHICH ONE?", line2="SEE PHONE"),
            detail="Several supported tasks match; pick one on the phone: " + "; ".join(c.title for c in chosen),
            alternatives=[c.title for c in chosen],
        )
    first = (pool[0] if pool else (cards[0] if cards else None))
    try_line = ("TRY: " + short_title(first.title, 21)) if first else "TRY LATER"
    return GoalResolution(
        session_id=req.session_id,
        status="unsupported",
        mode=req.mode,
        cue=Cue(line1="NOT SUPPORTED YET", line2=try_line),
        detail=(
            f"GhostBuild has no verified card for that {req.mode} goal"
            + (f" ({text!r})" if text else "")
            + f". Supported cards: {all_list}. No diagnosis is guessed."
        ),
        alternatives=supported_titles,
    )
