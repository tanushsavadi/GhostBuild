"""Deterministic voice intent resolver + grounded answers.

No LLM is required. A transcript is lowercased and matched against fixed phrase rules to ONE intent from a closed enum.
Answers are assembled ONLY from fields of the active Repair Card (GuideView.fallback/title, Check.action/why, Test.fact).
Nothing here writes free prose to the HUD. Pure functions: no engine, no HUD, no IO (voice.py applies the Reply).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal, Optional

from contracts.models import Card, Check, Cue, EvidenceLabel, Guide, Test

Intent = Literal[
    "where", "how", "correct_look", "why", "fallback_if_failed", "next_picture", "previous_picture", "status", "goal_text", "unknown"
]
INTENTS: tuple[str, ...] = (
    "where", "how", "correct_look", "why", "fallback_if_failed", "next_picture", "previous_picture", "status", "goal_text", "unknown",
)

L1, L2 = 24, 26  # HudFrame cue limits

NOT_SURE = Cue(line1="NOT SURE", line2="TRY: WHERE? HOW?")
NOT_IN_CARD = Cue(line1="NOT IN MY CARD", line2="SEE PHONE")
DIDNT_CATCH = Cue(line1="DIDN'T CATCH THAT", line2="TRY AGAIN OR TAP")
UNAVAILABLE = Cue(line1="VOICE UNAVAILABLE", line2="USE TOUCH")
CONSENT = Cue(line1="HOLD TO TALK", line2="AUDIO SENT TO SERVER")
LISTENING = Cue(line1="LISTENING", line2="RELEASE WHEN DONE")
THINKING = Cue(line1="THINKING", line2="")


def normalize(text: str) -> str:
    t = text.lower().replace("’", "'").replace("`", "'")
    t = re.sub(r"[^a-z0-9' ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


# Order matters: first matching rule wins. More specific phrasings come before generic words.
_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("next_picture", (r"\bnext\b", r"\bforward\b", r"\bone more\b", r"\bnext (picture|view|image|one|step)\b")),
    ("previous_picture", (r"\bprevious\b", r"\bgo back\b", r"\bback up\b", r"\blast (one|picture|view)\b", r"^back$")),
    (
        "fallback_if_failed",
        (
            r"\bdid not work\b", r"\bdidn't work\b", r"\bdoesn't work\b", r"\bdoes not work\b", r"\bnot working\b",
            r"\bwhat if\b", r"\bstill (black|dark|broken|lost|not|the same|wrong)\b", r"\bnothing (changed|happened)\b",
            r"\bno luck\b", r"\bfailed\b", r"\botherwise\b", r"\bwhat else\b", r"\bnext check\b",
        ),
    ),
    ("correct_look", (r"\blook like\b", r"\blooks like\b", r"\bsupposed to look\b", r"\bcorrect (view|picture|look|state)\b", r"\bgood (look|view|state)\b", r"\bwhat is correct\b", r"\bwhat's correct\b", r"\bshould it look\b")),
    ("why", (r"\bwhy\b", r"\bmatter\b", r"\breason\b", r"\bimportant\b", r"\bwhat causes\b")),
    ("where", (r"\bwhere\b", r"\bwhich part\b", r"\bpoint (to|at)\b", r"\blocate\b", r"\bshow me where\b")),
    ("how", (r"\bhow\b", r"\bfix it\b", r"\bwhat (do|should|can) i do\b", r"\bsteps?\b", r"\bwhat now\b", r"\binstructions?\b")),
    (
        "status",
        (
            r"\bstatus\b", r"\bwhat's wrong\b", r"\bwhat is wrong\b", r"\bwhats wrong\b", r"\bis it (fixed|ok|okay|working|good)\b",
            r"\bam i done\b", r"\bany (problem|problems|issue|issues)\b", r"\ball good\b", r"\bworking now\b", r"\bhow('s| is) it going\b",
        ),
    ),
]
_COMPILED = [(name, [re.compile(p) for p in pats]) for name, pats in _RULES]


def classify(text: str) -> Intent:
    """Rules only. 'goal_text' is decided by voice.py (it needs session context); this returns unknown for goal-like text."""
    t = normalize(text)
    if not t:
        return "unknown"
    for name, pats in _COMPILED:
        if any(p.search(t) for p in pats):
            return name  # type: ignore[return-value]
    return "unknown"


# --------------------------------------------------------------------------- goal text helpers
_FIX_WORDS = re.compile(
    r"\b(fix|broken|black|dark|blank|not working|doesn't|does not|won't|wrong|lost|repair|problem|stuck|covered|dead|no picture)\b"
)
_BUILD_WORDS = re.compile(r"\b(set ?up|build|assemble|install|put together|new station)\b")


def infer_goal_mode(text: str) -> Literal["fix", "build"]:
    t = normalize(text)
    if _FIX_WORDS.search(t):
        return "fix"
    if _BUILD_WORDS.search(t):
        return "build"
    return "fix"


# --------------------------------------------------------------------------- grounded answers
def wrap_two_lines(text: str) -> Optional[Cue]:
    """Greedy word wrap (UPPERCASE) into line1<=24 / line2<=26. None if it does not fit in two lines. Adds nothing."""
    words = text.upper().split()
    if not words:
        return None
    l1: list[str] = []
    i = 0
    while i < len(words) and len(" ".join(l1 + [words[i]])) <= L1:
        l1.append(words[i])
        i += 1
    if not l1:
        return None
    rest = " ".join(words[i:])
    if len(rest) > L2:
        return None
    return Cue(line1=" ".join(l1), line2=rest)


_INTERNAL_NOTE = re.compile(r"placeholder|calibrat|todo|unverified|not verified", re.I)


def fragments(why: str) -> list[str]:
    """Whole sentences of Check.why in document order (never clause fragments: they can change the meaning). Internal authoring notes skipped."""
    sentences = [s.strip(" .") for s in re.split(r"(?<=[.!?])\s+", why.strip()) if s.strip(" .")]
    return [s for s in sentences if not _INTERNAL_NOTE.search(s)]


def shorten_why(why: str) -> Optional[Cue]:
    for f in fragments(why):
        cue = wrap_two_lines(f)
        if cue is not None:
            return cue
    return None


@dataclass(frozen=True)
class Ctx:
    """Read-only snapshot of the active task, built by voice.py from the engine. No engine reference leaks in here."""

    card: Card
    fault: Optional[Test] = None  # the test currently failing (card order = priority)
    check: Optional[Check] = None
    check_idx: int = 0
    guide: Optional[Guide] = None
    help_open: bool = False
    erroring: bool = False  # link lost / camera unavailable or frozen: no confident answer
    measured_pass: bool = False


@dataclass(frozen=True)
class Reply:
    """What voice.py should do. `kind`:
    show      -> ask-mode text (cue) on the HUD for a few seconds
    help_goto -> open the existing guide view `target` (where|how|correct|next|previous)
    status    -> healthy status request (engine decides; a recheck, never a commit)
    suppress  -> an error is on screen; stay silent rather than answer confidently
    """

    kind: Literal["show", "help_goto", "status", "suppress"]
    cue: Optional[Cue] = None
    target: Optional[str] = None
    phone_text: Optional[str] = None  # full card text for the phone (Evidence event)
    phone_label: Optional[EvidenceLabel] = None
    fallback_cue: Optional[Cue] = None  # shown if help_goto finds nothing to open
    notes: list[str] = field(default_factory=list)


def _not_in_card(ctx: Ctx, why_full: Optional[str]) -> Reply:
    return Reply(kind="show", cue=NOT_IN_CARD, phone_text=why_full, phone_label=ctx.card.provenance if why_full else None)


def answer(intent: Intent, ctx: Ctx) -> Reply:
    if intent == "unknown":
        return Reply(kind="show", cue=NOT_SURE)
    if ctx.erroring:
        return Reply(kind="suppress")
    if ctx.fault is None:
        # Healthy (or nothing measured yet): every task question gets the existing press-when-healthy status. Never VERIFIED unmeasured.
        return Reply(kind="status")
    check = ctx.check
    if intent in ("where", "how", "correct_look"):
        view = {"where": "where", "how": "how", "correct_look": "correct"}[intent]
        return Reply(kind="help_goto", target=view, fallback_cue=check.action if check else ctx.fault.fact)
    if intent == "next_picture":
        return Reply(kind="help_goto", target="next", fallback_cue=NOT_IN_CARD)
    if intent == "previous_picture":
        return Reply(kind="help_goto", target="previous", fallback_cue=Cue(line1="NO PREVIOUS VIEW", line2="SAY: WHERE?"))
    if intent == "status":
        return Reply(kind="show", cue=ctx.fault.fact)
    if intent == "why":
        why = check.why if check else None
        cue = shorten_why(why) if why else None
        return Reply(kind="show", cue=cue, phone_text=why, phone_label=ctx.card.provenance) if cue else _not_in_card(ctx, why)
    if intent == "fallback_if_failed":
        checks = ctx.fault.checks
        nxt = checks[ctx.check_idx + 1] if ctx.check_idx + 1 < len(checks) else None
        if nxt is not None:
            return Reply(kind="show", cue=nxt.action, phone_text=nxt.why, phone_label=ctx.card.provenance)
        return _not_in_card(ctx, check.why if check else None)
    return Reply(kind="show", cue=NOT_SURE)


# --------------------------------------------------------------------------- playbook follow-ups (/ask and the voice lane)
PbIntent = Literal["where", "how", "correct", "repeat", "why", "faq", "troubleshoot", "next", "back", "picture", "status", "unknown"]

NOT_IN_PLAYBOOK = Cue(line1="NOT IN MY PLAYBOOK", line2="SEE PHONE")

_PB_STATUS = re.compile(r"\b(which|what) step\b|\bwhere am i\b|\bprogress\b|\bhow many (steps?|left)\b|\bstatus\b|\bam i done\b|\bsteps? (left|remaining)\b")
_PB_PICTURE = re.compile(r"\b(show|see|open|display)\b.*\b(picture|photo|image|diagram|pic|view)\b|\bpicture\b|\bphoto\b|\bdiagram\b")
_PB_NEXT = re.compile(
    r"^(?:(?:ok|okay|please) )?(?:next(?: step)?|done|finished|continue|go on|move on|forward|all done|"
    r"(?:i've|i have|i am|i'm|im) (?:done|finished)(?: (?:that|this|with this|with that))?)"
    r"(?: (?:what's|what is) next)?(?: please)?$"
)
_PB_HOW = re.compile(r"\bshow (?:me )?how\b|\bhow (?:do|should|can) i\b|^how$|\bhow (?:view|picture)\b")
_PB_CORRECT = re.compile(r"\b(?:look like|looks like|should it look|correct (?:view|picture|look))\b|^correct$")
_PB_REPEAT = re.compile(r"^(?:please )?(?:repeat|repeat that|say that again|what did you say|explain that again)(?: please)?$")

_PB_BACK = re.compile(r"^(?:please )?(?:back|previous|go back|previous step|last step|go back to the previous step)(?: please)?$")

_PB_TROUBLE = re.compile(
    r"\bdid not work\b|\bdidn't work\b|\bdoesn't work\b|\bdoes not work\b|\bnot working\b|\bwhat if\b|\bstill (not|wrong|broken|dark|off)\b|"
    r"\bnothing (changed|happened)\b|\bno luck\b|\bfailed\b|\bstuck\b|\bwon't\b|\bwhat else\b|\bproblem\b"
)
_PB_WHERE = re.compile(r"\bwhere\b|\bwhich part\b|\blocate\b")
_PB_WHY = re.compile(r"\bwhy\b|\bmatter\b|\breason\b|\bimportant\b")

_FAQ_STOP = {"the", "a", "an", "is", "are", "do", "does", "i", "it", "to", "of", "my", "me", "how", "what", "this", "that", "in", "on", "and", "or", "can", "should", "which"}


def _stem(w: str) -> str:
    for suf in ("ing", "es", "ed", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            return w[: -len(suf)]
    return w


def _content(text: str) -> set[str]:
    return {_stem(w) for w in normalize(text).split() if w not in _FAQ_STOP and len(w) >= 2}


def faq_best(text: str, faqs: list) -> Optional[tuple[int, float]]:
    """Index and overlap ratio of the FAQ question sharing the most content tokens with `text`, or None below the bar.
    Bar: at least 2 shared tokens, or the single content token of a one-word question. Ties go to the earlier FAQ (card order)."""
    mine = _content(text)
    best: Optional[tuple[int, int, float]] = None
    for i, fq in enumerate(faqs):
        theirs = _content(fq.q)
        if not theirs:
            continue
        shared = len(mine & theirs)
        if shared < 2 and not (shared == 1 and len(theirs) == 1):
            continue
        ratio = shared / len(theirs)
        if ratio < 0.5:
            continue
        if best is None or (shared, ratio) > (best[1], best[2]):
            best = (i, shared, ratio)
    return (best[0], best[2]) if best else None


def classify_playbook(text: str, faqs: list) -> PbIntent:
    t = normalize(text)
    if not t:
        return "unknown"
    if faq_best(t, faqs) is not None:
        return "faq"
    if _PB_STATUS.search(t):
        return "status"
    if _PB_TROUBLE.search(t):
        return "troubleshoot"
    if _PB_NEXT.search(t):
        return "next"
    if _PB_BACK.search(t):
        return "back"
    if _PB_REPEAT.search(t):
        return "repeat"
    if _PB_CORRECT.search(t):
        return "correct"
    if _PB_HOW.search(t):
        return "how"
    if _PB_PICTURE.search(t):
        return "picture"
    if _PB_WHERE.search(t):
        return "where"
    if _PB_WHY.search(t):
        return "why"
    return "unknown"
