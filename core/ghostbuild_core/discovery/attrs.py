"""Deterministic language handling for product discovery: what the person described, how candidates rank against it, how a spoken or
typed reply picks one, and which single question would separate the current candidates. No model, no network, no randomness.

Honesty rules: a candidate is only 'matched' on an attribute its OFFICIAL text states; an attribute the text never mentions is
'unverified' (not 'absent'); only a stated different value is a conflict. Scores order candidates; they are never shown as a confidence."""

from __future__ import annotations

import re
import unicodedata
from typing import Optional

from .models import Attrs, Candidate, ProductRecord, Question

# ----------------------------------------------------------------------------------------------- vocabulary (extend freely; generic furniture/goods)
CATEGORIES: dict[str, tuple[str, ...]] = {
    "desk": ("desk", "desks", "workstation", "computer table", "writing table"),
    "table": ("table", "tables", "dining table", "coffee table", "side table"),
    "bookcase": ("bookcase", "bookshelf", "book shelf", "shelving unit", "shelf unit"),
    "cabinet": ("cabinet", "cabinets", "sideboard", "storage cabinet"),
    "wardrobe": ("wardrobe", "closet", "armoire"),
    "chest of drawers": ("chest of drawers", "dresser", "drawer chest"),
    "drawer unit": ("drawer unit", "drawers unit"),
    "bed": ("bed", "bed frame", "bunk bed"),
    "sofa": ("sofa", "couch", "loveseat", "sectional"),
    "chair": ("chair", "armchair", "stool", "desk chair"),
    "tv unit": ("tv unit", "tv bench", "tv stand", "media unit", "tv cabinet"),
    "nightstand": ("nightstand", "bedside table", "night stand"),
    "shelf": ("shelf", "shelves", "wall shelf"),
    "bench": ("bench", "shoe bench"),
    "crib": ("crib", "cot"),
}
COMPAT = {
    "desk": ("desk", "table"),
    "table": ("table", "desk"),
}  # the shop files some desks as tables (and some tables are used as desks)
COLORS = (
    "white",
    "black",
    "brown",
    "grey",
    "gray",
    "beige",
    "oak",
    "birch",
    "walnut",
    "natural",
    "blue",
    "green",
    "red",
    "yellow",
    "pink",
    "anthracite",
    "black-brown",
    "dark grey",
    "light grey",
    "silver",
    "bamboo",
    "pine",
    "ash",
    "turquoise",
    "orange",
)
# feature -> words that state it. Counted features take a number ("two drawers").
FEATURES: dict[str, tuple[str, ...]] = {
    "drawer": ("drawer", "drawers"),
    "cabinet": ("cabinet", "cupboard", "door", "doors"),
    "shelf": ("shelf", "shelves", "shelving"),
    "cable": ("cable", "cables", "cord"),
    "wheels": ("wheels", "castors", "casters", "wheeled", "rolling"),
    "corner": ("corner", "l-shaped", "l shaped"),
    "adjustable": (
        "adjustable",
        "height-adjustable",
        "sit/stand",
        "sit stand",
        "standing",
    ),
    "glass": ("glass",),
    "mirror": ("mirror",),
    "metal": ("metal", "steel", "aluminium", "aluminum"),
    "wood": ("wood", "wooden", "solid pine", "solid oak"),
}
COUNTED = {"drawer", "shelf"}
NUMBER_WORDS = {
    "no": 0,
    "zero": 0,
    "a": 1,
    "an": 1,
    "one": 1,
    "single": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}
_NUM = (
    r"(?:\d{1,2}|"
    + "|".join(sorted((k for k in NUMBER_WORDS if k != "no"), key=len, reverse=True))
    + ")"
)
ORDINALS = {
    "first": 1,
    "1st": 1,
    "second": 2,
    "2nd": 2,
    "third": 3,
    "3rd": 3,
    "fourth": 4,
    "4th": 4,
    "fifth": 5,
    "5th": 5,
    "top": 1,
    "last": -1,
    "bottom": -1,
}
_STOP = set(
    "the a an i it its is my have has with that this of for on in and or to me please help need want am im i'm i've ive building build assemble assembling put together "
    "get got just some one mine its it's thing product furniture item here there and also really very kind sort like looks look".split()
)


def norm(text: str) -> str:
    t = (
        unicodedata.normalize("NFKD", text)
        .encode("ascii", "ignore")
        .decode()
        .lower()
        .replace("’", "'")
    )
    t = re.sub(r"[^a-z0-9'/\- ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _num(tok: str) -> Optional[int]:
    return int(tok) if tok.isdigit() else NUMBER_WORDS.get(tok)


# ----------------------------------------------------------------------------------------------- what the person described
def extract(text: str, known_names: tuple[str, ...] = ()) -> Attrs:
    t = norm(text)
    words = t.split()
    category = None
    best: tuple[int, int] = (
        10**6,
        0,
    )  # (position of the mention, -length): the first-named thing is the product ("desk with a cabinet" is a desk)
    for cat, syns in CATEGORIES.items():
        for s in syns:
            m = re.search(rf"\b{re.escape(s)}\b", t)
            if m and (m.start(), -len(s)) < best:
                category, best = cat, (m.start(), -len(s))
    color = next(
        (
            c
            for c in sorted(COLORS, key=len, reverse=True)
            if re.search(rf"\b{re.escape(c)}\b", t)
        ),
        None,
    )
    if color == "gray":
        color = "grey"
    features: dict[str, int | bool] = {}
    for feat, syns in FEATURES.items():
        for s in syns:
            m = re.search(
                rf"\b(?:({_NUM}|no|without|with no)\s+(?:small\s+|big\s+|large\s+)?)?{re.escape(s)}\b",
                t,
            )
            if not m:
                continue
            q = m.group(1)
            if q in ("no", "without", "with no"):
                features[feat] = False
            elif q in ("a", "an"):
                features.setdefault(
                    feat, True
                )  # "a drawer" says it has one, not that it has exactly one
            elif q is not None and feat in COUNTED and _num(q) is not None:
                features[feat] = _num(q)  # type: ignore[assignment]
            else:
                features.setdefault(feat, True)
            break
    # "drawers on both sides" / "cabinet on one side": keep as plain presence (the question asks for sides when needed)
    name_hint = None
    for n in known_names:
        if re.search(rf"\b{re.escape(norm(n))}\b", t):
            name_hint = n
            break
    keep = [w for w in words if w not in _STOP and len(w) > 2 and not w.isdigit()]
    return Attrs(
        category=category,
        color=color,
        features=features,
        name_hint=name_hint,
        words=keep[:12],
    )


def search_query(attrs: Attrs, fallback_text: str = "") -> str:
    """Keywords for an official-site search: what the person actually said, no invented attributes."""
    parts: list[str] = []
    if attrs.name_hint:
        parts.append(attrs.name_hint)
    if attrs.color:
        parts.append(attrs.color)
    if attrs.category:
        parts.append(attrs.category)
    for f, v in attrs.features.items():
        if v is False:
            continue
        parts.append(
            f"{v} {f}s"
            if isinstance(v, int) and not isinstance(v, bool) and v > 1
            else f
        )
    # Preserve useful stated qualifiers such as material and size in live retrieval.
    used = set(" ".join(parts).lower().split())
    parts.extend(w for w in attrs.words if w not in used and w not in _STOP)
    q = " ".join(dict.fromkeys(parts))
    return q or " ".join(norm(fallback_text).split()[:8])


# ----------------------------------------------------------------------------------------------- rank / dedupe
def _text(rec: ProductRecord) -> str:
    return norm(
        " ".join(
            [
                rec.name,
                rec.type_name,
                rec.color,
                rec.description,
                *rec.evidence,
                *rec.manual_evidence,
            ]
        )
    )


def stated_count(text: str, feat: str) -> Optional[int]:
    """The count the official text states for a feature ('two drawers' -> 2), the highest stated; None if no count is given."""
    found: list[int] = []
    for s in FEATURES.get(feat, (feat,)):
        for m in re.finditer(
            rf"\b({_NUM})(?:\s+|-)(?:small\s+|big\s+|large\s+|deep\s+)?{re.escape(s)}\b",
            text,
        ):
            n = _num(m.group(1))
            if n is not None and m.group(1) not in ("a", "an"):
                found.append(n)
    return max(found) if found else None


def mentions(text: str, feat: str) -> bool:
    return any(
        re.search(rf"\b{re.escape(s)}\b", text) for s in FEATURES.get(feat, (feat,))
    )


def score(rec: ProductRecord, attrs: Attrs, order: int) -> Candidate:
    text = _text(rec)
    matched: list[str] = []
    unverified: list[str] = []
    conflicts: list[str] = []
    s = 0.0
    if attrs.name_hint:
        if attrs.name_hint.lower() == rec.name.lower():
            s += 6
            matched.append(rec.name)
        else:
            s -= 2
    if attrs.category:
        syns = tuple(
            x
            for cat in COMPAT.get(attrs.category, (attrs.category,))
            for x in CATEGORIES.get(cat, (cat,))
        )
        tn = norm(rec.type_name)
        if any(re.search(rf"\b{re.escape(x)}\b", tn) for x in syns):
            s += 4
            matched.append(attrs.category)
        elif tn:
            # the shop files it as a different kind of thing (a drawer unit is not a desk, even if its photo caption says 'desk drawers')
            s -= 6
            conflicts.append(f"{attrs.category} (filed as {rec.type_name})")
        elif any(re.search(rf"\b{re.escape(x)}\b", text) for x in syns):
            s += 1
            unverified.append(attrs.category + " (only mentioned)")
        else:
            s -= 4
            conflicts.append(attrs.category)
    if attrs.color:
        c = attrs.color
        if re.search(rf"\b{re.escape(c)}\b", norm(rec.color) or text):
            s += 2
            matched.append(c)
        elif rec.color:
            s -= 2
            conflicts.append(f"{c} (this one is {rec.color})")
        else:
            unverified.append(c)
    for feat, want in attrs.features.items():
        have = mentions(text, feat)
        n = stated_count(text, feat) if feat in COUNTED else None
        if want is False:
            if have and feat != "cable":
                s -= 2
                conflicts.append(f"no {feat}")
            continue
        if isinstance(want, int) and not isinstance(want, bool) and feat in COUNTED:
            if n is not None and n == want:
                s += 3
                matched.append(f"{want} {feat}{'s' if want != 1 else ''}")
            elif n is not None:
                s -= 3
                conflicts.append(f"{want} {feat}s (page says {n})")
            elif have:
                s += 1
                unverified.append(f"{want} {feat}s")
            else:
                unverified.append(f"{want} {feat}s")
        elif have:
            s += 2
            matched.append(feat)
        else:
            unverified.append(feat)
    s += (
        1.0 / (1 + order)
    )  # the search's own order breaks ties (the provider's order, never a confidence estimate)
    origin = ""
    return Candidate(
        record=rec,
        rank=1,
        score=round(s, 3),
        matched=list(dict.fromkeys(matched)),
        unverified=list(dict.fromkeys(unverified)),
        conflicts=conflicts,
        origin=origin,
    )


def rank(
    records: list[ProductRecord], attrs: Attrs, limit: int = 5, min_score: float = 0.5
) -> list[Candidate]:
    """Up to `limit` DISTINCT products, best first. Dedupe is by article number (two colours or sizes are different products and stay
    separate); a record with a contradicted category never makes the list."""
    seen: set[str] = set()
    scored: list[Candidate] = []
    for i, r in enumerate(records):
        key = f"{r.source}:{r.article}"
        if key in seen:
            continue
        seen.add(key)
        scored.append(score(r, attrs, i))
    if attrs.category:
        scored = [c for c in scored if attrs.category not in " ".join(c.conflicts)]
    scored = (
        [c for c in scored if c.score >= min_score] if not attrs.is_empty() else scored
    )
    scored.sort(key=lambda c: (-c.score, c.record.name, c.record.article))
    out = scored[:limit]
    return [c.model_copy(update={"rank": i + 1}) for i, c in enumerate(out)]


# ----------------------------------------------------------------------------------------------- picking one
def pick_ordinal(text: str, n: int) -> Optional[int]:
    """'the first one', 'number three', '#2', 'option 4', 'the last one' -> zero-based index, or None."""
    t = norm(text)
    for w, v in ORDINALS.items():
        if re.search(rf"\b{re.escape(w)}\b", t):
            idx = v - 1 if v > 0 else n - 1
            return idx if 0 <= idx < n else None
    m = (
        re.search(rf"\b(?:number|no|option|choice|pick|item|#)\s*({_NUM})\b", t)
        or re.search(rf"^\s*({_NUM})\s*$", t)
        or re.search(rf"#\s*({_NUM})", text.lower())
    )
    if m:
        v = _num(m.group(1))
        if v and 1 <= v <= n:
            return v - 1
    return None


def pick_name(text: str, names: list[str]) -> list[int]:
    """Indexes of candidates whose product NAME the person said ('that is the named product'). Several = the name is not enough on its own."""
    t = norm(text)
    return [
        i
        for i, n in enumerate(names)
        if n and re.search(rf"\b{re.escape(norm(n))}\b", t)
    ]


_NONE = re.compile(
    r"\b(none of (?:those|these|them)|not (?:any|one) of (?:those|these|them)|neither|none|no(?:pe)?,? (?:none|not (?:one|any)|those|these)|"
    r"(?:that'?s|it'?s|they'?re) not (?:it|there|in there|any of)|not (?:in|on) (?:there|the list)|wrong (?:ones?|products?)|nothing (?:here|matches))\b"
)
_MORE = re.compile(
    r"\b(show (?:me )?more|more (?:options|results|choices)|any more|anything else|other (?:ones|options|results)|next (?:page|ones|results)|see more|more please|more)\b"
)
_NUMBER_INTENT = re.compile(
    r"\b(?:i )?(?:found|have|got|see|know|can read|located) (?:the |a |an |my )?(?:product |article |item )?(?:number|code|link|url)\b|\bi have the (?:link|number)\b|\bproduct number\b|\barticle number\b"
)
_CONFIRM_YES = re.compile(
    r"^(?:yes|yeah|yep|yup|correct|right|that'?s it|that is it|that'?s the one|exactly|sure|ok|okay|confirm|go ahead|do it|looks right|that one)\b"
)
_CONFIRM_NO = re.compile(
    r"^(?:no|nope|nah|wrong|not (?:it|that|this)|that'?s not (?:it|right|the one)|incorrect)\b"
)


def is_none(text: str) -> bool:
    return bool(_NONE.search(norm(text)))


def is_more(text: str) -> bool:
    t = norm(text)
    return bool(_MORE.search(t)) and not is_none(t)


def says_has_number(text: str) -> bool:
    return bool(_NUMBER_INTENT.search(norm(text)))


def is_yes(text: str) -> bool:
    return bool(_CONFIRM_YES.search(norm(text)))


def is_no(text: str) -> bool:
    return bool(_CONFIRM_NO.search(norm(text)))


# ----------------------------------------------------------------------------------------------- one useful question
def distinguishing_question(cands: list[Candidate], asked: Attrs) -> Optional[Question]:
    """The attribute whose REAL values split the current candidates best and which the person has not already told us. Built only from
    what the candidates' official text states; returns None when the candidates do not differ on anything we can read."""
    if len(cands) < 2:
        return None
    texts = [_text(c.record) for c in cands]
    best: Optional[tuple[float, Question]] = None
    for feat in (
        "drawer",
        "cabinet",
        "shelf",
        "wheels",
        "corner",
        "adjustable",
        "glass",
        "mirror",
    ):
        if feat in asked.features:
            continue
        if feat in COUNTED:
            counts = [stated_count(t, feat) for t in texts]
            known = [c for c in counts if c is not None]
            vals = sorted(set(known))
            if len(vals) >= 2 and len(known) >= 2:
                spread = len(vals) / len(known)
                opts = [
                    (f"{v} {feat}{'s' if v != 1 else ''}" if v else f"No {feat}s")
                    for v in vals[:3]
                ]
                q = Question(
                    id=f"count_{feat}",
                    prompt=f"How many {feat}s does yours have?",
                    options=[*opts, "Not sure"],
                    feature=feat,
                    values=[*vals[:3], None],
                )
                if best is None or spread > best[0]:
                    best = (spread, q)
                continue
        has = [mentions(t, feat) for t in texts]
        yes = sum(has)
        explicit_no = any(
            re.search(
                r"\b(?:no|without) (?:"
                + "|".join(re.escape(s) for s in FEATURES.get(feat, (feat,)))
                + r")\b",
                t,
            )
            for t in texts
        )
        if 0 < yes < len(cands) and explicit_no:
            balance = 1 - abs(yes / len(cands) - 0.5) * 2
            label = {
                "cabinet": "a cabinet or door",
                "wheels": "wheels",
                "corner": "a corner or L-shape",
                "adjustable": "an adjustable height",
                "shelf": "shelves",
            }.get(feat, f"a {feat}")
            q = Question(
                id=f"has_{feat}",
                prompt=f"Does yours have {label}?",
                options=["Yes", "No", "Not sure"],
                feature=feat,
                values=[True, False, None],
            )
            if best is None or balance > best[0]:
                best = (balance, q)
    return best[1] if best else None


def answer_to_attrs(q: Question, text: str) -> Optional[Attrs]:
    """Map a reply to the question to attributes. None = not sure / no usable answer."""
    t = norm(text)
    if q.feature is None:
        return None
    if re.search(r"\b(not sure|don'?t know|no idea|unsure|can'?t tell)\b", t):
        return None
    n = pick_ordinal(text, len(q.options) - 1)
    if n is not None and q.values and q.values[n] is not None:
        v = q.values[n]
        return Attrs(features={q.feature: v})  # type: ignore[dict-item]
    if q.id.startswith("count_"):
        m = re.search(rf"\b({_NUM})\b", t)
        if m and _num(m.group(1)) is not None:
            return Attrs(features={q.feature: _num(m.group(1))})  # type: ignore[dict-item]
    if is_yes(text) or re.search(r"\b(yes|has|have|does)\b", t):
        return Attrs(features={q.feature: True})
    if is_no(text) or re.search(r"\b(no|without|doesn'?t|does not)\b", t):
        return Attrs(features={q.feature: False})
    return None
