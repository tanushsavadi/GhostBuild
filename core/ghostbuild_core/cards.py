"""Load Repair Cards from a directory. Invalid cards are skipped with a logged warning, never fatal."""

from __future__ import annotations

import json
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
    for p in sorted(d.glob("*.json")):
        try:
            raw = json.loads(p.read_text())
        except Exception as exc:
            log.warning("skipping %s: unreadable JSON (%s)", p, exc)
            continue
        if not isinstance(raw, dict) or "card_id" not in raw or "tests" not in raw:
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
