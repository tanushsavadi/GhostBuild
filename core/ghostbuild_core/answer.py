"""Lossless word pagination within the existing text container's measured bounds."""

import textwrap
import unicodedata


# Non-ASCII symbols are spelled out, not dropped: "220 Ω" must never become "220".
_SPELL = {"’": "'", "‘": "'", "“": '"', "”": '"', "–": "-", "—": "-", "−": "-", "…": "...", "°": " DEG ", "×": "X",
          "Ω": " OHM ", "µ": "U", "μ": "U", "→": " TO ", "≈": " ABOUT ", "≥": " AT LEAST ", "≤": " AT MOST ", "±": " +/- "}


def pages(text: str) -> list[str]:
    # Fold unsupported typography, never use an ellipsis to drop an answer's tail.
    folded = unicodedata.normalize("NFKC", text)
    folded = unicodedata.normalize("NFKD", "".join(_SPELL.get(ch, ch) for ch in folded))
    folded = folded.encode("ascii", "ignore").decode().upper()
    lines = textwrap.wrap(
        " ".join(folded.split()),
        width=38,
        break_long_words=True,
        break_on_hyphens=False,
    )
    return ["\n".join(lines[i : i + 5]) for i in range(0, len(lines), 5)] or [
        "NO ANSWER AVAILABLE"
    ]
