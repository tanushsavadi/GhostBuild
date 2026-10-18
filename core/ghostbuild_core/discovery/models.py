"""Product discovery data. Generic: nothing here names a retailer, a product line or a device.

A ProductRecord is what an OFFICIAL page said about ONE real product (fetched and validated by a ProductSource). A Candidate is a
record plus why it ranked (which stated attributes the page's own text supports, which it does not mention). Nothing is invented:
a field the page did not give stays empty, and `verified_at` is the moment the facts were read from the official page.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

How = Literal["exact_url", "exact_article", "cache", "live_search"]
Phase = Literal[
    "idle",
    "searching",
    "choosing",
    "confirming",
    "asking",
    "configuring",
    "loading",
    "ready",
    "no_match",
    "unavailable",
]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProductRecord(Strict):
    source: str = Field(description="id of the ProductSource that validated it")
    article: str = Field(description="normalised article number, digits only")
    article_display: str = Field(
        default="", description="as the shop prints it, e.g. 802.130.74"
    )
    name: str = Field(min_length=1, max_length=80)
    type_name: str = Field(default="", max_length=80)
    color: str = Field(default="", max_length=60)
    size: str = Field(default="", max_length=60)
    description: str = Field(default="", max_length=800)
    evidence: list[str] = Field(
        default_factory=list,
        description="sentences the official page itself states (description, image alt texts); the only text features are matched against",
    )
    manual_evidence: list[str] = Field(
        default_factory=list,
        description="short facts read from a cached official manual (e.g. 'drawer', 'door'); labelled as manual-derived",
    )
    image_url: str = ""
    local_image: Optional[str] = Field(
        default=None, description="repo-relative path of the cached photo"
    )
    product_url: str
    manual_url: Optional[str] = None
    manual_verified: bool = Field(
        default=False,
        description="the official PDF URL answered 200 application/pdf when checked",
    )
    manual_cached: bool = Field(
        default=False,
        description="a derived bundle (playbooks + diagrams) is available offline",
    )
    verified_at: int = Field(
        default=0, description="epoch ms the facts were read from the official page"
    )
    how: How = "cache"


class Candidate(Strict):
    record: ProductRecord
    rank: int = Field(ge=1)
    score: float
    matched: list[str] = Field(
        default_factory=list,
        description="requested attributes the official text supports",
    )
    unverified: list[str] = Field(
        default_factory=list,
        description="requested attributes the official text does not mention (not the same as 'absent')",
    )
    conflicts: list[str] = Field(
        default_factory=list,
        description="requested attributes the official text contradicts",
    )
    origin: str = Field(
        default="",
        description="human-readable provenance: cached (date) or live official-site search",
    )


class Attrs(Strict):
    """What the person told us. Merged across turns; a newer statement replaces an older one about the same attribute."""

    category: Optional[str] = None
    color: Optional[str] = None
    features: dict[str, int | bool] = Field(
        default_factory=dict,
        description="feature -> count, or True/False (False = explicitly not wanted)",
    )
    name_hint: Optional[str] = None
    words: list[str] = Field(
        default_factory=list, description="free words kept for the search query"
    )

    def merged(self, new: "Attrs") -> "Attrs":
        feats = dict(self.features)
        feats.update(new.features)
        return Attrs(
            category=new.category or self.category,
            color=new.color or self.color,
            features=feats,
            name_hint=new.name_hint or self.name_hint,
            words=list(dict.fromkeys([*self.words, *new.words])),
        )

    def is_empty(self) -> bool:
        return not (self.category or self.color or self.features or self.name_hint)

    def describe(self) -> str:
        parts: list[str] = []
        if self.color:
            parts.append(self.color)
        if self.category:
            parts.append(self.category)
        for f, v in self.features.items():
            if v is False:
                parts.append(f"no {f}")
            elif v is True:
                parts.append(f"with {f}")
            else:
                parts.append(f"{v} {f}{'s' if v != 1 else ''}")
        if self.name_hint:
            parts.append(self.name_hint)
        return " ".join(parts)


class Question(Strict):
    """One distinguishing question built from the REAL differences between the current candidates."""

    id: str
    prompt: str
    options: list[str] = Field(min_length=2, max_length=4)
    feature: Optional[str] = None
    values: list[Optional[int | bool]] = Field(
        default_factory=list,
        description="the attribute value each option stands for (None = not sure)",
    )


class ConfigOption(Strict):
    id: str
    label: str
    image: Optional[str] = Field(
        default=None,
        description="core URL of a picture that shows this choice, from the manual",
    )


class ConfigQuestion(Strict):
    id: str
    prompt: str
    short_prompt: Optional[str] = Field(default=None, max_length=24)
    options: list[ConfigOption] = Field(min_length=2, max_length=4)
    help: str = ""


class Timings(Strict):
    total_ms: int = 0
    exact_ms: Optional[int] = None
    cache_ms: Optional[int] = None
    search_ms: Optional[int] = None
    validate_ms: Optional[int] = None
    provider: Optional[str] = None


class DiscoveryState(Strict):
    session_id: str
    phase: Phase = "idle"
    source: Optional[str] = None
    source_label: Optional[str] = None
    query: str = ""
    attrs: Attrs = Field(default_factory=Attrs)
    candidates: list[Candidate] = Field(default_factory=list)
    page: int = 0
    focus: Optional[int] = Field(
        default=None, description="index of the candidate shown alone on the glasses"
    )
    question: Optional[Question] = None
    pending: Optional[Candidate] = Field(
        default=None,
        description="an exact article/URL match waiting for a one-tap confirmation",
    )
    selected: Optional[ProductRecord] = None
    config_question: Optional[ConfigQuestion] = None
    config: dict[str, str] = Field(default_factory=dict)
    card_id: Optional[str] = None
    notice: str = ""
    search_mode: Literal["none", "cache", "live", "cache+live"] = "none"
    live_state: Literal["off", "running", "done", "failed", "unavailable"] = "off"
    timings: Timings = Field(default_factory=Timings)
    seen: list[str] = Field(
        default_factory=list,
        description="article numbers already shown (a 'show me more' skips them)",
    )
    message: str = Field(
        default="", description="what the specialist says right now, in plain words"
    )
    updated_ms: int = 0
