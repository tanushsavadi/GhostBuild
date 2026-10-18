"""IKEA adapter: id/URL parsing, intent gating, official-page validation, exact lookup, cache, search + dedupe. Fully offline (fixtures are
trimmed copies of the real ikea.com pages; the search provider and fetcher are fakes)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ghostbuild_core.discovery.models import ProductRecord
from integrations.ikea import ids
from integrations.ikea.page import Fetched, PageError, fetch_product, parse_product_page
from integrations.ikea.search import AnthropicWebSearch, FakeSearch, SearchHit
from integrations.ikea.source import IkeaSource

FIX = Path(__file__).parent / "fixtures"
URL_1 = "https://www.ikea.com/us/en/p/micke-desk-white-80213074/"
URL_2 = "https://www.ikea.com/us/en/p/micke-desk-white-90214308/"
NOW = 1_800_000_000_000


class FakeFetcher:
    def __init__(self, pages: dict[str, str], pdf_ok=True, fail: set[str] | None = None):
        self.pages, self.pdf_ok, self.fail, self.gets, self.heads = pages, pdf_ok, fail or set(), [], []

    def get(self, url, timeout):
        self.gets.append(url)
        if url in self.fail:
            raise PageError("could not reach ikea.com (TimeoutError)")
        if url.endswith(".jpg"):
            return Fetched(200, url, "image/jpeg", b"\xff\xd8\xff" + b"0" * 50)
        key = url if url in self.pages else next((k for k in self.pages if url.rstrip("/").endswith(k.rstrip("/").split("-")[-1]) or k.endswith(url[-10:])), None)
        if key is None:
            return Fetched(404, url, "text/html", b"")
        return Fetched(200, key, "text/html", self.pages[key].encode())

    def head(self, url, timeout):
        self.heads.append(url)
        return Fetched(200 if self.pdf_ok else 404, url, "application/pdf" if self.pdf_ok else "text/html", b"")


def pages():
    return {URL_1: (FIX / "product_80213074.html").read_text(), URL_2: (FIX / "product_90214308.html").read_text()}


# ------------------------------------------------------------------------------------------------------------- ids
@pytest.mark.parametrize("text,art", [("802.130.74", "80213074"), ("article 802 130 74", "80213074"), ("80213074", "80213074"), ("S59422220", "s59422220"),
                                      ("it is 902-143-08 on the box", "90214308"), ("call 555 1234", None), ("1234567", None)])
def test_parse_article(text, art):
    assert ids.parse_article(text) == art


def test_parse_url_accepts_only_ikea_https_and_extracts_article():
    assert ids.parse_url(f"here is the link {URL_1}.") == (URL_1.rstrip("/"), "80213074") or ids.parse_url(f"here {URL_1}")[1] == "80213074"
    assert ids.parse_url("see http://www.ikea.com/us/en/p/micke-desk-white-80213074/")[1] == "80213074"
    assert ids.parse_url("https://evil.example/ikea.com/us/en/p/x-80213074/") is None
    assert ids.parse_url("https://www.ikea.com.evil.example/us/en/p/x-80213074/") is None
    assert ids.parse_url("https://www.ikea.com/us/en/cat/desks-20649/") == ("https://www.ikea.com/us/en/cat/desks-20649/", None)


def test_product_url_vs_category_and_series_pages():
    assert ids.is_product_url(URL_1) == "80213074"
    assert ids.is_product_url("https://www.ikea.com/us/en/p/-80213074/") == "80213074"
    assert ids.is_product_url("https://www.ikea.com/us/en/cat/micke-series-17499/") is None
    assert ids.is_product_url("http://www.ikea.com/us/en/p/x-80213074/") is None
    assert ids.is_product_url("https://example.com/us/en/p/x-80213074/") is None


@pytest.mark.parametrize("text", [
    "Help me assemble an IKEA desk.", "I'm building a white IKEA table with drawers.", "I have a MICKE desk.", "Help me assemble IKEA 80213074.",
    "Here's the IKEA product link https://www.ikea.com/us/en/p/micke-desk-white-80213074/", "I need help with this IKEA cabinet.",
    "build me my ikea sofa", "i bought a white ikea desk with a drawer and cabinet", "how do I put together the BILLY bookcase", "article number 802.130.74",
    "I have a white IKEA desk with a drawer and cabinet.",
])
def test_activates_for_real_requests(text):
    assert ids.wants_help_with_ikea_product(text)


@pytest.mark.parametrize("text", [
    "I love IKEA meatballs", "IKEA closes at nine tonight", "blink an LED on my pi", "fold a paper cup", "my camera view is black", "call me at 555 123 4567",
    "what time is it", "ikea", "the ikea near me is far",
])
def test_does_not_activate_for_casual_or_unrelated(text):
    assert not ids.wants_help_with_ikea_product(text)


def test_accents_fold():
    assert ids.known_name_in("my BESTÅ unit") == "BESTA"


# ------------------------------------------------------------------------------------------------------------- page validation
def test_parse_real_page_facts():
    rec = parse_product_page((FIX / "product_80213074.html").read_text(), URL_1, NOW)
    assert (rec.article, rec.article_display, rec.name, rec.type_name) == ("80213074", "802.130.74", "MICKE", "desk")
    assert rec.color == "white" and rec.product_url == URL_1 and rec.image_url.startswith("https://www.ikea.com/")
    assert rec.manual_url == "https://www.ikea.com/us/en/assembly_instructions/micke-desk-white__AA-476615-12-100.pdf"
    assert any("one drawer" in e for e in rec.evidence) and rec.verified_at == NOW and rec.manual_verified is False


def test_page_for_a_different_article_than_the_url_is_refused():
    with pytest.raises(PageError, match="address says"):
        parse_product_page((FIX / "product_90214308.html").read_text(), URL_1, NOW)


def test_page_without_article_or_image_is_refused():
    with pytest.raises(PageError):
        parse_product_page("<html><head><title>x</title></head><body>nothing</body></html>", URL_1, NOW)
    html = (FIX / "product_80213074.html").read_text().replace('property="og:image"', 'property="og:nope"')
    with pytest.raises(PageError, match="image"):
        parse_product_page(html, URL_1, NOW)


def test_fetch_product_checks_the_pdf_before_calling_it_verified():
    f = FakeFetcher(pages())
    assert fetch_product(f, URL_1, NOW).manual_verified is True and f.heads
    assert fetch_product(FakeFetcher(pages(), pdf_ok=False), URL_1, NOW).manual_verified is False


def test_fetch_product_404_is_an_error_not_a_guess():
    with pytest.raises(PageError, match="404"):
        fetch_product(FakeFetcher({}), URL_1, NOW)


# ------------------------------------------------------------------------------------------------------------- source
def make_source(tmp_path, hits=None, error=None, fetcher=None, provider=None):
    prov = provider or FakeSearch(hits or [], error=error)
    return IkeaSource(tmp_path, provider=prov, fetcher=fetcher or FakeFetcher(pages()), now_ms=lambda: NOW)


def test_exact_url_lookup_validates_remembers_and_then_serves_from_cache(tmp_path):
    f = FakeFetcher(pages())
    s = make_source(tmp_path, fetcher=f)
    r = s.lookup(s.claim(URL_1), 5)
    assert r.record and r.record.article == "80213074" and r.record.how == "exact_url" and "just now" in r.origin
    n = len(f.gets)
    r2 = s.lookup(s.claim("802.130.74"), 5)
    assert r2.record.how == "exact_article" and len(f.gets) == n and "saved record" in r2.origin  # no second page read
    assert (tmp_path / "knowledge/products/ikea/cache/records.json").is_file()
    s2 = make_source(tmp_path, fetcher=FakeFetcher({}))  # a new process still knows it
    assert s2.record_for("80213074").name == "MICKE"


def test_exact_lookup_of_a_category_link_explains_instead_of_guessing(tmp_path):
    s = make_source(tmp_path)
    r = s.lookup(s.claim("https://www.ikea.com/us/en/cat/desks-20649/"), 5)
    assert r.record is None and "not a product page" in r.error


def test_exact_lookup_unreadable_site_with_no_cache_is_an_honest_error(tmp_path):
    s = make_source(tmp_path, fetcher=FakeFetcher({}, fail={"https://www.ikea.com/us/en/p/-80213074/"}))
    r = s.lookup(s.claim("80213074"), 5)
    assert r.record is None and "Could not confirm" in r.error


def test_stale_cache_is_used_with_a_label_when_the_site_cannot_be_read(tmp_path):
    base = tmp_path / "knowledge/products/ikea"
    base.mkdir(parents=True)
    rec = parse_product_page((FIX / "product_80213074.html").read_text(), URL_1, NOW - 40 * 24 * 3600 * 1000)
    (base / "index.json").write_text(json.dumps({"records": [rec.model_dump(mode="json")]}))
    s = make_source(tmp_path, fetcher=FakeFetcher({}, fail={"https://www.ikea.com/us/en/p/-80213074/"}))
    r = s.lookup(s.claim("80213074"), 5)
    assert r.record is not None and "could not be read just now" in r.origin


def test_search_returns_only_validated_product_pages_deduped(tmp_path):
    hits = [SearchHit(URL_1, "MICKE desk, white"), SearchHit("https://www.ikea.com/us/en/cat/micke-series-17499/", "MICKE series"),
            SearchHit(URL_2, "MICKE desk, white"), SearchHit(URL_1, "dup"), SearchHit("https://evil.example/us/en/p/x-12345678/", "x"),
            SearchHit("https://www.ikea.com/us/en/p/ghost-desk-white-11111111/", "not real")]
    s = make_source(tmp_path, hits=hits)
    out = s.search("white desk drawer", 10, set())
    assert [r.article for r in out.records] == ["80213074", "90214308"]  # category, foreign host and a page that 404s are all dropped
    assert out.provider == "fake search" and out.error is None


def test_search_without_provider_key_is_unavailable_not_empty(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    s = IkeaSource(tmp_path, provider=AnthropicWebSearch(), fetcher=FakeFetcher(pages()), now_ms=lambda: NOW)
    assert s.live_available() is False
    out = s.search("white desk", 5, set())
    assert out.unavailable and out.records == []


def test_search_provider_error_is_reported(tmp_path):
    out = make_source(tmp_path, error="the search timed out").search("white desk", 5, set())
    assert out.error == "the search timed out" and out.records == []


def test_search_respects_exclude(tmp_path):
    s = make_source(tmp_path, hits=[SearchHit(URL_1, "a"), SearchHit(URL_2, "b")])
    assert [r.article for r in s.search("desk", 5, {"80213074"}).records] == ["90214308"]


def test_anthropic_provider_parses_search_result_blocks_and_ignores_model_text():
    class B:
        def __init__(self, **k): self.__dict__.update(k)
    resp = B(content=[B(type="text", text="https://www.ikea.com/us/en/p/made-up-99999999/"),
                      B(type="web_search_tool_result", content=[B(url=URL_1, title="MICKE"), B(url="https://www.ikea.com/us/en/cat/x/", title="cat")])])
    client = B(messages=B(create=lambda **kw: resp))
    out = AnthropicWebSearch(client=client).search("white desk", 5)
    assert [h.url for h in out.hits] == [URL_1, "https://www.ikea.com/us/en/cat/x/"] and out.error is None  # the model's own text never becomes a hit


def test_anthropic_provider_error_block_is_an_error_not_a_crash():
    class B:
        def __init__(self, **k): self.__dict__.update(k)
    resp = B(content=[B(type="web_search_tool_result", content=B(error_code="max_uses_exceeded"))])
    out = AnthropicWebSearch(client=B(messages=B(create=lambda **kw: resp))).search("x", 5)
    assert out.hits == [] and "max_uses_exceeded" in out.error

def test_related_series_images_never_supply_this_product_features():
    page=(FIX/'product_80213074.html').read_text()
    rec=parse_product_page(page,URL_1,NOW)
    assert not any('Black MICKE' in x or 'filing cabinet' in x for x in rec.evidence)
    assert any('one drawer' in x for x in rec.evidence)

def test_cached_records_never_keep_live_origin(tmp_path):
    source=make_source(tmp_path)
    rec=parse_product_page((FIX/'product_80213074.html').read_text(),URL_1,NOW)
    source._records[rec.article]=rec.model_copy(update={'how':'live_search'})
    assert source.cached()[0].how=='cache'
