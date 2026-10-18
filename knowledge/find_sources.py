"""Source discovery for an uncached task: Anthropic's documented server-side web_search tool, then pick official/specialist pages.

Cold path only. Returns page URLs the compiler may fetch; it never reads search-result pages itself and never scrapes.
Manufacturer and specialist repair sites rank first (knowledge/sources.py). Up to `limit` distinct pages.
"""

from __future__ import annotations

import logging
import os
import re
import time
from urllib.parse import urlparse

from .sources import MANUFACTURERS, SPECIALISTS, trusted

log = logging.getLogger("ghostbuild.find_sources")
SYSTEM = ("Find the official manufacturer support/manual page(s), or a well-established specialist repair guide, that give the actual "
          "step-by-step procedure or troubleshooting for the task. Prefer the manufacturer. Avoid forums, videos, shops and SEO blogs. "
          "Reply with the best 1-3 page URLs, one per line, best first.")


def find_sources(task: str, *, limit: int = 3, timeout_s: float = 40.0, client=None) -> tuple[list[str], dict]:
    import anthropic

    t0 = time.monotonic()
    client = client or anthropic.Anthropic(timeout=timeout_s, max_retries=1)
    tool = os.environ.get("GB_SOURCE_SEARCH_TOOL", "web_search_20250305")
    r = client.messages.create(
        model=os.environ.get("GB_COMPILE_MODEL", "claude-opus-5-5"), max_tokens=1200, system=SYSTEM, output_config={"effort": "low"},
        tools=[{"type": tool, "name": "web_search", "max_uses": 3}],
        messages=[{"role": "user", "content": f"Task: {task}"}],
    )
    results, text = [], ""
    for b in getattr(r, "content", []) or []:
        if getattr(b, "type", "") == "web_search_tool_result" and isinstance(getattr(b, "content", None), list):
            results += [x.url for x in b.content if getattr(x, "url", "")]
        elif getattr(b, "type", "") == "text":
            text += b.text + "\n"
    chosen = [u.rstrip(").,]") for u in re.findall(r"https?://[^\s<>\"']+", text)]
    pool = [u for u in dict.fromkeys(chosen + results) if urlparse(u).scheme == "https" and not re.search(r"youtube|reddit|forum|amazon\.|ebay\.", u)]
    rank = lambda u: (0 if any(urlparse(u).netloc.endswith(d) for d in MANUFACTURERS) else 1 if trusted(u) else 2, pool.index(u))
    urls = sorted(pool, key=rank)[:limit]
    return urls, {"search_s": round(time.monotonic() - t0, 2), "tool": tool, "results": len(results), "picked": urls,
                  "trusted": [u for u in urls if trusted(u)], "searches": getattr(getattr(r, "usage", None), "server_tool_use", None) and getattr(r.usage.server_tool_use, "web_search_requests", None)}
