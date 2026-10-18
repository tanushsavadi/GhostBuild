"""Article numbers, product URLs and 'is this about IKEA' detection. Pure functions."""

from __future__ import annotations

import re
import unicodedata
from typing import Optional
from urllib.parse import urlparse

ALLOWED_HOSTS = ("www.ikea.com", "ikea.com")
_DOTTED = re.compile(r"(?<![\d.])(\d{3})[.\s-](\d{3})[.\s-](\d{2})(?![\d])")
_EIGHT = re.compile(r"(?<![\d.])s?(\d{8})(?![\d])", re.I)
_URL = re.compile(r"https?://(?:www\.)?ikea\.com/[^\s\"'<>)]*", re.I)
_PIP = re.compile(r"^/([a-z]{2})/([a-z]{2})/p/([a-z0-9\-%]*?)-?(s?\d{8})/?$", re.I)

# Well-known IKEA product-line names (a recogniser, not a catalogue: nothing here is shown to anyone as a product).
KNOWN_NAMES = frozenset("""
MICKE ALEX LAGKAPTEN LINNMON ADILS TROTTEN BEKANT IDASEN IDANAS MITTZON KALLAX BILLY HEMNES MALM BESTA EKET PAX LACK POANG BRIMNES
SONGESAND NORDLI TROFAST KURA SUNDVIK STUVA FRIHETEN KIVIK EKTORP SODERHAMN STRANDMON SLAKT FJALLBO HAVSTA IVAR SKUBB GALANT BEKVAM
TONSTAD VITTSJO GORM RAST BROR ENHET PLATSA KOMPLEMENT HEMNES STUVA FLISAT SMASTAD KNOXHULT METOD FINNALA LANDSKRONA SKOGSTA NORDKISA
""".split())
_ASSEMBLY = re.compile(r"\b(assembl\w*|build\w*|put(?:ting)? (?:it |this |that )?together|set(?:ting)? (?:it |this )?up|install\w*|construct\w*|instructions?|manual|"
                       r"help (?:me )?with|working on|putting|bought|got|have|having|just (?:got|bought)|unbox\w*|flat.?pack\w*)\b")
_THING = re.compile(r"\b(desk|table|bookcase|bookshelf|shelf|shelves|cabinet|wardrobe|closet|dresser|drawers?|bed|crib|sofa|couch|chair|stool|bench|"
                    r"nightstand|bedside|tv (?:unit|bench|stand)|shoe (?:cabinet|rack)|storage|unit|furniture|frame|rack|workstation)\b")


def fold(text: str) -> str:
    """Lowercase, accents removed (BESTÅ -> besta): spoken and typed names rarely carry the diacritics."""
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)).lower()


def parse_article(text: str) -> Optional[str]:
    """802.130.74 / 802 130 74 / 80213074 / S59422220 -> the 8 digits ('s' prefix kept for S-articles). None if no article number."""
    m = _DOTTED.search(text)
    if m:
        return "".join(m.groups())
    m = _EIGHT.search(text)
    if m:
        return ("s" if m.group(0).lower().startswith("s") else "") + m.group(1)
    return None


def display(article: str) -> str:
    d = article.lstrip("sS")
    return f"{d[:3]}.{d[3:6]}.{d[6:]}" if len(d) == 8 else article


def parse_url(text: str) -> Optional[tuple[str, Optional[str]]]:
    """The first ikea.com URL in the text as (clean https url, article from a /p/ product path or None). Other hosts are never accepted."""
    m = _URL.search(text)
    if not m:
        return None
    raw = m.group(0).rstrip(".,;:!?")
    u = urlparse(raw)
    if u.scheme != "https" and u.scheme != "http":
        return None
    if (u.hostname or "").lower() not in ALLOWED_HOSTS:
        return None
    url = f"https://{u.hostname.lower()}{u.path}"
    pip = _PIP.match(u.path)
    return url, (pip.group(4).lower() if pip else None)


def is_product_url(url: str) -> Optional[str]:
    """The article if `url` is a clean official product page (https, ikea.com, /xx/yy/p/<slug>-<article>/); else None. Category and series pages are not products."""
    try:
        u = urlparse(url)
    except ValueError:
        return None
    if u.scheme != "https" or (u.hostname or "").lower() not in ALLOWED_HOSTS:
        return None
    m = _PIP.match(u.path)
    return m.group(4).lower() if m else None


def canonical_url(article: str, locale: str = "us/en") -> str:
    """ikea.com resolves /p/-<article>/ to the product's own page (a public redirect, not an API)."""
    return f"https://www.ikea.com/{locale}/p/-{article.lower()}/"


def mentions_ikea(text: str) -> bool:
    return bool(re.search(r"\bikea\b|ikea\.com", fold(text)))


def known_name_in(text: str) -> Optional[str]:
    t = fold(text)
    for n in sorted(KNOWN_NAMES, key=len, reverse=True):
        if re.search(rf"\b{n.lower()}\b", t):
            return n
    return None


def wants_help_with_ikea_product(text: str, cached_names: tuple[str, ...] = ()) -> bool:
    """Should GhostBuild start IKEA product identification for this request? Needs IKEA AND an assembly/ownership intent about a thing,
    an IKEA URL, an article number said together with IKEA, or a known IKEA product-line name with a thing or an assembly intent.
    'I love IKEA meatballs' and 'IKEA closes at nine' do not qualify."""
    t = fold(text)
    if parse_url(text):
        return True
    art = parse_article(text)
    ikea = mentions_ikea(text)
    if art and (ikea or re.search(r"\b(article|product|item)\s*(?:number|no|#)", t)):
        return True
    names = {n.lower() for n in (*KNOWN_NAMES, *cached_names)}
    name = next((n for n in sorted(names, key=len, reverse=True) if re.search(rf"\b{re.escape(fold(n))}\b", t)), None)
    thing = bool(_THING.search(t))
    assembly = bool(_ASSEMBLY.search(t))
    if ikea and (thing or (assembly and re.search(r"\b(help|how|can you|need)\b", t))):
        return thing or assembly
    if name and (thing or assembly):
        # a bare product-line name must be said like a request/ownership about it, and (for 4+ letter ALL-CAPS-ish names) is allowed without 'ikea'
        return True
    return False
