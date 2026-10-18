"""Turn whatever a research agent returned into the GhostBuild import ENVELOPE (docs/sponsors/CREAO_AGENT_BRIEF.md).

Deterministic and offline: no model, no network. Nothing here is a claim about CREAO's real output shape (UNVERIFIED until a
key is supplied); `extract_payload` searches a tolerant set of locations and `to_envelope` accepts three payload shapes:
  (a) already our envelope or our Card          -> passed through (provenance sanitised, missing parts defaulted)
  (b) a generic playbook-ish JSON object        -> mapped into a Card (see _build_card)
  (d) anything else                             -> {"error": {"message", "found"}} (is_error() is True)
Rules this module will not bend:
  * a step is MANUAL unless the payload explicitly names an allowed telemetry signal (then a `verify` is built);
  * cues are upper-case, glyph-sanitised, <= 24 / 26 chars, shortened at word boundaries only, with the full text kept in `detail`
    and every shortening recorded in research.uncertainties;
  * no `guides`/GuideView is ever created (they need real image files); picture descriptions/links go to
    research.visual_references and the step `detail`;
  * a quote is kept only if it is verbatim in supplied source_texts; provenance is never AUTHORED/REVIEWED.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from typing import Any, Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from knowledge.importer import REVIEWED, is_http_url
from knowledge.validate import ALLOWED_VERIFY_SIGNALS, STEP_GLYPHS, STEP_DIAGNOSIS

AUTHORED = "AUTHORED DEMO METADATA"
MAX_DEPTH = 8
OUTPUT_KEYS = ("output", "outputs", "result", "results", "response", "final_output", "data", "message", "messages", "text", "content", "artifacts")
SKIP_KEYS = frozenset({"input", "inputs", "request", "params", "request_body"})
STEP_LIST_KEYS = ("steps", "instructions", "procedure", "stages", "directions")
STEP_ACTION_KEYS = ("action", "instruction", "text", "step", "title", "name")
STEP_TITLE_KEYS = ("title", "name")
STEP_DETAIL_KEYS = ("detail", "details", "description", "explanation", "notes")
STEP_WARN_KEYS = ("warnings", "warning", "tips", "tip", "safety", "cautions", "caution")
FAQ_KEYS = ("faq", "faqs", "questions")
TROUBLE_KEYS = ("troubleshooting", "troubleshoot", "problems")
SOURCE_KEYS = ("sources", "references", "citations")
UNCERTAIN_KEYS = ("uncertainties", "caveats", "limitations", "unknowns", "uncertainty")
VISUAL_KEYS = ("visuals", "images", "diagrams", "visual_references", "pictures")
FENCE = re.compile(r"```[ \t]*(?:json|JSON)?[ \t]*\r?\n(.*?)```", re.DOTALL)

MANUFACTURER_HOSTS = (
    "raspberrypi.com", "docs.arduino.cc", "learn.adafruit.com", "learn.sparkfun.com",
)
HARD_WORDS = re.compile(r"\b(BROKEN|DEAD|FAULTY|WRONG|BAD|DEFECTIVE|DAMAGED|VERIFIED|CORRECT)\b")
SOFT_WORDS = re.compile(r"\b(IS|ARE)\b")
LINE1, LINE2 = 24, 26


# ----------------------------------------------------------------------------- extract_payload
def _looks_like_steps(items: Any) -> bool:
    return isinstance(items, list) and len(items) > 0 and all(isinstance(x, (dict, str)) for x in items)


def _is_playbookish(d: dict) -> bool:
    if isinstance(d.get("card"), dict):
        return True
    for key in STEP_LIST_KEYS:
        if _looks_like_steps(d.get(key)):
            return True
    return False


def _json_in_text(text: str):
    """Yield JSON candidates, so a metadata block cannot hide a later actual playbook."""
    candidates: list[str] = [m.group(1) for m in FENCE.finditer(text)]
    stripped = text.strip()
    if stripped[:1] in "{[":
        candidates.append(stripped)
    for block in candidates:
        try:
            value = json.loads(block)
        except ValueError:
            continue
        if isinstance(value, (dict, list)) and value:
            yield value
    decoder = json.JSONDecoder()
    for m in re.finditer(r"\{", text):
        try:
            value, _ = decoder.raw_decode(text[m.start():])
        except ValueError:
            continue
        if isinstance(value, dict) and value:
            yield value


def _find(obj: Any, depth: int) -> Any:
    if depth > MAX_DEPTH or obj is None:
        return None
    if isinstance(obj, str):
        for inner in _json_in_text(obj):
            found = _find(inner, depth + 1)
            if found is not None:
                return found
        return None
    if isinstance(obj, dict):
        if _is_playbookish(obj):
            return obj
        for key in OUTPUT_KEYS:
            if key in obj:
                found = _find(obj[key], depth + 1)
                if found is not None:
                    return found
        for key, value in obj.items():
            if key in OUTPUT_KEYS or key in SKIP_KEYS:
                continue
            found = _find(value, depth + 1)
            if found is not None:
                return found
        return None
    if isinstance(obj, list):
        if obj and all(isinstance(x, dict) and any(k in x for k in ("action", "instruction", "step", "title", "text")) and not any(k in x for k in ("role", "type", "content", "mime", "mime_type")) for x in obj):
            return {"steps": obj}  # a bare list of step objects
        for item in reversed(obj):  # the last message/artifact is the answer
            found = _find(item, depth + 1)
            if found is not None:
                return found
    return None


def extract_payload(raw: Any) -> Any:
    """Dig the agent's playbook out of a raw run response; None if nothing recognisable is there."""
    return _find(raw, 0)


def top_level_summary(raw: Any) -> list[str]:
    if isinstance(raw, dict):
        return [f"{k}: {type(v).__name__}" for k, v in list(raw.items())[:30]]
    return [type(raw).__name__]


def is_error(envelope: Any) -> bool:
    return isinstance(envelope, dict) and isinstance(envelope.get("error"), dict) and "card" not in envelope


# ----------------------------------------------------------------------------- text helpers
def slugify(text: str, limit: int = 48) -> str:
    s = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    if len(s) > limit:
        s = s[:limit].rsplit("_", 1)[0] if "_" in s[:limit] else s[:limit]
    return s.strip("_")


_FOLD = {"’": "'", "‘": "'", "`": "'", "“": "", "”": "", '"': "", "–": "-", "—": "-", "−": "-", "…": "...", "✓": "OK", "✔": "OK",
         "°": " DEG", "×": "X", "&": " AND ", "%": " PERCENT", ";": ",", "[": "(", "]": ")", "{": "(", "}": ")", "_": " ",
         "*": " ", "#": " ", "|": " ", "\\": "/", "<": " ", ">": " ", "~": " ", "@": " AT ", "$": " USD ", "^": " "}


def sanitize_text(text: str) -> str:
    s = unicodedata.normalize("NFKD", str(text))
    out = []
    for ch in s:
        out.append(_FOLD.get(ch, ch))
    s = "".join(c for c in "".join(out) if ord(c) < 128 or c in "·●").upper()
    s = "".join(c if STEP_GLYPHS.match(c) else " " for c in s)
    return re.sub(r"\s+", " ", s).strip()


def _wrap(words: list[str], lead: str = "") -> Optional[tuple[str, str]]:
    """Greedy two-line wrap; `lead` (e.g. CHECK) is always the start of line 1. None if it does not fit."""
    line1: list[str] = [lead] if lead else []
    i = 0
    while i < len(words) and len(" ".join(line1 + [words[i]])) <= LINE1:
        line1.append(words[i])
        i += 1
    if not line1 or (lead and len(line1) == 1 and words):
        return None if words else (lead, "")
    rest = words[i:]
    if not rest:
        return " ".join(line1), ""
    line2 = " ".join(rest)
    if len(line2) <= LINE2:
        return " ".join(line1), line2
    return None


_CLAUSE_SPLIT = re.compile(
    r",|:|\.\s+| - | THEN | AND THEN | SO THAT | UNTIL | WHICH | BEFORE | AFTER | WHILE | BECAUSE | WITH | USING | WHEN | IF | AS | SO | FOR | BY "
)
_CLAUSE_SPLIT_KEEP = re.compile("(" + _CLAUSE_SPLIT.pattern + ")")
_PARENS = re.compile(r"\([^)]*\)")
_DANGLING = frozenset("A AN THE WITH OF TO AND OR IN ON FOR AT BY FROM UNTIL IF AS SO THAT THIS THESE THOSE YOUR ITS INTO ONTO OVER UNDER ANY SOME EACH EVERY ALL THEIR ABOUT BOTH THAN WHERE WHILE BECAUSE THEN BEFORE AFTER NOT MAY CAN WILL SHOULD MUST COULD WOULD".split())


def _tidy(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip(" ,:-")


def _legal(text: str) -> Optional[str]:
    """Remove IS/ARE (meaning preserved: VALVE IS OPEN -> VALVE OPEN); refuse text with other diagnosis/forbidden words."""
    t = _tidy(SOFT_WORDS.sub(" ", text))
    if HARD_WORDS.search(t) or STEP_DIAGNOSIS.search(t):
        return None
    return t


def _drop_dangling(words: list[str]) -> list[str]:
    while len(words) > 1 and words[-1] in _DANGLING:
        words = words[:-1]
    return words


def make_cue(text: str, prefix: str = "") -> tuple[dict[str, str], bool, str]:
    """(cue dict, shortened, how) for glasses text. `prefix` (e.g. "CHECK", "UNCERTAIN:") always starts line 1.
    `shortened` is True when words were dropped or a generic fallback was used; callers record that. Words are never cut mid-word."""
    lead = sanitize_text(prefix)
    raw = sanitize_text(text)
    if lead and raw.startswith(lead):
        raw = raw[len(lead):].strip()
    full = _legal(raw)
    shortened = False
    how = ""
    if full is None:
        parts = [p for p in (_tidy(x) for x in _CLAUSE_SPLIT.split(raw)) if p]
        keep = []
        for p in parts:
            c = _legal(p)
            if c is None:
                break
            keep.append(c)
        full = keep[0] if keep else ""
        shortened, how = True, "contained a word the glasses may not show (diagnosis wording); only the clause before it is shown"
    if full:
        words = full.split(" ")
        fit = _wrap(words, lead)
        if fit:
            return {"line1": fit[0], "line2": fit[1]}, shortened, how
        no_par = _tidy(_PARENS.sub(" ", full))
        # (1) the longest run of whole clauses (connectors kept inside the run) that fits two lines
        pieces = _CLAUSE_SPLIT_KEEP.split(no_par)
        clause_best: Optional[tuple[str, str]] = None
        clause_len = 0
        for k in range(0, len(pieces), 2):
            prefix = _tidy("".join(pieces[: k + 1]))
            got = _wrap(prefix.split(" "), lead)
            if got is None:
                break
            clause_best, clause_len = got, len(prefix)
        # (2) leading words, never ending on a dangling article/preposition
        words = no_par.split(" ")
        while len(words) > 2 and _wrap(words, lead) is None:
            words.pop()
        words = _drop_dangling(words)
        word_best = _wrap(words, lead)
        word_len = len(" ".join(words))
        best = clause_best if clause_best and clause_len >= 0.7 * word_len else word_best or clause_best
        if best is not None and len(" ".join(best).split()) >= (2 if not lead else 3):
            return {"line1": best[0], "line2": best[1]}, True, "was shortened to its leading words to fit two glasses lines"
    if lead:
        return {"line1": lead[:LINE1], "line2": "SEE PHONE"}, True, "could not be shown on the glasses; the cue points to the phone"
    return {"line1": "DO THIS STEP", "line2": "DETAILS ON PHONE"}, True, "could not be shown as a glasses cue; a generic cue points to the phone"


# ----------------------------------------------------------------------------- sources
def _host(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def classify_source(url: Optional[str]) -> tuple[str, str]:
    """(EvidenceLabel, research kind word) from the URL host. Only http(s) URLs get a typed kind."""
    if not url or not is_http_url(url):
        return "WEB TUTORIAL", "tutorial"
    host = _host(url)
    path = urlparse(url).path.lower()
    if host in ("youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "music.youtube.com") or host.endswith(".youtube.com"):
        return "VIDEO TUTORIAL", "video"
    if host == "github.com" or host.endswith(".github.com") or host in ("raw.githubusercontent.com", "gist.github.com"):
        return "GITHUB SOURCE", "github"
    for known in MANUFACTURER_HOSTS:
        if host == known or host.endswith("." + known):
            return "MANUFACTURER DOC", "docs"
    if host in ("adafruit.com", "www.adafruit.com") and path.startswith("/learn"):
        return "MANUFACTURER DOC", "docs"
    if host in ("sparkfun.com", "www.sparkfun.com") and path.startswith(("/tutorials", "/learn")):
        return "MANUFACTURER DOC", "docs"
    return "WEB TUTORIAL", "tutorial"


def parse_timestamp(value: Any) -> Optional[int]:
    """Seconds from 754, '754s', 't=754s', '12:34', '1:02:03', '00:12:34', '12m34s', '1h2m3s'; None if not a timestamp."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value) if value >= 0 else None
    s = str(value).strip().lower().removeprefix("t=").strip()
    if not s:
        return None
    if re.fullmatch(r"\d+s?", s):
        return int(s.rstrip("s"))
    m = re.fullmatch(r"(?:(\d+):)?(\d{1,2}):(\d{2})(?:\.\d+)?", s)
    if m:
        return int(m.group(1) or 0) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
    m = re.fullmatch(r"(?:(\d+)h)?\s*(?:(\d+)m)?\s*(?:(\d+)s)?", s)
    if m and any(m.groups()):
        return int(m.group(1) or 0) * 3600 + int(m.group(2) or 0) * 60 + int(m.group(3) or 0)
    return None


def hms(seconds: int) -> str:
    return f"{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"


def deep_link(url: Optional[str], seconds: Optional[int], kind: str) -> Optional[str]:
    if not url or not is_http_url(url):
        return None
    if kind != "video" or seconds is None:
        return url
    parts = urlparse(url)
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != "t"]
    query.append(("t", f"{seconds}s"))
    return urlunparse(parts._replace(query=urlencode(query)))


# ----------------------------------------------------------------------------- generic helpers
def _first_str(d: dict, keys: tuple[str, ...]) -> str:
    for k in keys:
        v = d.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def _as_list(value: Any) -> list:
    if value is None or value == "":
        return []
    return value if isinstance(value, list) else [value]


def _text_of(item: Any) -> str:
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict):
        return _first_str(item, ("text", "note", "description", "uncertainty", "caveat", "limitation", "message", "detail", "summary", "claim"))
    return ""


def _tokens(text: str) -> set[str]:
    stop = {"the", "a", "an", "of", "to", "and", "or", "in", "on", "for", "with", "it", "is", "are", "be", "that", "this", "your", "you", "step"}
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 2 and w not in stop}


def _short_title(title: str, limit: int = 28) -> str:
    t = re.sub(r"\s+", " ", title).strip().rstrip(".")
    if len(t) <= limit:
        return t
    words, out = t.split(" "), ""
    for w in words:
        nxt = f"{out} {w}".strip()
        if len(nxt) > limit:
            break
        out = nxt
    return out or t[:limit]


def _unique(base: str, taken: set[str], fallback: str) -> str:
    base = base or fallback
    cand, n = base, 2
    while cand in taken:
        cand = f"{base}_{n}"
        n += 1
    taken.add(cand)
    return cand


def _norm_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


class _Ctx:
    """Mutable collection bag for one conversion."""

    def __init__(self) -> None:
        self.shortened: list[str] = []  # glasses texts that did not fit and were shortened (aggregated into one note)
        self.notes: list[str] = []  # normalizer notes (go to research.uncertainties, prefixed)
        self.agent_uncertainties: list[str] = []
        self.video_notes: list[dict] = []
        self.visual_refs: list[dict] = []
        self.research_sources: list[dict] = []
        self.sources: list[dict] = []
        self.source_texts: dict[str, str] = {}
        self.by_key: dict[str, str] = {}  # url / agent ref / title -> our source id

    def short(self, what: str) -> None:
        if what not in self.shortened:
            self.shortened.append(what)

    def note(self, text: str) -> None:
        line = f"GhostBuild normalizer: {text}"
        if line not in self.notes:
            self.notes.append(line)


# ----------------------------------------------------------------------------- source registration
def _register_source(ctx: _Ctx, entry: Any) -> Optional[str]:
    """Add one source entry (URL string or object) and return our source id; also fills research.sources/video_notes."""
    if isinstance(entry, str):
        entry = {"url": entry} if re.match(r"https?://", entry.strip(), re.I) else {"title": entry}
    if not isinstance(entry, dict):
        return None
    url = _first_str(entry, ("url", "link", "href", "uri"))
    title = _first_str(entry, ("title", "name", "label")) or ""
    agent_ref = str(entry.get("id") or entry.get("source_id") or "").strip()
    if url and not is_http_url(url):
        ctx.note(f"source {url!r} dropped from the card: only http(s) URLs are kept")
        url = ""
        if not title:
            return None
    if not url and not title:
        return None
    key = url or f"title:{title.lower()}"
    sid = ctx.by_key.get(key)
    label, word = classify_source(url or None)
    if sid is None:
        n = len(ctx.sources) + 1
        sid = f"{word}_{n}"
        host = _host(url) if url else ""
        ctx.sources.append({"id": sid, "kind": label, "title": (title or host or "source")[:200], "url": url or None, "file": None})
        ctx.by_key[key] = sid
        ctx.by_key[f"ref:{sid}"] = sid
        used = _first_str(entry, ("used_for", "purpose", "note", "notes", "summary", "why"))
        ctx.research_sources.append({"id": sid, "kind": word, "url": url or None, "used_for": used or "listed by the research agent"})
        if not url:
            ctx.note(f"source {title!r} has no URL; kept as a title-only reference")
    if agent_ref:
        ctx.by_key[f"ref:{agent_ref}"] = sid
    text = entry.get("source_text") or entry.get("text_read") or entry.get("excerpt")
    if isinstance(text, str) and text.strip():
        ctx.source_texts[sid] = text
    # timestamps
    stamps = _as_list(entry.get("timestamps")) + _as_list(entry.get("timestamp")) + _as_list(entry.get("t")) + _as_list(entry.get("time"))
    for stamp in stamps:
        note = ""
        if isinstance(stamp, dict):
            note = _first_str(stamp, ("note", "summary", "label", "description", "text"))
            seconds = parse_timestamp(stamp.get("t") if "t" in stamp else stamp.get("timestamp", stamp.get("time", stamp.get("start"))))
            end = parse_timestamp(stamp.get("end", stamp.get("t_end")))
        else:
            seconds, end = parse_timestamp(stamp), None
        if seconds is None:
            continue
        ctx.video_notes.append({"url": deep_link(url, seconds, word) or url, "t_start": hms(seconds), "t_end": hms(end) if end is not None else "", "summary": note or title or "referenced moment", "source": sid})
    return sid


def _cite(ctx: _Ctx, ref: Any, default_loc: str = "") -> Optional[dict]:
    """A Cite dict from a per-step source reference (url string, agent id, or object with url/timestamp/section/quote)."""
    entry = ref
    if isinstance(ref, str):
        sid = ctx.by_key.get(ref) or ctx.by_key.get(f"ref:{ref}")
        entry = {"url": ref} if (sid is None and re.match(r"https?://", ref.strip(), re.I)) else {"id": ref}
    if not isinstance(entry, dict):
        return None
    sid = None
    for k in (_first_str(entry, ("url", "link", "href")), f"ref:{entry.get('id') or entry.get('source') or entry.get('source_id') or ''}"):
        if k and k in ctx.by_key:
            sid = ctx.by_key[k]
            break
    if sid is None:
        if not _first_str(entry, ("url", "link", "href", "title", "name")):
            return None
        sid = _register_source(ctx, entry)
    if sid is None:
        return None
    src = next(s for s in ctx.sources if s["id"] == sid)
    word = classify_source(src["url"])[1]
    seconds = None
    for k in ("timestamp", "t", "time", "start", "t_start"):
        if k in entry:
            seconds = parse_timestamp(entry[k])
            if seconds is not None:
                break
    loc = f"t={hms(seconds)}" if seconds is not None else (_first_str(entry, ("loc", "section", "location", "page")) or default_loc or "whole source")
    quote = entry.get("quote")
    out = {"source": sid, "loc": loc, "quote": None, "url": deep_link(src["url"], seconds, word)}
    if isinstance(quote, str) and quote.strip():
        text = ctx.source_texts.get(sid)
        if text is not None and _norm_ws(quote) in _norm_ws(text):
            out["quote"] = quote
        else:
            ctx.note(f"a quote from source {sid} was dropped: it is not verbatim in any supplied source text")
    return out


# ----------------------------------------------------------------------------- verify (explicit only)
def _build_verify(ctx: _Ctx, step_title: str, raw: Any) -> Optional[dict]:
    if not isinstance(raw, dict):
        return None
    whens = raw.get("when") if isinstance(raw.get("when"), list) else [raw]
    preds = []
    for w in whens:
        if not isinstance(w, dict) or not isinstance(w.get("signal"), str):
            continue
        if w["signal"] not in ALLOWED_VERIFY_SIGNALS:
            ctx.note(f"verify on step {step_title!r} ignored: signal {w['signal']!r} is not an allowed telemetry signal")
            continue
        op = w.get("op", "eq")
        if op not in ("lt", "gt", "eq", "is_null", "not_null"):
            continue
        preds.append({"signal": w["signal"], "op": op, "value": w.get("value")})
    if not preds or len(preds) != len([w for w in whens if isinstance(w, dict) and isinstance(w.get("signal"), str)]):
        return None
    ok_text = _first_str(raw, ("ok", "ok_text", "message")) if isinstance(raw.get("ok"), str) or "ok_text" in raw else ""
    ok_cue = make_cue("● " + (ok_text or "CHECK PASSED").lstrip("● "))[0]
    if any(p["signal"].startswith("led.") for p in preds):
        ok_cue = {k: re.sub(r"\b(VERIFIED|CONFIRMED|CORRECT)\b", "COMMANDED", v) for k, v in ok_cue.items()}
    return {"when": preds, "hold_ms": int(raw.get("hold_ms", 1500)) if str(raw.get("hold_ms", "")).isdigit() else 1500, "ok": ok_cue}


# ----------------------------------------------------------------------------- card building
def _clean_faq_q(q: str) -> str:
    return re.sub(r"\s+", " ", q).strip().lower().rstrip("?").strip() or "what is this step"


def _step_ref(step_ref: Any, steps: list[dict]) -> Optional[int]:
    """Index of a referenced step: 1-based number, step id, or a step title."""
    if isinstance(step_ref, bool) or step_ref is None:
        return None
    if isinstance(step_ref, int) or (isinstance(step_ref, str) and step_ref.strip().isdigit()):
        n = int(step_ref) - 1
        return n if 0 <= n < len(steps) else None
    if isinstance(step_ref, str):
        low = step_ref.strip().lower()
        for i, s in enumerate(steps):
            if low in (s["id"], s["title"].lower()):
                return i
    return None


def _attribute_text(text: str, steps: list[dict]) -> Optional[int]:
    m = re.search(r"\bstep\s+(\d{1,2})\b", text, re.I)
    if m and 0 < int(m.group(1)) <= len(steps):
        return int(m.group(1)) - 1
    low = text.lower()
    for i, s in enumerate(steps):
        if len(s["title"]) >= 5 and s["title"].lower() in low:
            return i
    return None


def _best_step(text: str, steps: list[dict]) -> int:
    toks = _tokens(text)
    best, score = 0, 0
    for i, s in enumerate(steps):
        sc = len(toks & _tokens(s["title"] + " " + s["_action"] + " " + s["detail"]))
        if sc > score:
            best, score = i, sc
    return best


def _build_card(payload: dict, request: str, ctx: _Ctx, device: str, model: str, intent: str) -> dict:
    title = _first_str(payload, ("title", "name", "task", "goal")) or request.strip()
    items = next((payload[k] for k in STEP_LIST_KEYS if _looks_like_steps(payload.get(k))), [])

    # sources first so steps can cite them
    for entry in [e for k in SOURCE_KEYS for e in _as_list(payload.get(k))]:
        _register_source(ctx, entry)
    raw_texts = payload.get("source_texts")
    if isinstance(raw_texts, dict):
        for ref, text in raw_texts.items():
            sid = ctx.by_key.get(f"ref:{ref}") or ctx.by_key.get(str(ref))
            if sid and isinstance(text, str):
                ctx.source_texts[sid] = text

    taken_ids: set[str] = set()
    steps: list[dict] = []
    for i, item in enumerate(items):
        d = item if isinstance(item, dict) else {"action": item}
        action = _first_str(d, ("action", "instruction", "text", "step")) or _first_str(d, STEP_TITLE_KEYS)
        if not action:
            ctx.note(f"step {i + 1} had no readable text and was skipped")
            continue
        title_s = _first_str(d, STEP_TITLE_KEYS)
        step_title = _short_title(title_s or action)
        sid = _unique(slugify(title_s or action, 32), taken_ids, f"step_{i + 1}")
        cue, shortened, how = make_cue(action)
        detail_parts = []
        if shortened:
            ctx.short(f"step {i + 1} cue ({step_title})")
        if shortened or len(action) > 60 or title_s:
            if action.rstrip(".") != step_title.rstrip("."):
                detail_parts.append(action if action.endswith((".", "!", "?")) else action + ".")
        extra = _first_str(d, STEP_DETAIL_KEYS)
        if extra:
            detail_parts.append(extra)
        step: dict[str, Any] = {
            "id": sid, "title": step_title, "cue": cue, "detail": "", "why": None, "where": None, "warnings": [],
            "faq": [], "troubleshoot": [], "guide_id": None, "verify": None, "requires": [], "_action": action,
        }
        # warnings / tips / safety
        for k in STEP_WARN_KEYS:
            for w in _as_list(d.get(k)):
                t = _text_of(w)
                if t and t not in step["warnings"]:
                    step["warnings"].append(t)
        # why / where
        why_text = _first_str(d, ("why", "reason", "rationale"))
        if why_text:
            detail_parts.append("Why: " + why_text)
            step["_why"] = why_text
        where_text = _first_str(d, ("where", "location"))
        if where_text:
            wc, w_short, _ = make_cue(where_text)
            step["where"] = wc
            if w_short or len(where_text) > 40:
                detail_parts.append("Where: " + where_text)
        # faq
        for f in _as_list(d.get("faq")) + _as_list(d.get("questions")):
            _add_faq(step, f, ctx)
        # troubleshoot
        for t in _as_list(d.get("troubleshooting")) + _as_list(d.get("troubleshoot")) + _as_list(d.get("problems")):
            _add_trouble(step, t, ctx)
        # per-step uncertainty
        for k in ("uncertainties", "uncertainty", "caveats", "caveat", "limitations"):
            for u in _as_list(d.get(k)):
                t = _text_of(u)
                if t:
                    ctx.agent_uncertainties.append(t)
                    step.setdefault("_uncertain", []).append(t)
        # explicit telemetry only
        verify_raw = d.get("verify") or d.get("telemetry")
        if verify_raw is not None:
            step["verify"] = _build_verify(ctx, step_title, verify_raw)
        # per-step visuals
        for k in ("visuals", "visual", "images", "image", "diagrams", "diagram", "pictures"):
            for v in _as_list(d.get(k)):
                _add_visual(ctx, v, step, len(steps))
        # per-step source references (a step-level timestamp applies to its source reference)
        refs = [r for k in ("sources", "source", "video", "references", "reference", "citations", "cite") for r in _as_list(d.get(k))]
        refs = [({"url": r} if re.match(r"https?://", r.strip(), re.I) else {"id": r}) if isinstance(r, str) else r for r in refs]
        step_stamp = next((d[k] for k in ("timestamp", "t", "time") if k in d), None)
        if step_stamp is not None:
            if not refs and len(ctx.sources) == 1:
                refs = [{"id": ctx.sources[0]["id"]}]
            if refs and isinstance(refs[0], dict) and not any(k in refs[0] for k in ("timestamp", "t", "time")):
                refs[0] = {**refs[0], "timestamp": step_stamp}
        step["_cites"] = [c for c in (_cite(ctx, r) for r in refs) if c]
        step["detail"] = (" ".join(detail_parts) + " " + step["detail"]).strip()
        steps.append(step)

    if not steps:
        return {}

    # top-level per-card material, attached to the best matching step
    top_warnings = [t for k in STEP_WARN_KEYS for t in (_text_of(w) for w in _as_list(payload.get(k))) if t]
    for w in top_warnings:
        if w not in steps[0]["warnings"]:
            steps[0]["warnings"].append(w)
    for f in [f for k in FAQ_KEYS for f in _as_list(payload.get(k))]:
        q = _first_str(f, ("q", "question")) if isinstance(f, dict) else ""
        _add_faq(steps[_best_step(q, steps)], f, ctx)
    for t in [t for k in TROUBLE_KEYS for t in _as_list(payload.get(k))]:
        text = _text_of(t) if not isinstance(t, dict) else (_first_str(t, ("problem", "issue", "symptom")) + " " + _first_str(t, ("fix", "solution", "action", "check")))
        _add_trouble(steps[_best_step(text, steps)], t, ctx)
    for u in [u for k in UNCERTAIN_KEYS for u in _as_list(payload.get(k))]:
        text = _text_of(u)
        if not text:
            continue
        ctx.agent_uncertainties.append(text)
        idx = None
        if isinstance(u, dict):
            idx = _step_ref(u.get("step"), steps)
        if idx is None:
            idx = _attribute_text(text, steps)
        if idx is not None:
            steps[idx].setdefault("_uncertain", []).append(text)
    for v in [v for k in VISUAL_KEYS for v in _as_list(payload.get(k))]:
        _add_visual(ctx, v, None, -1, steps)
    for src in [e for k in SOURCE_KEYS for e in _as_list(payload.get(k))]:
        if isinstance(src, dict):  # top-level source entries naming the steps they back
            refs = _as_list(src.get("steps") or src.get("step") or src.get("used_in_steps"))
            for r in refs:
                idx = _step_ref(r, steps)
                cite = _cite(ctx, src) if idx is not None else None
                if cite:
                    steps[idx]["_cites"].append(cite)

    # finalise each step: UNCERTAIN why line, source-reference checks, detail cap, strip private keys
    for step in steps:
        unc = step.pop("_uncertain", [])
        why_text = step.pop("_why", "")
        if unc:
            cue, short, _ = make_cue(unc[0], "UNCERTAIN:")
            step["why"] = cue
            step["detail"] = (step["detail"] + " " + " ".join("UNCERTAIN: " + u for u in unc)).strip()
            if short:
                ctx.short(f"{step['title']}: UNCERTAIN line")
        elif why_text:
            cue, short, how = make_cue(why_text)
            step["why"] = cue
            if short:
                ctx.short(f"{step['title']}: why line")
        cites = step.pop("_cites")
        seen = set()
        for c in cites:
            key = (c["source"], c["loc"])
            if key in seen:
                continue
            seen.add(key)
            src = next(s for s in ctx.sources if s["id"] == c["source"])
            is_video = src["kind"] == "VIDEO TUTORIAL"
            first = f"CHECK SOURCE VIDEO" if is_video else "CHECK SOURCE"
            second = ("AT " + c["loc"].removeprefix("t=")) if c["loc"].startswith("t=") else "SEE PHONE"
            step["troubleshoot"].append({
                "when": [], "action": {"line1": first, "line2": second},
                "why": f"Source for this step: {src['title']} ({c['loc']}).", "cites": [c], "guide_id": None,
            })
        step.pop("_action", None)
        if len(step["detail"]) > 600:
            cut = step["detail"][:597].rsplit(" ", 1)[0]
            step["detail"] = cut + "..."
            ctx.note(f"the phone detail of step {step['title']!r} was cut to 600 characters")

    # provenance: never AUTHORED or REVIEWED; the draft is labelled by what it was sourced from (approve sets REVIEWED)
    provenance = _draft_provenance(ctx)
    if not ctx.sources:
        ctx.note("the research agent returned no sources")
    intent_l = (intent or str(payload.get("intent") or payload.get("goal_mode") or payload.get("mode") or "")).strip().lower()
    goal_mode = "fix" if intent_l in ("fix", "repair", "troubleshoot") else "build"
    card_id = _card_id(title, request)
    return {
        "v": 2, "card_id": card_id, "title": title[:120], "provenance": provenance,
        "sources": ctx.sources, "tests": [], "steps": steps, "functional": None, "guides": [],
        "goal_mode": goal_mode, "aliases": _aliases(title, request, device, model),
    }


def _draft_provenance(ctx: _Ctx) -> str:
    order = ["MANUFACTURER DOC", "GITHUB SOURCE", "VIDEO TUTORIAL", "WEB TUTORIAL"]
    kinds = {s["kind"] for s in ctx.sources}
    for k in order:
        if k in kinds:
            return k
    return "WEB TUTORIAL"


def _card_id(title: str, request: str) -> str:
    base = slugify(title or request, 40) or "task"
    suffix = hashlib.sha1(f"{request}\x00{title}".encode()).hexdigest()[:4]
    return f"{base}_{suffix}"


def _aliases(title: str, request: str, device: str, model: str) -> list[str]:
    out: list[str] = []

    def add(text: str) -> None:
        a = re.sub(r"[^a-z0-9 ]+", " ", (text or "").lower())
        a = re.sub(r"\s+", " ", a).strip()
        if a and a not in out and (len(a.split()) >= 2 or a == re.sub(r"[^a-z0-9 ]+", " ", title.lower()).strip()):
            out.append(a[:60])

    add(title)
    add(request[:60])
    lead = re.sub(r"^(how to |to )?(replace|change|fix|repair|reset|build|make|install|set up|setup|assemble|fold)\s+(a |an |the |my )?", "", title.lower()).strip()
    add(lead)
    add(" ".join(x for x in (device, model) if x))
    add(model)
    return out


def _add_faq(step: dict, f: Any, ctx: _Ctx) -> None:
    if not isinstance(f, dict):
        return
    q = _first_str(f, ("q", "question"))
    a = _first_str(f, ("a", "answer"))
    if not q or not a:
        return
    cue, short, _ = make_cue(a)
    if short:
        ctx.short(f"{step['title']}: answer to {q!r}")
    step["faq"].append({"q": _clean_faq_q(q), "a": cue})
    if short:
        step["detail"] = (step["detail"] + f" FAQ: {q.strip()} {a.strip()}").strip()


def _add_trouble(step: dict, t: Any, ctx: _Ctx) -> None:
    problem = fix = ""
    if isinstance(t, str):
        fix = t.strip()
    elif isinstance(t, dict):
        problem = _first_str(t, ("problem", "issue", "symptom", "if"))
        fix = _first_str(t, ("check", "fix", "solution", "action", "then", "text"))
    if not fix and not problem:
        return
    action_text = re.sub(r"^(check|make sure|ensure)\b[: ]*", "", (fix or problem), flags=re.I)
    cue, short, _ = make_cue(action_text, "CHECK")
    if short:
        ctx.short(f"{step['title']}: CHECK item")
    why = " ".join(x for x in (problem and f"If {problem.rstrip('.')}:", fix) if x)
    step["troubleshoot"].append({"when": [], "action": cue, "why": why, "cites": [], "guide_id": None})


def _add_visual(ctx: _Ctx, v: Any, step: Optional[dict], index: int, steps: Optional[list[dict]] = None) -> None:
    url = desc = view = step_ref = ""
    if isinstance(v, str):
        if re.match(r"https?://", v.strip(), re.I):
            url = v.strip()
        else:
            desc = v.strip()
    elif isinstance(v, dict):
        url = _first_str(v, ("url", "link", "src", "href"))
        desc = _first_str(v, ("description", "caption", "alt", "depicts", "text", "title"))
        view = _first_str(v, ("view",)).lower()
        step_ref = v.get("step")
    else:
        return
    if url and not is_http_url(url):
        ctx.note(f"visual reference {url!r} dropped: only http(s) URLs are kept")
        url = ""
    if not url and not desc:
        return
    target = step
    if target is None and steps:
        idx = _step_ref(step_ref, steps)
        target = steps[idx] if idx is not None else None
    ctx.visual_refs.append({"view": view if view in ("where", "how", "correct") else "how", "url": url or None, "description": desc or "", "step": target["id"] if target else None})
    if target is not None:
        piece = f"Reference only, no picture on the glasses: {desc or 'see link'}{' ' + url if url else ''}."
        target["detail"] = (target["detail"] + " " + piece).strip()


# ----------------------------------------------------------------------------- envelope
def _sanitize_provenance(card: dict, ctx: _Ctx) -> None:
    prov = card.get("provenance")
    if prov in (AUTHORED, REVIEWED) or not isinstance(prov, str):
        ctx.note(f"card provenance {prov!r} from the agent was replaced: only a human review (knowledge.approve) may set it")
        card["provenance"] = _draft_provenance(ctx) if ctx.sources else next((s["kind"] for s in card.get("sources", []) if isinstance(s, dict) and isinstance(s.get("kind"), str)), "WEB TUTORIAL")


def _apply_intent(card: dict, intent: str) -> None:
    """An explicit request intent decides goal_mode (fix|repair|troubleshoot -> fix, anything else -> build)."""
    if intent and intent.strip():
        card["goal_mode"] = "fix" if intent.strip().lower() in ("fix", "repair", "troubleshoot") else "build"


def to_envelope(payload: Any, request: str, *, run_id: Optional[str] = None, device: str = "", model: str = "", intent: str = "") -> dict:
    """Payload -> import envelope, or {"error": {...}} when the payload is unusable."""
    request = (request or "").strip() or "research request"
    rid = run_id or "run-" + hashlib.sha1(request.encode()).hexdigest()[:10]
    ctx = _Ctx()
    if isinstance(payload, dict) and isinstance(payload.get("card"), dict):  # (a) our envelope
        envelope = json.loads(json.dumps(payload))
        card = envelope["card"]
        for s in card.get("sources", []) if isinstance(card.get("sources"), list) else []:
            if isinstance(s, dict) and isinstance(s.get("kind"), str):
                ctx.sources.append(s)
        _sanitize_provenance(card, ctx)
        _apply_intent(card, intent)
        research = envelope.get("research") if isinstance(envelope.get("research"), dict) else {}
        for name in ("sources", "video_notes", "visual_references", "uncertainties"):
            if not isinstance(research.get(name), list):
                research[name] = []
        if not isinstance(card.get("guides"), list) or card.get("guides"):
            pass  # guides given by the agent are validated (and rejected) by the importer; nothing is invented here
        research["uncertainties"].extend(n for n in ctx.notes if n not in research["uncertainties"])
        envelope["research"] = research
        envelope.setdefault("source_texts", {})
        if not isinstance(envelope["source_texts"], dict):
            envelope["source_texts"] = {}
        # Transport metadata wins over a model-authored run id.
        envelope["run_id"] = run_id or (envelope.get("run_id") if isinstance(envelope.get("run_id"), str) and envelope.get("run_id") else rid)
        envelope["request"] = envelope.get("request") if isinstance(envelope.get("request"), str) and envelope.get("request").strip() else request
        return envelope
    if isinstance(payload, dict) and isinstance(payload.get("steps"), list) and payload.get("card_id") and payload.get("v") == 2:  # (a) our Card
        card = json.loads(json.dumps(payload))
        for s in card.get("sources", []):
            if isinstance(s, dict) and isinstance(s.get("kind"), str):
                ctx.sources.append(s)
        _sanitize_provenance(card, ctx)
        _apply_intent(card, intent)
        return {"run_id": rid, "request": request, "card": card, "source_texts": {},
                "research": {"sources": [], "video_notes": [], "visual_references": [], "uncertainties": ctx.notes}}
    if isinstance(payload, list) and _looks_like_steps(payload):
        payload = {"steps": payload}
    if not isinstance(payload, dict) or not any(_looks_like_steps(payload.get(k)) for k in STEP_LIST_KEYS):
        found = sorted(payload.keys()) if isinstance(payload, dict) else [type(payload).__name__]
        return {"error": {"message": "the payload has no recognisable card, envelope, or steps list", "found": found[:40]}}
    card = _build_card(payload, request, ctx, device, model, intent)
    if not card:
        return {"error": {"message": "no step had readable text", "found": sorted(payload.keys())[:40]}}
    if ctx.visual_refs:
        ctx.note("visual references are descriptions or links only; no pictures were produced and none are shown on the glasses")
    if ctx.shortened:
        ctx.note("glasses text shortened at word boundaries to fit two lines (the full text is in the phone detail): " + "; ".join(ctx.shortened))
    uncertainties = list(dict.fromkeys(ctx.agent_uncertainties)) + ctx.notes
    return {
        "run_id": rid,
        "request": request,
        "card": card,
        "source_texts": dict(ctx.source_texts),
        "research": {
            "sources": ctx.research_sources,
            "video_notes": ctx.video_notes,
            "visual_references": ctx.visual_refs,
            "uncertainties": uncertainties,
        },
    }


def normalize(raw: Any, request: str, *, run_id: Optional[str] = None, device: str = "", model: str = "", intent: str = "") -> dict:
    """extract_payload + to_envelope. On failure returns {"error": {"message", "found"}}."""
    payload = extract_payload(raw)
    if payload is None:
        return {"error": {"message": "no playbook found anywhere in the run response", "found": top_level_summary(raw)}}
    return to_envelope(payload, request, run_id=run_id, device=device, model=model, intent=intent)
