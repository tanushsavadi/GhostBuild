# /// script
# requires-python = ">=3.10"
# ///
"""Compare local Ollama models at turning English into ASL gloss order.

Every model gets the same prompt (rules + 4 worked examples), the same 18 test
sentences, temperature 0 and a JSON schema. Each answer is scored 0-1:
  0.4  signs: share of the required signs present (any listed alternative counts)
  0.2  face:  the facial cue matches (brows down / brows up / head shake / none)
  0.2  order: question word last, time word first, when the sentence has one
  0.2  clean: no English filler glosses (IS, THE, DO, TO, I ...)
Also reported: share of output signs our vocabulary can show ("usable"), and
median latency with the model already loaded.

The reference answers are AI-drafted ASL orders (UNCHECKED), good enough to
rank models, not to grade ASL.

Run (from the repo root, Ollama running):
  uv run tools/bench_llm.py qwen2.5:7b-instruct-q4_K_M qwen3:8b ...
Writes tmp/bench_llm.md.
"""

from __future__ import annotations

import json
import statistics
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OLLAMA = "http://localhost:11434/api/chat"

SYSTEM = """Turn an English sentence into ASL gloss for a beginner signer.
- ASL order: time words first, then topic, then comment. Question words (WHO WHAT WHERE WHEN WHY HOW) go LAST.
- Keep every person: I/me -> ME, my -> MY, you -> YOU, your -> YOUR.
- Drop: is are am was the a an do does did to be of.
- Base forms only: GO not GOING, EAT not ATE.
- Negation: put NOT after the verb, or use DONT-KNOW / DONT-LIKE / NOT-UNDERSTAND when they fit.
- A name or place with no common sign: spell=true.
- face: "brows down" for WHO/WHAT/WHERE/WHEN/WHY/HOW questions, "brows up" for yes/no questions, "head shake" when the sentence is negative, else "".
Each gloss is one word or a hyphenated sign, capital letters only."""

EXAMPLES = [
    ("What is your name?", ["YOUR", "NAME", "WHAT"], [], "brows down"),
    ("Are you deaf?", ["YOU", "DEAF"], [], "brows up"),
    ("I don't understand", ["ME", "NOT-UNDERSTAND"], [], "head shake"),
    ("I went to Boston yesterday", ["YESTERDAY", "ME", "GO", "BOSTON"], ["BOSTON"], ""),
]

SCHEMA = {
    "type": "object",
    "properties": {
        "signs": {"type": "array", "items": {"type": "object", "properties": {
            "gloss": {"type": "string"}, "spell": {"type": "boolean"}}, "required": ["gloss", "spell"]}},
        "face": {"type": "string", "enum": ["brows down", "brows up", "head shake", ""]},
    },
    "required": ["signs", "face"],
}

WH = {"WHO", "WHAT", "WHERE", "WHEN", "WHY", "HOW", "WHICH"}
TIME = {"TODAY", "TOMORROW", "YESTERDAY", "NOW", "LATER", "MORNING", "TONIGHT"}
FILLER = {"IS", "ARE", "AM", "WAS", "THE", "A", "AN", "DO", "DOES", "DID", "TO", "BE", "OF", "I", "IN"}

# (sentence, required signs (alternatives with |), expected face, extra order rule)
TESTS = [
    ("What time does the store close?", ["TIME", "STORE|SHOP", "CLOSE"], "brows down", "wh_last"),
    ("I'm going to the store tomorrow", ["TOMORROW", "ME", "GO", "STORE|SHOP"], "", "time_first"),
    ("Did you eat breakfast?", ["YOU", "EAT", "BREAKFAST"], "brows up", None),
    ("My sister is a doctor in Chicago", ["MY", "SISTER", "DOCTOR", "CHICAGO"], "", None),
    ("I don't like coffee", ["ME", "COFFEE", "DONT-LIKE|NOT-LIKE|NOT"], "head shake", None),
    ("Where do you work?", ["YOU", "WORK", "WHERE"], "brows down", "wh_last"),
    ("Can you help me find the bathroom?", ["HELP", "BATHROOM", "FIND|LOOK-FOR|SEARCH"], "brows up", None),
    ("Nice to meet you, I'm learning sign language", ["NICE", "MEET", "YOU", "LEARN", "SIGN|SIGN-LANGUAGE"], "", None),
    ("Who is your teacher?", ["YOUR", "TEACHER", "WHO"], "brows down", "wh_last"),
    ("I am not hungry", ["ME", "HUNGRY", "NOT"], "head shake", None),
    ("Yesterday I went to the hospital", ["YESTERDAY", "ME", "GO", "HOSPITAL"], "", "time_first"),
    ("Why are you sad?", ["YOU", "SAD", "WHY"], "brows down", "wh_last"),
    ("Do you want coffee or water?", ["YOU", "WANT", "COFFEE", "WATER"], "brows up", None),
    ("My name is Abdul", ["MY", "NAME", "ABDUL"], "", None),
    ("Please wait here", ["PLEASE", "WAIT", "HERE"], "", None),
    ("When is your birthday?", ["YOUR", "BIRTHDAY", "WHEN"], "brows down", "wh_last"),
    ("I love my family", ["ME", "LOVE", "MY", "FAMILY"], "", None),
    ("Tomorrow we will go to school", ["TOMORROW", "WE", "GO", "SCHOOL"], "", "time_first"),
]


def vocabulary() -> set[str]:
    vocab = set()
    for word, row in json.loads((ROOT / "g2/src/asllex.json").read_text(encoding="utf-8")).items():
        vocab.add(row[0])
        vocab.add(word.upper().replace(" ", "-"))
    for sign in json.loads((ROOT / "g2/src/deck.json").read_text(encoding="utf-8"))["signs"]:
        vocab.add(sign["gloss"])
    return vocab


def messages(sentence: str) -> list[dict]:
    msgs = [{"role": "system", "content": SYSTEM}]
    for english, glosses, spelled, face in EXAMPLES:
        answer = {"signs": [{"gloss": g, "spell": g in spelled} for g in glosses], "face": face}
        msgs += [{"role": "user", "content": english}, {"role": "assistant", "content": json.dumps(answer)}]
    return msgs + [{"role": "user", "content": sentence}]


def ask(model: str, sentence: str) -> tuple[dict | None, float]:
    body = {"model": model, "stream": False, "format": SCHEMA, "keep_alive": "10m", "think": False,
            "options": {"temperature": 0}, "messages": messages(sentence)}
    t0 = time.time()
    for attempt in range(2):
        req = urllib.request.Request(OLLAMA, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=300) as res:
                content = json.load(res)["message"]["content"]
            break
        except urllib.error.HTTPError as err:
            if attempt == 0 and "think" in err.read().decode(errors="replace").lower():
                body.pop("think")  # model without a thinking switch
                continue
            raise
    elapsed = time.time() - t0
    try:
        return json.loads(content), elapsed
    except json.JSONDecodeError:
        return None, elapsed


def score(out: dict | None, required: list[str], face: str, rule: str | None) -> dict:
    if not out:
        return {"total": 0.0, "signs": 0, "face": 0, "order": 0, "clean": 0}
    glosses = [str(s.get("gloss", "")).upper().strip() for s in out.get("signs", [])]
    have = set(glosses)
    signs = sum(any(alt in have for alt in need.split("|")) for need in required) / len(required)
    face_ok = float(out.get("face", "") == face)
    order = 1.0
    if rule == "wh_last":
        order = float(bool(glosses) and (glosses[-1] in WH or glosses[-1] == "TIME"))
    elif rule == "time_first":
        order = float(bool(glosses) and glosses[0] in TIME)
    clean = float(not (have & FILLER))
    return {"total": 0.4 * signs + 0.2 * face_ok + 0.2 * order + 0.2 * clean,
            "signs": signs, "face": face_ok, "order": order, "clean": clean}


def main() -> None:
    models = sys.argv[1:] or ["qwen2.5:7b-instruct-q4_K_M"]
    vocab = vocabulary()
    lines = ["# Local model comparison: English to ASL gloss", ""]
    summary = []
    for model in models:
        print(f"== {model}: loading")
        ask(model, "Hello")  # load into memory; not timed
        rows, times, totals, usable, total_signs = [], [], [], 0, 0
        for sentence, required, face, rule in TESTS:
            out, secs = ask(model, sentence)
            s = score(out, required, face, rule)
            times.append(secs)
            totals.append(s["total"])
            signs = out.get("signs", []) if out else []
            for sign in signs:
                total_signs += 1
                usable += bool(sign.get("spell")) or str(sign.get("gloss", "")).upper() in vocab
            gloss = " ".join(("#" if x.get("spell") else "") + str(x.get("gloss", "")) for x in signs)
            rows.append(f"| {sentence} | {gloss} | {out.get('face', '') if out else 'INVALID'} | {s['total']:.2f} |")
            print(f"  {s['total']:.2f}  {secs:4.1f}s  {sentence} -> {gloss} [{out.get('face') if out else '-'}]")
        summary.append((model, rows, times, usable / max(total_signs, 1), statistics.mean(totals)))
        # Free GPU memory for the next model.
        urllib.request.urlopen(urllib.request.Request(OLLAMA, data=json.dumps(
            {"model": model, "messages": [], "keep_alive": 0}).encode(), headers={"Content-Type": "application/json"}))

    lines += ["| Model | Score (0-1) | Usable signs | Median latency |", "|---|---|---|---|"]
    for model, _, times, use, total in sorted(summary, key=lambda s: -s[4]):
        lines.append(f"| {model} | {total:.2f} | {use:.0%} | {statistics.median(times):.1f} s |")
    for model, rows, *_ in summary:
        lines += ["", f"## {model}", "", "| English | Gloss | Face | Score |", "|---|---|---|---|", *rows]
    out_path = ROOT / "tmp" / "bench_llm.md"
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:4 + len(summary)]))
    print(f"\nfull results: {out_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
