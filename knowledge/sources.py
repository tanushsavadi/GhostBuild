"""Generic source adapter: an official web page or PDF -> numbered text blocks + its own images.

One adapter for any manufacturer/specialist page (Apple Support, Park Tool, Prusa, ...). No site-specific scraping rules,
no search-page scraping, no private APIs: a public page the person or the search step pointed to is fetched once,
reduced to headings/paragraphs/list items and the images it embeds, and cached. The compiler (knowledge/compile.py)
may only cite these blocks and use these images.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
from dataclasses import asdict, dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15 GhostBuild/1.0"
def _trust() -> tuple[tuple[str, ...], tuple[str, ...]]:
    try:
        d = json.loads((Path(__file__).with_name("source_trust.json")).read_text())
        return tuple(d.get("manufacturers", ())), tuple(d.get("specialists", ()))
    except (OSError, ValueError):
        return (), ()


MANUFACTURERS, SPECIALISTS = _trust()  # data: knowledge/source_trust.json
CACHE = "knowledge/live/sources_cache"
_SKIP = {"script", "style", "noscript", "svg", "nav", "footer", "header", "form", "button", "select", "template", "iframe"}
_BLOCK = {"h1": "h", "h2": "h", "h3": "h", "h4": "h", "p": "p", "li": "li", "td": "p", "dt": "p", "dd": "p", "figcaption": "p", "blockquote": "p"}


@dataclass
class Block:
    i: int
    kind: str  # h | p | li
    text: str


@dataclass
class Img:
    i: int
    src: str
    alt: str
    near: str  # the text block just before it (what the page says next to the picture)


@dataclass
class SourceDoc:
    url: str
    title: str
    kind: str  # EvidenceLabel for this source
    blocks: list[Block] = field(default_factory=list)
    images: list[Img] = field(default_factory=list)
    fetched_ms: int = 0

    def text(self) -> str:
        return "\n".join(b.text for b in self.blocks)

    def to_json(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_json(d: dict) -> "SourceDoc":
        return SourceDoc(url=d["url"], title=d["title"], kind=d["kind"], fetched_ms=d.get("fetched_ms", 0),
                         blocks=[Block(**b) for b in d["blocks"]], images=[Img(**x) for x in d["images"]])


def source_kind(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if any(host == d or host.endswith("." + d) for d in MANUFACTURERS):
        return "MANUFACTURER DOC"
    return "WEB TUTORIAL"


def trusted(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return any(host == d or host.endswith("." + d) for d in MANUFACTURERS + SPECIALISTS)


class _Page(HTMLParser):
    def __init__(self, base: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base, self.skip, self.cur, self.kind = base, 0, [], None
        self.blocks: list[tuple[str, str]] = []
        self.images: list[tuple[str, str, str]] = []
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in _SKIP:
            self.skip += 1
        if tag == "title":
            self._in_title = True
        if self.skip:
            return
        if tag in _BLOCK:
            self._flush()
            self.kind = _BLOCK[tag]
        if tag == "br":
            self.cur.append(" ")
        if tag in ("img", "source") and tag == "img":
            src = a.get("src") or a.get("data-src") or ""
            if not src and a.get("srcset"):
                src = a["srcset"].split(",")[-1].strip().split(" ")[0]
            if src and not src.startswith("data:"):
                near = self.blocks[-1][1] if self.blocks else ""
                self.images.append((urljoin(self.base, src), (a.get("alt") or "").strip(), near))

    def handle_endtag(self, tag):
        if tag in _SKIP and self.skip:
            self.skip -= 1
        if tag == "title":
            self._in_title = False
        if not self.skip and tag in _BLOCK:
            self._flush()

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        if not self.skip and self.kind:
            self.cur.append(data)

    def _flush(self):
        t = " ".join("".join(self.cur).split())
        if self.kind and len(t) >= 3:
            self.blocks.append((self.kind, t))
        self.cur, self.kind = [], None


def parse_html(url: str, body: str) -> SourceDoc:
    p = _Page(url)
    p.feed(body)
    p._flush()
    seen, blocks = set(), []
    for kind, t in p.blocks:
        if t in seen or len(t) > 1200:
            continue
        seen.add(t)
        blocks.append(Block(len(blocks), kind, html.unescape(t)))
    imgs, srcs = [], set()
    for src, alt, near in p.images:
        low = src.lower()
        if src in srcs or any(k in low for k in ("logo", "icon", "sprite", "avatar", "badge", "tracking", "pixel", ".svg", ".gif")):
            continue
        srcs.add(src)
        imgs.append(Img(len(imgs), src, alt[:200], near[:200]))
    title = " ".join(p.title.split()) or (blocks[0].text if blocks else url)
    return SourceDoc(url=url, title=title[:160], kind=source_kind(url), blocks=blocks[:400], images=imgs[:60])


def parse_pdf(url: str, data: bytes) -> SourceDoc:
    import fitz  # PyMuPDF, already a dependency of the manual pipeline

    doc = fitz.open(stream=data, filetype="pdf")
    blocks = []
    for pno, page in enumerate(doc):
        for para in re.split(r"\n\s*\n", page.get_text("text")):
            t = " ".join(para.split())
            if len(t) >= 3:
                blocks.append(Block(len(blocks), "p", f"[p{pno + 1}] {t}"[:1200]))
    title = (doc.metadata or {}).get("title") or url.rsplit("/", 1)[-1]
    # PDF pages are images too: the compiler may choose a page; image prep renders and crops it.
    imgs = [Img(i, f"{url}#page={i + 1}", f"page {i + 1}", "") for i in range(min(len(doc), 60))]
    return SourceDoc(url=url, title=title[:160], kind=source_kind(url), blocks=blocks[:600], images=imgs)


def fetch(url: str, root: Path, *, timeout_s: float = 20.0, refresh: bool = False, now_ms: Optional[int] = None) -> SourceDoc:
    """Fetch (or load the cached copy of) one public source page. Raises on HTTP errors or empty pages."""
    import time

    import httpx

    key = hashlib.sha1(url.encode()).hexdigest()[:16]
    path = root / CACHE / f"{key}.json"
    if path.is_file() and not refresh:
        return SourceDoc.from_json(json.loads(path.read_text()))
    r = httpx.get(url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}, timeout=timeout_s, follow_redirects=True)
    r.raise_for_status()
    ctype = r.headers.get("content-type", "")
    doc = parse_pdf(str(r.url), r.content) if "pdf" in ctype or url.lower().endswith(".pdf") else parse_html(str(r.url), r.text)
    if len(doc.blocks) < 3:
        raise ValueError(f"{url}: no readable content (the page may need a browser)")
    doc.fetched_ms = now_ms if now_ms is not None else int(time.time() * 1000)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc.to_json(), ensure_ascii=False))
    return doc


def fetch_image(src: str, root: Path, timeout_s: float = 20.0) -> bytes:
    """Bytes of one image the source embeds (or a rendered PDF page for `...pdf#page=N`)."""
    import httpx

    if "#page=" in src and src.split("#")[0].lower().endswith(".pdf"):
        import fitz

        pdf_url, page = src.split("#page=")
        data = httpx.get(pdf_url, headers={"User-Agent": UA}, timeout=timeout_s, follow_redirects=True).content
        pix = fitz.open(stream=data, filetype="pdf")[int(page) - 1].get_pixmap(dpi=110)
        return pix.tobytes("png")
    r = httpx.get(src, headers={"User-Agent": UA, "Referer": src}, timeout=timeout_s, follow_redirects=True)
    r.raise_for_status()
    return r.content


def normalize(text: str) -> str:
    t = html.unescape(text or "").lower()
    t = re.sub(r"[‘’´`]", "'", t)
    t = re.sub(r"[“”]", '"', t)
    t = re.sub(r"[–—−]", "-", t)
    return " ".join(re.sub(r"[^a-z0-9'%°.\- ]+", " ", t).split())


def quote_in(quote: str, doc: SourceDoc) -> bool:
    """Is this quote verbatim (after whitespace/punctuation normalisation) in the source?"""
    q = normalize(quote)
    return len(q) >= 12 and q in normalize(doc.text())
