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


def _stem(w: str) -> str:
    """Light, deterministic stemming so 'blinking'/'blinks' match 'blink'."""
    for suf in ("ing", "es", "ed", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            return w[: -len(suf)]
    return w


def _words(s: str) -> list[str]:
    return [_stem(w) for w in re.findall(r"[a-z0-9]+", s.lower())]


def _tokens(s: str) -> set[str]:
    """Content tokens (stop words removed), stemmed."""
    return {_stem(w) for w in re.findall(r"[a-z0-9]+", s.lower()) if w not in _STOP and len(w) >= 2}


def _has_phrase(words: list[str], phrase: list[str]) -> bool:
    n = len(phrase)
    return n > 0 and any(words[i : i + n] == phrase for i in range(len(words) - n + 1))


_MODEL = re.compile(r"(?<![\w.+-])(?=[a-z0-9.+-]*\d)(?=[a-z0-9.+-]*[a-z])[a-z0-9][a-z0-9.+-]{1,15}(?![\w.+-])", re.I)
_UNITS = re.compile(r"^\d+(?:mm|cm|m|in|v|w|mah|gb|tb|hz|s|min|h|x|nd|st|rd|th|k)$", re.I)


def model_tokens(text: str) -> set[str]:
    """Affirmed identifiers containing letters and digits; exclude units and negated models."""
    out = set()
    for m in _MODEL.finditer(text or ""):
        if re.search(r"\b(?:not|isn['’]?t|isnt|instead of|rather than)\s+(?:a |an |the |my )?$", text[:m.start()], re.I):
            continue
        t = m.group(0).strip(".-").lower()
        if len(t) >= 2 and not _UNITS.match(t):
            out.add(t)
    return out


def model_conflict(text: str, card: Card) -> bool:
    """The person names a model and this model-specific card is for a different one (it names models, none of them theirs)."""
    said = model_tokens(text)
    if not said:
        return False
    theirs = model_tokens(" ".join([card.title, *card.aliases]))
    return bool(theirs) and not (said & theirs)


def _score(card: Card, text: str) -> int:
    """Deterministic: +3 per alias whose (stemmed) words appear in order in the text, +1 per shared title token when
    at least two are shared (or the title has a single content token). No LLM, no network."""
    words = _words(text)
    score = 0
    for a in card.aliases:
        if _has_phrase(words, _words(a)):
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
    if card.steps:
        line2 = "ANY TAP: FIRST QUESTION" if card.steps[0].kind == "question" else "SWIPE DOWN WHEN DONE"
    else:
        line2 = "WATCHING NOW" if mode == "fix" else "FOLLOW THE CUES"
    return Cue(line1=pre + short_title(card.title, 24 - len(pre)), line2=line2)


def candidates(req: GoalRequest, cards: list[Card]) -> list[Card]:
    """Cards the goal could mean, best first (score desc, then short title, then id). Menu confirm (no text): the whole
    goal_mode pool. Free text: the best-scoring cards only (ties kept); empty if nothing matches."""
    pool = [c for c in cards if c.goal_mode == req.mode]
    key = lambda c: (short_title(c.title, 40), c.card_id)  # noqa: E731
    text = (req.text or "").strip()
    if not text:
        return sorted(pool, key=key)
    scored = [(c, 0 if model_conflict(text, c) else _score(c, text)) for c in pool]
    best = max((s for _, s in scored), default=0)
    if best <= 0:
        return []
    return sorted((c for c, s in scored if s == best), key=key)


def option_label(card: Card, taken: set[str]) -> str:
    base = short_title(card.title, 24)
    label, n = base, 2
    while label in taken:
        suffix = f" {n}"
        label = base[: 24 - len(suffix)].rstrip() + suffix
        n += 1
    taken.add(label)
    return label


def chooser_options(chosen: list[Card]) -> tuple[list[Card], list[str], bool]:
    """Menu allows up to 4 options: all cards when at most 4 are loaded, else 3 cards + `MORE ON PHONE`."""
    more = len(chosen) > 4
    shown = chosen[:3] if more else chosen[:4]
    taken: set[str] = set()
    labels = [option_label(c, taken) for c in shown]
    if more:
        labels.append(MORE_ON_PHONE)
    return shown, labels, more


MORE_ON_PHONE = "MORE ON PHONE"


def _supported_detail(c: Card) -> str:
    if c.steps:
        return f"Supported: {c.title}. {len(c.steps)} steps; swipe down on the glasses to confirm each step you finish. Steps with a check advance only on measured evidence."
    return f"Supported: {c.title}. GhostBuild shows one cue only when a test on the connected device fails."


def resolve(req: GoalRequest, cards: list[Card]) -> GoalResolution:
    pool = [c for c in cards if c.goal_mode == req.mode]
    supported_titles = [c.title for c in cards]
    all_list = "; ".join(f"{c.title} ({c.goal_mode})" for c in cards) or "none"
    text = (req.text or "").strip()
    chosen = candidates(req, cards)

    if len(chosen) == 1:
        c = chosen[0]
        return GoalResolution(
            session_id=req.session_id,
            status="supported",
            mode=req.mode,
            card_id=c.card_id,
            task_title=c.title,
            cue=task_cue(c, req.mode),
            detail=_supported_detail(c),
            alternatives=[],
        )
    if len(chosen) > 1:
        return GoalResolution(
            session_id=req.session_id,
            status="ambiguous",
            mode=req.mode,
            cue=Cue(line1="WHICH ONE?", line2="SEE PHONE"),
            detail="Several supported tasks match; pick one on the glasses menu or the phone: " + "; ".join(c.title for c in chosen),
            alternatives=[c.title for c in chosen],
        )
    if not text and not pool:
        other = any(c.goal_mode != req.mode for c in cards)
        return GoalResolution(
            session_id=req.session_id,
            status="unsupported",
            mode=req.mode,
            cue=Cue(line1="NOTHING LOADED YET", line2="TRY THE OTHER OPTION" if other else "SEE PHONE"),
            detail=f"No {req.mode} task is loaded on this device. Loaded: {all_list}. Nothing is guessed.",
            alternatives=supported_titles,
        )
    first = pool[0] if pool else (cards[0] if cards else None)
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
