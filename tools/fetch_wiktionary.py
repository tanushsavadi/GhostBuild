# /// script
# requires-python = ">=3.10"
# ///
"""Fetch the English "Production" descriptions of ASL signs from Wiktionary.

Wiktionary text is CC BY-SA 4.0: reuse is allowed with credit and a link, and
anything derived from it must carry the same licence. Every entry keeps its
page URL so the phone page can credit it.

Writes g2/src/wiktionary.json: {GLOSS: {"t": text, "u": page url}}.
Polite to the API: page sources come in batches of 50, and the description
templates are expanded in batches of 40 (about a dozen requests in all), with
backoff on HTTP 429. Responses are cached in tmp/wiktionary/ (git-ignored).

Run (from the repo root):  uv run tools/fetch_wiktionary.py
"""

from __future__ import annotations

import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://en.wiktionary.org/w/api.php"
HEADERS = {"User-Agent": "sign-coach-hackathon/0.1 (ASL learning demo)"}
ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "tmp" / "wiktionary"
OUT = ROOT / "g2" / "src" / "wiktionary.json"
SEP = "\n@@@@\n"


def api(params: dict) -> dict:
    body = urllib.parse.urlencode({**params, "format": "json", "formatversion": "2"}).encode()
    for attempt in range(6):
        try:
            req = urllib.request.Request(API, data=body, headers=HEADERS)  # POST: batches are long
            with urllib.request.urlopen(req, timeout=60) as res:
                time.sleep(2)
                return json.load(res)
        except urllib.error.HTTPError as err:
            if err.code != 429:
                raise
            wait = int(err.headers.get("Retry-After") or 30 * (attempt + 1))
            print(f"rate limited; waiting {wait} s")
            time.sleep(wait)
    raise SystemExit("Wiktionary kept rate-limiting; try again later")


def cached(name: str, fetch):
    path = CACHE / name
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    data = fetch()
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data


def sources() -> dict[str, str]:
    def fetch() -> dict[str, str]:
        titles, cont = [], {}
        while True:
            r = api({"action": "query", "list": "categorymembers", "cmtype": "page", "cmlimit": "500",
                     "cmtitle": "Category:American Sign Language lemmas", **cont})
            titles += [m["title"] for m in r["query"]["categorymembers"]]
            if "continue" not in r:
                break
            cont = r["continue"]
        pages = {}
        for i in range(0, len(titles), 50):
            r = api({"action": "query", "prop": "revisions", "rvprop": "content", "rvslots": "main",
                     "titles": "|".join(titles[i:i + 50])})
            for p in r["query"]["pages"]:
                pages[p["title"]] = p["revisions"][0]["slots"]["main"]["content"]
        return pages
    return cached("sources.json", fetch)


def production_wikitext(src: str) -> str:
    m = re.search(r"===\s*Production\s*===(.*?)(?:\n===|\Z)", src, re.S)
    if not m:
        return ""
    # Only the written steps (bullet lines), not the image table or the sign chart.
    lines = [l for l in m.group(1).splitlines() if l.startswith("*") and "sign-chart" not in l and "rfi" not in l]
    return "\n".join(lines)


def expand(texts: list[str]) -> list[str]:
    out = []
    for i in range(0, len(texts), 40):
        batch = texts[i:i + 40]
        r = cached(f"expanded_{i:03d}.json", lambda: api({"action": "expandtemplates", "prop": "wikitext",
                                                          "text": SEP.join(batch)}))
        parts = r["expandtemplates"]["wikitext"].split(SEP.strip())
        if len(parts) != len(batch):
            raise SystemExit(f"batch {i}: expected {len(batch)} parts, got {len(parts)}")
        out += parts
    return out


def plain(wikitext: str) -> str:
    t = re.sub(r"\[\[(?:File|Image):[^\]]*\]\]", " ", wikitext, flags=re.I)  # inline pictures
    t = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", t)                 # [[link|text]] -> text
    t = re.sub(r"\{\{[^{}]*\}\}", " ", t)                           # leftover templates
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"'{2,}", "", t)
    t = re.sub(r"^[*#:]+\s*", "", t, flags=re.M)
    t = html.unescape(t)
    t = t.translate(str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"'}))
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"\s*Stokoe:.*$", "", t)  # notation the lens font cannot show
    t = re.sub(r"\s+([.,;:])", r"\1", t).strip()
    # "This one-handed ASL sign is produced with a smile:" -> "One-handed, with a smile:"
    m = re.match(r"This (one|two)-handed ASL sign is produced (.*?):\s*", t)
    if m:
        extra = "" if m.group(2) == "as follows" else f", {m.group(2)}"
        t = f"{m.group(1).capitalize()}-handed{extra}: {t[m.end():]}"
    return t


def main() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    pages = sources()
    items = [(title, production_wikitext(src)) for title, src in pages.items()]
    items = [(title, wt) for title, wt in items if wt]
    texts = expand([wt for _, wt in items])

    out: dict[str, dict] = {}
    for (title, _), expanded in zip(items, texts):
        text = plain(expanded)
        if len(text) < 20 or "]]" in text:  # empty, or a cross-reference that did not render
            continue
        url = "https://en.wiktionary.org/wiki/" + urllib.parse.quote(title.replace(" ", "_"))
        for gloss in re.findall(r"gloss=([A-Z0-9][A-Z0-9\-' ]*)", pages[title]):
            out.setdefault(gloss.strip(), {"t": text, "u": url})
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"wrote {len(out)} glosses from {len(items)} entries to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
