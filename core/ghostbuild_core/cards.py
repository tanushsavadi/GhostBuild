"""Load Repair Cards from a directory. Invalid cards are skipped with a logged warning, never fatal."""

from __future__ import annotations

import json
import os
import logging
from pathlib import Path

from contracts.models import Card

log = logging.getLogger("ghostbuild.cards")


def load_cards(directory: Path | str) -> list[Card]:
    d = Path(directory)
    cards: list[Card] = []
    if not d.is_dir():
        log.warning("cards directory %s does not exist", d)
        return cards
    # Compiled guides (knowledge/compiled/<id>/card.json, a sibling of the cards directory) use the same contract.
    compiled = sorted((d.parent / "compiled").glob("*/card.json")) if os.getenv("GB_COMPILED_CARDS", "1") != "0" else []
    for p in sorted(d.glob("*.json")) + compiled:
        try:
            raw = json.loads(p.read_text())
        except Exception as exc:
            log.warning("skipping %s: unreadable JSON (%s)", p, exc)
            continue
        if not isinstance(raw, dict) or "card_id" not in raw or not ("tests" in raw or "steps" in raw):
            log.debug("skipping %s: not a Repair Card", p)
            continue
        try:
            cards.append(Card.model_validate(raw))
        except Exception as exc:
            log.warning("skipping invalid card %s: %s", p, str(exc).splitlines()[0:3])
    seen: set[str] = set()
    out = []
    for c in cards:
        if c.card_id in seen:
            log.warning("duplicate card_id %s ignored", c.card_id)
            continue
        seen.add(c.card_id)
        out.append(c)
    return out
