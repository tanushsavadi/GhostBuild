"""Official-site search: Anthropic's documented server-side web_search tool, restricted to ikea.com.

The provider returns only (url, title) pairs; the model's own words are ignored. Each URL is later validated by reading the official
page (page.py). Measured 2026-10-18: claude-opus-5-5 + web_search_20250305, one search, ~5.5 s; claude-haiku-5-5 timed out at 40 s."""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Optional, Protocol

log = logging.getLogger("ghostbuild.ikea.search")

SYSTEM = (
    "You find official IKEA product pages. Run exactly one web search restricted to ikea.com, using short keywords for the furniture type, "
    "colour and distinguishing features the person described. Do not answer from memory and do not write anything else."
)


@dataclass
class SearchHit:
    url: str
    title: str


@dataclass
class SearchOutcome:
    hits: list[SearchHit] = field(default_factory=list)
    ms: int = 0
    provider: str = ""
    error: Optional[str] = None  # person-safe reason ("no key", "timed out", ...)


class SearchProvider(Protocol):
    name: str

    def search(self, query: str, timeout_s: float) -> SearchOutcome: ...


class AnthropicWebSearch:
    """claude-opus-5-5 at low effort + web_search (allowed_domains=["ikea.com"]). Needs ANTHROPIC_API_KEY on the backend only."""

    def __init__(self, model: Optional[str] = None, tool: Optional[str] = None, client=None) -> None:
        self.model = model or os.environ.get("GB_DISCOVERY_MODEL") or "claude-opus-5-5"
        self.tool = tool or os.environ.get("GB_DISCOVERY_SEARCH_TOOL") or "web_search_20250305"
        self.name = f"anthropic web_search ({self.model}, {self.tool}, allowed_domains=ikea.com)"
        self._client = client

    def available(self) -> bool:
        return self._client is not None or bool(os.environ.get("ANTHROPIC_API_KEY"))

    def _cl(self, timeout_s: float):
        if self._client is not None:
            return self._client
        import anthropic

        return anthropic.Anthropic(timeout=timeout_s, max_retries=0)

    def search(self, query: str, timeout_s: float = 15.0) -> SearchOutcome:
        t0 = time.monotonic()
        if not self.available():
            return SearchOutcome(provider=self.name, error="live search is not configured")
        try:
            r = self._cl(timeout_s).messages.create(
                model=self.model, max_tokens=800, system=SYSTEM, output_config={"effort": "low"},
                tools=[{"type": self.tool, "name": "web_search", "max_uses": 1, "allowed_domains": ["ikea.com"]}],
                messages=[{"role": "user", "content": f"IKEA US product page for: {query}"}],
            )
        except Exception as exc:  # typed SDK errors all mean the same here: no live results (timeout, rate limit, no web search access)
            log.info("ikea web search failed: %s", type(exc).__name__)
            return SearchOutcome(provider=self.name, ms=int((time.monotonic() - t0) * 1000), error=_reason(exc))
        hits: list[SearchHit] = []
        for b in getattr(r, "content", []) or []:
            if getattr(b, "type", "") != "web_search_tool_result":
                continue
            content = getattr(b, "content", None)
            if isinstance(content, list):  # an error is a single object, a success is a list
                for x in content:
                    url, title = getattr(x, "url", ""), getattr(x, "title", "")
                    if url:
                        hits.append(SearchHit(url=url, title=title))
            else:
                return SearchOutcome(provider=self.name, ms=int((time.monotonic() - t0) * 1000), error=f"web search error: {getattr(content, 'error_code', 'unknown')}")
        return SearchOutcome(hits=hits, ms=int((time.monotonic() - t0) * 1000), provider=self.name)


def _reason(exc: Exception) -> str:
    n = type(exc).__name__
    if "Timeout" in n:
        return "the search timed out"
    if "Authentication" in n or "PermissionDenied" in n:
        return "live search is not authorised on this key"
    if "RateLimit" in n:
        return "the search is rate limited right now"
    if "Connection" in n:
        return "no network to the search service"
    return f"the search failed ({n})"


class FakeSearch:
    """Scripted provider for tests and offline demos. Records its queries."""

    name = "fake search"

    def __init__(self, hits: list[SearchHit] | None = None, error: Optional[str] = None, delay_s: float = 0.0) -> None:
        self.hits, self.error, self.delay_s = hits or [], error, delay_s
        self.queries: list[str] = []

    def search(self, query: str, timeout_s: float = 15.0) -> SearchOutcome:
        self.queries.append(query)
        if self.delay_s:
            time.sleep(self.delay_s)
        return SearchOutcome(hits=list(self.hits), ms=int(self.delay_s * 1000), provider=self.name, error=self.error)
