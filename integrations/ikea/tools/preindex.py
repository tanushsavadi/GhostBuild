"""Pre-index genuine IKEA products for the demo: run real searches (Anthropic web_search restricted to ikea.com), validate every result
against its official page, keep the validated records (and their photos) in knowledge/products/ikea/index.json.

    uv run python -m integrations.ikea.tools.preindex            # default demo queries
    uv run python -m integrations.ikea.tools.preindex "white wardrobe" "billy bookcase"

Needs ANTHROPIC_API_KEY (backend only; read from the environment or .env). Records say when they were read; nothing is invented."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from ghostbuild_core.discovery.models import ProductRecord

from ..source import IkeaSource

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_QUERIES = [
    "white desk with one drawer and a cabinet", "white desk with two drawers", "black-brown desk with drawers", "white computer desk",
    "MICKE desk", "white corner desk", "white bookcase", "white wardrobe", "white tv unit", "white chest of drawers", "white dining table",
]


def _env() -> None:
    f = ROOT / ".env"
    if f.is_file() and not os.environ.get("ANTHROPIC_API_KEY"):
        for line in f.read_text().splitlines():
            if line.startswith("ANTHROPIC_API_KEY="):
                os.environ["ANTHROPIC_API_KEY"] = line.split("=", 1)[1].strip().strip('"').strip("'")


def main(argv: list[str]) -> int:
    _env()
    queries = argv or DEFAULT_QUERIES
    src = IkeaSource(ROOT)
    if not src.live_available():
        print("no ANTHROPIC_API_KEY: cannot run live search", file=sys.stderr)
        return 2
    keep: dict[str, ProductRecord] = {}
    log = []
    for q in queries:
        t0 = time.monotonic()
        out = src.search(q, 25.0, set())
        print(f"{q!r}: {len(out.records)} validated in {int((time.monotonic()-t0)*1000)} ms (search {out.search_ms} ms, validate {out.validate_ms} ms) {out.error or ''}")
        log.append({"query": q, "validated": [r.article for r in out.records], "search_ms": out.search_ms, "validate_ms": out.validate_ms, "error": out.error, "provider": out.provider})
        for r in out.records:
            keep.setdefault(r.article, r)
    base = ROOT / "knowledge" / "products" / "ikea"
    (base / "images").mkdir(parents=True, exist_ok=True)
    final = []
    for a, r in keep.items():
        if r.local_image and "/cache/images/" in r.local_image:
            src_f, dst = ROOT / r.local_image, base / "images" / f"{a}.jpg"
            if src_f.is_file():
                dst.write_bytes(src_f.read_bytes())
                r = r.model_copy(update={"local_image": str(dst.relative_to(ROOT))})
        final.append(r.model_copy(update={"how": "cache"}))
    existing = {}
    idx = base / "index.json"
    if idx.is_file():
        existing = {d["article"]: d for d in json.loads(idx.read_text()).get("records", [])}
    for r in final:
        existing[r.article] = r.model_dump(mode="json")
    idx.write_text(json.dumps({"note": "Records read from official ikea.com product pages (validated). Not a catalogue: only what these searches returned.",
                               "queries": log, "records": list(existing.values())}, indent=1))
    print(f"index now holds {len(existing)} validated records -> {idx}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
