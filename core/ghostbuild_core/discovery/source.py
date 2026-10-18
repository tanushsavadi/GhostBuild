"""What a product source (a retailer, a manufacturer) must provide. Core only knows this protocol; sources plug in from outside core."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional, Protocol

from contracts.models import Card

from .models import ConfigQuestion, ProductRecord


@dataclass
class Claim:
    """A source recognised the text as being about one of its products."""

    kind: Literal["url", "article", "text"]
    value: str
    article: Optional[str] = None


@dataclass
class LookupResult:
    record: Optional[ProductRecord] = None
    error: Optional[str] = None  # person-safe
    ms: int = 0
    origin: str = ""


@dataclass
class SearchResult:
    records: list[ProductRecord] = field(default_factory=list)
    search_ms: int = 0
    validate_ms: int = 0
    provider: str = ""
    error: Optional[str] = (
        None  # person-safe reason when live search gave nothing usable
    )
    unavailable: bool = False  # the provider is not configured / not reachable at all (vs. searched and found nothing)


class ProductSource(Protocol):
    id: str
    label: str

    def wants(self, text: str) -> bool:
        """Is this request about one of our products and an assembly/ownership intent? (casual mentions must return False)"""

    def claim(self, text: str) -> Optional[Claim]:
        """An exact reference (URL or article number) inside `text`, or None. Used while a discovery is already active, so a bare number counts."""

    def known_names(self) -> tuple[str, ...]: ...

    def cached(self) -> list[ProductRecord]:
        """Verified records we already hold (pre-indexed and learned)."""

    def lookup(self, claim: Claim, timeout_s: float) -> LookupResult: ...

    def search(self, query: str, timeout_s: float, exclude: set[str]) -> SearchResult:
        """Search the official site; every returned record has been validated against the official page."""

    def live_available(self) -> bool: ...

    def bundle(self, rec: ProductRecord) -> Optional["ManualBundle"]: ...

    def record_for(self, article: str) -> Optional[ProductRecord]: ...


@dataclass
class ManualBundle:
    """Everything derived from an official manual for one product, ready offline: playbook cards per configuration, the one question that picks
    the configuration, and short facts read from the manual (used only as labelled evidence when matching)."""

    source: str
    article: str
    name: str
    root: Path
    manual_url: str
    manual_title: str = ""
    config_question: Optional[ConfigQuestion] = None
    cards: dict[str, str] = field(
        default_factory=dict
    )  # option id (or "default") -> card file relative to root
    evidence: list[str] = field(default_factory=list)
    built_from: dict = field(default_factory=dict)

    def card_ids(self) -> list[str]:
        return [
            Card.model_validate(json.loads((self.root / p).read_text())).card_id
            for p in self.cards.values()
        ]

    def load_card(self, option: Optional[str]) -> Card:
        key = (
            option
            if option in self.cards
            else ("default" if "default" in self.cards else None)
        )
        if key is None:
            raise KeyError(f"no card for configuration {option!r}")
        return Card.model_validate(
            json.loads((self.root / self.cards[key]).read_text())
        )

    def all_cards(self) -> list[Card]:
        return [
            Card.model_validate(json.loads((self.root / p).read_text()))
            for p in self.cards.values()
        ]


def load_bundle(root: Path) -> Optional[ManualBundle]:
    """Read <root>/bundle.json (format v1). None when there is no bundle (the product has no cached manual yet)."""
    f = Path(root) / "bundle.json"
    if not f.is_file():
        return None
    d = json.loads(f.read_text())
    cq = (
        ConfigQuestion.model_validate(d["config_question"])
        if d.get("config_question")
        else None
    )
    return ManualBundle(
        source=d["source"],
        article=d["article"],
        name=d.get("name", ""),
        root=Path(root),
        manual_url=d["manual_url"],
        manual_title=d.get("manual_title", ""),
        config_question=cq,
        cards=dict(d["cards"]),
        evidence=list(d.get("evidence", [])),
        built_from=dict(d.get("built_from", {})),
    )
