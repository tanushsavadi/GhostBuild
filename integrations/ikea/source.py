"""IkeaSource: the ProductSource for IKEA. Exact lookup, cached records, official-site search, and cached manual bundles."""

from __future__ import annotations

import json
import logging
import re
import time
from threading import RLock
from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures import TimeoutError as FuturesTimeout
from pathlib import Path
from typing import Callable, Optional

from ghostbuild_core.discovery.models import ProductRecord
from ghostbuild_core.discovery.source import Claim, LookupResult, ManualBundle, SearchResult, load_bundle

from . import ids
from .page import Fetcher, PageError, UrllibFetcher, fetch_product
from .search import AnthropicWebSearch, SearchProvider

log = logging.getLogger("ghostbuild.ikea")
FRESH_MS = 14 * 24 * 3600 * 1000  # a record read from the official page within two weeks is used without asking the site again
IMG_TIMEOUT = 6.0


class IkeaSource:
    id = "ikea"
    label = "IKEA"

    def __init__(self, root: Path | str, *, provider: Optional[SearchProvider] = None, fetcher: Optional[Fetcher] = None,
                 now_ms: Callable[[], int] = lambda: int(time.time() * 1000), locale: str = "us/en", workers: int = 5) -> None:
        self.root = Path(root)
        self.base = self.root / "knowledge" / "products" / "ikea"
        self.index_path = self.base / "index.json"        # pre-indexed, committed: records read from official pages ahead of the demo
        self.cache_path = self.base / "cache" / "records.json"  # learned at run time, not committed
        self.provider = provider if provider is not None else AnthropicWebSearch()
        self.fetcher = fetcher or UrllibFetcher()
        self.now_ms = now_ms
        self.locale = locale
        self.workers = workers
        self._lock = RLock()
        self._records: dict[str, ProductRecord] = {}
        self._pre: set[str] = set()
        self._load()

    @staticmethod
    def _scoped_evidence(rec):
        own=[]
        for text in rec.evidence:
            first=text.split('.')[0].lower()
            pattern=r"\b"+re.escape(rec.name.lower())+r"\s+(?:[a-z-]+\s+){0,2}"+re.escape(rec.type_name.lower())+r"\b"
            if not re.search(pattern,first): continue
            if rec.color and rec.color.lower() not in first: continue
            own.append(text)
        return rec.model_copy(update={"evidence":own})

    # ------------------------------------------------------------------ store
    def _load(self) -> None:
        for path, pre in ((self.index_path, True), (self.cache_path, False)):
            if not path.is_file():
                continue
            try:
                for d in json.loads(path.read_text()).get("records", []):
                    r = ProductRecord.model_validate(d)
                    r = self._scoped_evidence(r)
                    self._records[r.article] = r
                    if pre:
                        self._pre.add(r.article)
            except Exception:
                log.exception("could not read %s", path)

    def _save_cache(self) -> None:
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            learned = [r.model_dump(mode="json") for a, r in self._records.items() if a not in self._pre]
            tmp = self.cache_path.with_suffix(".tmp")
            tmp.write_text(json.dumps({"records": learned}, indent=1))
            tmp.replace(self.cache_path)
        except Exception:
            log.exception("could not write the record cache")

    def _remember(self, rec: ProductRecord, *, pre: bool = False) -> ProductRecord:
        with self._lock:
            return self._remember_locked(rec, pre=pre)

    def _remember_locked(self, rec: ProductRecord, *, pre: bool = False) -> ProductRecord:
        b = self.bundle(rec)
        rec = rec.model_copy(update={"manual_cached": b is not None, "manual_evidence": list(b.evidence) if b else rec.manual_evidence})
        old = self._records.get(rec.article)
        if old is not None and old.local_image and not rec.local_image:
            rec = rec.model_copy(update={"local_image": old.local_image})
        self._records[rec.article] = rec
        if pre:
            self._pre.add(rec.article)
        else:
            self._save_cache()
        return rec

    def _with_bundle(self, rec: ProductRecord) -> ProductRecord:
        b = self.bundle(rec)
        return rec.model_copy(update={"manual_cached": b is not None, "manual_evidence": list(b.evidence) if b else rec.manual_evidence})

    # ------------------------------------------------------------------ ProductSource
    def wants(self, text: str) -> bool:
        return ids.wants_help_with_ikea_product(text, self.known_names())

    def claim(self, text: str) -> Optional[Claim]:
        u = ids.parse_url(text)
        if u:
            return Claim("url", u[0], u[1])
        a = ids.parse_article(text)
        return Claim("article", a, a) if a else None

    def known_names(self) -> tuple[str, ...]:
        return tuple(sorted({r.name for r in self._records.values()} | set(ids.KNOWN_NAMES)))

    def cached(self) -> list[ProductRecord]:
        return [self._with_bundle(r.model_copy(update={"how": "cache"})) for r in list(self._records.values())]

    def record_for(self, article: str) -> Optional[ProductRecord]:
        r = self._records.get(article.lower())
        return self._with_bundle(r) if r else None

    def live_available(self) -> bool:
        return bool(getattr(self.provider, "available", lambda: True)())

    def bundle(self, rec: ProductRecord) -> Optional[ManualBundle]:
        return load_bundle(self.base / rec.article)

    def auto_card(self, rec: ProductRecord) -> Optional[dict]:
        """No prepared bundle: build a per-step guide from the validated official manual (see auto_manual.py)."""
        from .auto_manual import build_card

        return build_card(article=rec.article, name=rec.name, pdf_url=rec.manual_url, product_url=rec.product_url, root=self.root)

    def lookup(self, claim: Claim, timeout_s: float = 10.0) -> LookupResult:
        t0 = time.monotonic()
        article = claim.article
        if claim.kind == "url" and article is None:
            return LookupResult(error="That link is on ikea.com but is not a product page. Open the product's own page and paste that link, or type its article number.")
        assert article is not None
        have = self._records.get(article)
        now = self.now_ms()
        if have is not None and now - have.verified_at < FRESH_MS and have.verified_at > 0:
            return LookupResult(self._with_bundle(have.model_copy(update={"how": "exact_url" if claim.kind == "url" else "exact_article"})),
                                ms=int((time.monotonic() - t0) * 1000), origin=f"saved record, read from ikea.com {_day(have.verified_at)}")
        url = claim.value if claim.kind == "url" else ids.canonical_url(article, self.locale)
        try:
            rec = fetch_product(self.fetcher, url, now, timeout=min(timeout_s, 9.0))
        except PageError as e:
            if have is not None:  # the site could not be read: the saved record is still real, and it is labelled as old
                return LookupResult(self._with_bundle(have.model_copy(update={"how": "exact_article"})), ms=int((time.monotonic() - t0) * 1000),
                                    origin=f"saved record from {_day(have.verified_at)} (ikea.com could not be read just now: {e})")
            return LookupResult(error=f"Could not confirm that on ikea.com: {e}.", ms=int((time.monotonic() - t0) * 1000))
        rec = rec.model_copy(update={"how": "exact_url" if claim.kind == "url" else "exact_article"})
        rec = self._remember(self._with_image(rec))
        return LookupResult(rec, ms=int((time.monotonic() - t0) * 1000), origin="read from ikea.com just now")

    def search(self, query: str, timeout_s: float = 18.0, exclude: Optional[set[str]] = None) -> SearchResult:
        exclude = exclude or set()
        if not self.live_available():
            return SearchResult(provider=getattr(self.provider, "name", ""), unavailable=True, error="live search is not set up on this machine")
        out = self.provider.search(query, min(timeout_s, 20.0))
        if out.error:
            return SearchResult(provider=out.provider, search_ms=out.ms, error=out.error, unavailable=("not configured" in out.error or "authoris" in out.error))
        t0 = time.monotonic()
        wanted: dict[str, str] = {}
        for h in out.hits:
            a = ids.is_product_url(h.url)
            if a and a not in wanted and a not in exclude:
                wanted[a] = h.url
        recs: dict[str, ProductRecord] = {}
        now = self.now_ms()
        todo: dict[str, str] = {}
        for a, u in wanted.items():
            have = self._records.get(a)
            if have is not None and now - have.verified_at < FRESH_MS and have.verified_at > 0:
                recs[a] = self._with_bundle(have.model_copy(update={"how": "live_search"}))
            else:
                todo[a] = u
        if todo:
            budget = max(3.0, timeout_s - out.ms / 1000.0)
            ex = ThreadPoolExecutor(max_workers=min(self.workers, len(todo)))
            futs = {ex.submit(self._validate, u): a for a, u in todo.items()}
            try:
                for f in as_completed(futs, timeout=budget):
                    try:
                        rec = f.result()
                    except Exception:  # a page that did not validate is simply not a candidate (never shown, never guessed)
                        continue
                    if rec is not None:
                        recs[futs[f]] = rec
            except FuturesTimeout:
                log.info("some official pages were too slow; showing the ones that validated")
            ex.shutdown(wait=False, cancel_futures=True)
        ordered = [recs[a] for a in wanted if a in recs]
        return SearchResult(records=ordered, search_ms=out.ms, validate_ms=int((time.monotonic() - t0) * 1000), provider=out.provider)

    def _validate(self, url: str) -> Optional[ProductRecord]:
        try:
            rec = fetch_product(self.fetcher, url, self.now_ms(), timeout=8.0)
        except PageError as e:
            log.info("page refused: %s (%s)", url, e)
            return None
        return self._remember(self._with_image(rec.model_copy(update={"how": "live_search"})))

    def _with_image(self, rec: ProductRecord) -> ProductRecord:
        """Keep a local copy of the official product photo (the glasses image is made from it; the phone shows it offline)."""
        if rec.local_image and (self.root / rec.local_image).is_file():
            return rec
        try:
            dest = self.base / "cache" / "images" / f"{rec.article}.jpg"
            dest.parent.mkdir(parents=True, exist_ok=True)
            r = self.fetcher.get(rec.image_url, IMG_TIMEOUT) if rec.image_url.startswith("https://www.ikea.com/") else None
            if r is not None and r.status == 200 and r.body[:3] in (b"\xff\xd8\xff", b"\x89PN"):
                dest.write_bytes(r.body)
                return rec.model_copy(update={"local_image": str(dest.relative_to(self.root))})
        except (PageError, OSError):
            pass
        return rec


def _day(ms: int) -> str:
    return time.strftime("%Y-%m-%d", time.gmtime(ms / 1000))
