"""Turn free text into a glasses cue: the glyph whitelist, ALL CAPS, two short lines. Pure functions.

The glasses draw one small font and silently drop what they lack, so text from a model is folded to the same safe subset the
card validator uses before it can reach the display. Nothing here decides WHAT to say."""

from __future__ import annotations

import re
import unicodedata

from contracts.models import Cue

L1, L2 = 24, 26
SAFE = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 .-/'?!:,()+=·●")
_FOLD = {"’": "'", "‘": "'", "“": "", "”": "", '"': "", "–": "-", "—": "-", "−": "-", "…": "...", "&": " AND ", "%": " PERCENT ", ";": ",",
         "°": " DEG ", "×": "X", "Ω": " OHM ", "µ": "U", "μ": "U", "→": " TO ", "≈": " ABOUT ", "≥": " AT LEAST ", "≤": " AT MOST "}


def sanitize(text: str) -> str:
    s = unicodedata.normalize("NFKC", str(text or ""))
    s = "".join(_FOLD.get(ch, ch) for ch in s)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().upper()
    s = "".join(ch if ch in SAFE else " " for ch in s)
    return re.sub(r"\s+", " ", s).strip(" ,:-")


def _wrap(words: list[str]) -> tuple[str, str]:
    line1: list[str] = []
    i = 0
    while i < len(words) and len(" ".join(line1 + [words[i]])) <= L1:
        line1.append(words[i])
        i += 1
    if not line1 and words:  # one very long word: hard-cut it
        return words[0][:L1], ""
    rest = " ".join(words[i:])
    if len(rest) <= L2:
        return " ".join(line1), rest
    cut = rest[: L2 - 3].rsplit(" ", 1)[0].rstrip(" ,:-")  # never end mid-word
    return " ".join(line1), (cut or rest[: L2 - 3]) + "..."


def fit_cue(text: str) -> Cue:
    """Best-effort two-line cue from any text (the first sentence-ish chunk that matters most)."""
    words = sanitize(text).split()
    l1, l2 = _wrap(words) if words else ("", "")
    return Cue(line1=l1 or "?", line2=l2)


def cue_from_reply(cue1: str, cue2: str, fallback_text: str) -> Cue:
    """Prefer the brain's own short cue if it survives sanitising and fits; else wrap the full text."""
    a, b = sanitize(cue1), sanitize(cue2)
    if a and len(a) <= L1 and len(b) <= L2:
        return Cue(line1=a, line2=b)
    return fit_cue(fallback_text)
