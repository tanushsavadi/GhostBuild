"""Small persistent reuse cache for completed work, never physical evidence.

Matching is deliberately conservative: wording/order can change, but identity,
quantities, negations and requested configuration remain part of the key. Cache
misses do not guess a product or transfer a completion to another task.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
import unicodedata
from pathlib import Path
from typing import Any

from contracts.models import Card

log = logging.getLogger("ghostbuild.cache")
VERSION = 1
ANSWER_TTL_S = 7 * 24 * 3600
_STOP = frozenset(
    [
        "a",
        "an",
        "the",
        "i",
        "me",
        "my",
        "mine",
        "we",
        "our",
        "you",
        "your",
        "please",
        "kindly",
        "can",
        "could",
        "would",
        "will",
        "help",
        "need",
        "want",
        "like",
        "have",
        "has",
        "own",
        "just",
        "also",
        "actually",
        "really",
        "some",
        "to",
        "for",
        "with",
        "of",
        "in",
        "on",
        "and",
        "how",
        "do",
        "does",
        "am",
        "is",
        "are",
        "it",
        "this",
        "that",
        "instructions",
        "instruction",
        "guide",
        "tutorial",
        "show",
        "tell",
        "building",
        "build",
        "making",
        "make",
        "assemble",
        "assembling",
        "assembly",
        "put",
        "together",
    ]
)
_WORDS = {
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
    "repair": "fix",
    "repairing": "fix",
    "fixing": "fix",
    "setup": "setup",
    "blinking": "blink",
    "blinks": "blink",
    "folding": "fold",
    "folds": "fold",
    "connecting": "connect",
    "connects": "connect",
    "tightening": "tighten",
    "tightens": "tighten",
    "screws": "screw",
    "fasteners": "fastener",
    "drawers": "drawer",
    "cabinets": "cabinet",
    "bolts": "bolt",
    "desks": "desk",
}


def folded(text: str) -> str:
    return (
        unicodedata.normalize("NFKD", text.replace("’", "'"))
        .encode("ascii", "ignore")
        .decode()
        .lower()
    )


def terms(text: str) -> frozenset[str]:
    text = folded(text)
    text = re.sub(r"\b(?:i'm|i've|it's|that's)\b", " ", text)
    text = re.sub(r"\bset(?:ting)? up\b", "setup", text)
    text = re.sub(r"\bdon[\s\']?t\b", "not", text)
    return frozenset(
        _WORDS.get(t, t)
        for t in re.findall(r"[a-z0-9]+(?:[.-][a-z0-9]+)*", text)
        if t not in _STOP and t
    )


def _relations(text: str) -> list[str]:
    # Preserve which object a quantity or negation modifies. A bag of words
    # alone would confuse "two drawers, three shelves" with the reverse.
    words = [_WORDS.get(t, t) for t in re.findall(r"[a-z0-9]+", folded(text))]
    relations = []
    for i, word in enumerate(words):
        if word.isdigit() or word in {"no", "not", "without", "left", "right"}:
            tail = [w for w in words[i + 1 :] if w not in _STOP][:2]
            relations.append(" ".join([word, *tail]))
    return sorted(relations)


def goal_key(text: str, mode: str) -> str:
    return digest(
        {"mode": mode, "terms": sorted(terms(text)), "relations": _relations(text)}
    )


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode()
    ).hexdigest()


def reusable_question(text: str) -> bool:
    """Only standalone guide questions: follow-up pronouns depend on the conversation."""
    return len(terms(text)) >= 2 and not re.search(
        r"\b(it|that|this|these|those|they|them|instead|earlier|previous|again|my|mine)\b",
        folded(text),
    )


def question_key(text: str) -> dict:
    t = folded(text)
    intent = next(
        (
            x
            for x in ("why", "where", "how", "when", "which", "what")
            if re.search(r"\b" + x + r"\b", t)
        ),
        "question",
    )
    return {"intent": intent, "terms": sorted(terms(t)), "relations": _relations(t)}


class AppCache:
    def __init__(
        self, path: Path | None, *, enabled: bool | None = None, now=time.time
    ):
        self.path = path
        self.enabled = (
            os.getenv("GB_SMART_CACHE", "1") != "0" if enabled is None else enabled
        )
        self.now = now
        self.data: dict[str, dict[str, dict]] = {
            "guides": {},
            "answers": {},
            "products": {},
        }
        self.hits = {"guides": 0, "answers": 0, "products": 0}
        self.misses = {"guides": 0, "answers": 0, "products": 0}
        if self.enabled and path and path.is_file():
            try:
                raw = json.loads(path.read_text())
                if isinstance(raw, dict) and raw.get("v") == VERSION:
                    for name in self.data:
                        rows = raw.get(name, {})
                        if isinstance(rows, dict):
                            self.data[name] = {
                                k: v
                                for k, v in rows.items()
                                if isinstance(v, dict)
                                and "value" in v
                                and isinstance(v.get("at", 0), (int, float))
                                and (
                                    v.get("expires") is None
                                    or isinstance(v["expires"], (int, float))
                                )
                            }
            except (ValueError, OSError):
                log.warning(
                    "saved reuse cache could not be read; using the normal lookup path"
                )

    def _save(self):
        if not self.enabled or self.path is None:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps({"v": VERSION, **self.data}))
            tmp.replace(self.path)
        except OSError:
            log.warning(
                "could not persist reuse cache; current-session reuse remains available"
            )

    def get(self, namespace: str, key: str):
        if not self.enabled:
            return None
        item = self.data[namespace].get(key)
        if item and (not item.get("expires") or item["expires"] > self.now()):
            self.hits[namespace] += 1
            return item["value"]
        self.misses[namespace] += 1
        return None

    def put(self, namespace: str, key: str, value: Any, *, ttl: float = 0):
        if not self.enabled:
            return
        self.data[namespace][key] = {
            "at": self.now(),
            "expires": self.now() + ttl if ttl else None,
            "value": value,
        }
        limit = 120 if namespace == "guides" else 250
        while len(self.data[namespace]) > limit:
            first = min(
                self.data[namespace], key=lambda k: self.data[namespace][k].get("at", 0)
            )
            del self.data[namespace][first]
        self._save()

    def remember_guide(
        self, text: str, mode: str, card: Card, review: dict | None = None
    ):
        if not terms(text):
            return
        self.put(
            "guides",
            goal_key(text, mode),
            {
                "request": text[:300],
                "mode": mode,
                "card": card.model_dump(mode="json"),
                "review": review or {},
            },
        )

    def guide(self, text: str, mode: str):
        value = self.get("guides", goal_key(text, mode))
        if not value:
            return None
        try:
            return Card.model_validate(value["card"]), value.get("review", {})
        except (ValueError, KeyError, TypeError):
            return None

    def saved_guides(self):
        """Validated snapshots allow session restore before any providers are configured."""
        if not self.enabled:
            return []
        found = {}
        for item in self.data["guides"].values():
            try:
                value = item["value"]
                card = Card.model_validate(value["card"])
                found[card.card_id] = (card, value.get("review", {}))
            except (ValueError, KeyError, TypeError):
                continue
        return list(found.values())

    def status(self):
        return {
            "enabled": self.enabled,
            "persistent": self.path is not None,
            "entries": {n: len(rows) for n, rows in self.data.items()},
            "hits": dict(self.hits),
            "misses": dict(self.misses),
        }
