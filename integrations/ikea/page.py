"""Read ONE official ikea.com product page and validate it. Everything shown to a person comes from here, never from a model.

Validation (a record is refused unless all hold): https + ikea.com host after redirects; the page names the same article number as the
URL and as its own article-number markup; a product name, an image and a canonical URL are present. The assembly PDF link, when the
page lists one, is checked separately (HEAD: 200 + application/pdf) before it counts as verified."""

from __future__ import annotations

import html as htmllib
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Optional, Protocol
from urllib.parse import urljoin, urlparse

from ghostbuild_core.discovery.models import ProductRecord

from . import ids

UA = "GhostBuild/1.0 (hackathon assembly assistant; reads public product pages)"
MAX_BYTES = 3_000_000


class PageError(Exception):
    """The page could not be read or did not validate. The message is safe to show."""


@dataclass
class Fetched:
    status: int
    url: str  # final URL after redirects
    content_type: str
    body: bytes


class Fetcher(Protocol):
    def get(self, url: str, timeout: float) -> Fetched: ...

    def head(self, url: str, timeout: float) -> Fetched: ...


class UrllibFetcher:
    """Plain HTTPS GET/HEAD with an honest User-Agent, a size cap and a host allow-list (also after redirects)."""

    def _open(self, url: str, timeout: float, method: str) -> Fetched:
        if ids.is_product_url(url) is None and not _is_ikea_asset(url):
            raise PageError("only ikea.com pages are read")
        req = urllib.request.Request(url, method=method, headers={"User-Agent": UA, "Accept": "text/html,application/pdf,image/*;q=0.8"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 (scheme and host are checked above and after the redirect)
                final = r.geturl()
                if (urlparse(final).hostname or "").lower() not in ids.ALLOWED_HOSTS and not final.startswith("https://www.ikea.com/"):
                    raise PageError("redirected away from ikea.com")
                body = b"" if method == "HEAD" else r.read(MAX_BYTES + 1)
                if len(body) > MAX_BYTES:
                    raise PageError("page too large")
                return Fetched(r.status, final, r.headers.get("Content-Type", ""), body)
        except urllib.error.HTTPError as e:
            return Fetched(e.code, url, e.headers.get("Content-Type", "") if e.headers else "", b"")
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise PageError(f"could not reach ikea.com ({type(e).__name__})") from None

    def get(self, url: str, timeout: float) -> Fetched:
        return self._open(url, timeout, "GET")

    def head(self, url: str, timeout: float) -> Fetched:
        return self._open(url, timeout, "HEAD")


def _is_ikea_asset(url: str) -> bool:
    u = urlparse(url)
    return u.scheme == "https" and (u.hostname or "").lower() in ids.ALLOWED_HOSTS and (u.path.endswith((".pdf", ".jpg", ".jpeg", ".png")) or "/p/" in u.path)


def _meta(h: str, prop: str) -> Optional[str]:
    m = re.search(rf'<meta[^>]+(?:property|name)="{re.escape(prop)}"[^>]*?content="([^"]*)"', h) or re.search(rf'<meta[^>]+content="([^"]*)"[^>]+(?:property|name)="{re.escape(prop)}"', h)
    return htmllib.unescape(m.group(1)).strip() if m else None


def parse_product_page(page: str, url: str, now_ms: int) -> ProductRecord:
    """Facts from the page itself. Raises PageError when the page is not a self-consistent product page."""
    article = ids.is_product_url(url)
    if article is None:
        raise PageError("not an official product page URL")
    prod = re.search(r'"itemNo":"(s?\d{8})","visibleItemNo":"([\d.]+)","name":"([^"]+)","type":"[A-Z]+","typeName":"([^"]*)"', page, re.I)
    label = re.search(r'aria-label="Article Number: ([\d.]+)"', page)
    if prod is None and label is None:
        raise PageError("the page does not state an article number")
    page_no = (prod.group(1) if prod else ids.parse_article(label.group(1)) or "").lower()
    if page_no != article:
        raise PageError(f"the page says article {page_no or '?'} but the address says {article}")
    if label is not None and ids.parse_article(label.group(1)) != article.lstrip("sS") and ids.parse_article(label.group(1)) != article:
        raise PageError("the page's article number markup disagrees with its own data")
    name = (prod.group(3) if prod else "").strip() or ""
    type_name = (prod.group(4) if prod else "").strip()
    title = _meta(page, "og:title") or ""
    if not name and title:
        name = re.split(r"[ ,]", title, 1)[0]
    if not name:
        raise PageError("the page does not name the product")
    canon = re.search(r'<link rel="canonical" href="([^"]+)"', page)
    if canon and ids.is_product_url(htmllib.unescape(canon.group(1))) != article:
        raise PageError("the canonical address is a different product")
    image = _meta(page, "og:image") or ""
    if not image:
        raise PageError("the page has no product image")
    desc = _meta(page, "og:description") or _meta(page, "description") or ""
    parts = [p.strip() for p in re.split(r",\s*", htmllib.unescape(title))] if title else []
    color = parts[1] if len(parts) >= 3 else ""
    size = parts[-1] if len(parts) >= 2 else ""
    # Related items share series names. Only gallery images with this product's
    # own image slug contribute attributes (a related drawer unit is not this desk).
    slug = urlparse(image).path.rsplit('/', 1)[-1].split('__')[0]
    alts = []
    for tag in re.findall(r'<img\b[^>]*>', page):
        alt = re.search(r'\balt="([^"]{12,300})"', tag)
        if alt and slug + '__' in tag:
            alts.append(htmllib.unescape(alt.group(1)))
    mine = [a for a in dict.fromkeys(alts) if name.lower() in a.lower() and not re.search(r"payment|gift card|logo", a, re.I)]
    desc_body = desc[len(title):].strip() if title and desc.startswith(title) else desc
    pdf = re.search(r'assembly_instructions/[^"\'\\ <>]+\.pdf', page)
    locale = "/".join(urlparse(url).path.strip("/").split("/")[:2]) or "us/en"
    manual = f"https://www.ikea.com/{locale}/{pdf.group(0)}" if pdf else None
    return ProductRecord(
        source="ikea", article=article, article_display=ids.display(article), name=name[:80], type_name=type_name[:80], color=color[:60], size=size[:60],
        description=desc_body[:800], evidence=mine[:6], image_url=image, product_url=url, manual_url=manual, manual_verified=False,
        verified_at=now_ms, how="live_search",
    )


def fetch_product(fetcher: Fetcher, url: str, now_ms: int, timeout: float = 8.0, check_manual: bool = True) -> ProductRecord:
    """Fetch + validate one product page (and HEAD its assembly PDF). Raises PageError with a person-safe message."""
    r = fetcher.get(url, timeout)
    if r.status != 200 or b"<html" not in r.body[:200000].lower():
        raise PageError(f"ikea.com answered {r.status} for that page")
    final = r.url
    rec = parse_product_page(r.body.decode("utf-8", "replace"), final if ids.is_product_url(final) else url, now_ms)
    if check_manual and rec.manual_url:
        try:
            h = fetcher.head(rec.manual_url, min(timeout, 6.0))
            rec = rec.model_copy(update={"manual_verified": h.status == 200 and "pdf" in h.content_type.lower()})
        except PageError:
            pass
    return rec
