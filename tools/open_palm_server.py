# /// script
# requires-python = ">=3.10"
# dependencies = ["fastapi>=0.110", "uvicorn>=0.29", "httpx>=0.27"]
# ///
"""Open Palm laptop server: keeps the API keys off the phone.

  POST /api/stt     body = raw PCM (16 kHz, 16-bit, mono, little-endian, as the
                    G2 microphone delivers it) -> ElevenLabs speech-to-text
                    -> {"text": "...", "ms": 812}
  POST /api/translate  {"text": "Where do you work?"} -> local model (Ollama,
                    qwen3.5:4b) -> cleaned ASL gloss order + face cue
                    -> {"signs": [{"gloss": "YOU", "spell": false}, ...],
                        "face": "brows down", "source": "AI · LOCAL", "ms": 2900}
  POST /api/prepare {"scenario": "Lunch with Sam", "use_history": true} -> CREAO
                    agent plans 6 sentences in ASL order (~1 min, background)
                    -> {"job": "1"}; GET /api/prepare/1 -> status + phrasebook
  GET  /api/phrasebook   the last prepared phrasebook
  POST /api/history {"kind": "sentence"|"hard_sign", "text": ...}  opt-in, text only
  DELETE /api/history    forget it all
  GET  /api/health  -> which keys/models are available (never the keys themselves)

The plugin reaches this through the Vite dev server's /api proxy, so the phone
only needs port 5173. Audio is forwarded and dropped: nothing is stored or logged.
Keys come from .env in the repo root (ELEVENLABS_API_KEY). The model only orders
signs; the plugin builds every card from its own checked data.

Run (from the repo root):  uv run tools/open_palm_server.py
"""

from __future__ import annotations

import asyncio
import copy
import importlib.util
import json
import os
import re
import time
from pathlib import Path

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Request

ROOT = Path(__file__).resolve().parent.parent
PORT = 8790
STT_URL = "https://api.elevenlabs.io/v1/speech-to-text"
MAX_AUDIO_BYTES = 16_000 * 2 * 30  # 30 s of 16 kHz 16-bit mono
OLLAMA = "http://127.0.0.1:11434/api/chat"
MODEL = os.environ.get("OPEN_PALM_MODEL", "qwen3.5:4b-q4_K_M")  # best in tools/bench_llm.py

# Same prompt the benchmark scored (tools/bench_llm.py), so results match.
_spec = importlib.util.spec_from_file_location("bench_llm", ROOT / "tools" / "bench_llm.py")
bench = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bench)

# The benchmark prompt plus an emotion for the face picture (happy / sad / surprised).
EMOTIONS = ("happy", "sad", "surprised")
SCHEMA = copy.deepcopy(bench.SCHEMA)
SCHEMA["properties"]["emotion"] = {"type": "string", "enum": [*EMOTIONS, ""]}
SCHEMA["required"] = [*SCHEMA["required"], "emotion"]
EMOTION_RULE = ('\n- emotion: the feeling to show on the face: "happy" (greetings, thanks, good news), '
                '"sad" (sorry, bad news), "surprised" (wow, really?), else "".')


def messages(text: str) -> list[dict]:
    msgs = bench.messages(text)
    msgs[0] = {**msgs[0], "content": msgs[0]["content"] + EMOTION_RULE}
    return msgs


WH = {"WHO", "WHAT", "WHERE", "WHEN", "WHY", "HOW", "WHICH"}
FILLER = {"IS", "ARE", "AM", "WAS", "WERE", "THE", "A", "AN", "DO", "DOES", "DID", "TO", "BE", "OF", "WILL"}
# Compounds the model invents -> the sign names our vocabulary uses.
RENAME = {"I": ["ME"], "NOT-LIKE": ["DONT-LIKE"], "NOT-KNOW": ["DONT-KNOW"], "DO-NOT-KNOW": ["DONT-KNOW"],
          "NOT-WANT": ["DONT-WANT"], "DONT-UNDERSTAND": ["NOT-UNDERSTAND"], "SIGN-LANGUAGE": ["SIGN-LANGUAGE"]}
KEEP_COMPOUND = {"NOT-UNDERSTAND", "DONT-KNOW", "DONT-LIKE", "DONT-WANT", "THANK-YOU", "I-LOVE-YOU", "SIGN-LANGUAGE"}


QUESTION_START = re.compile(r"^\s*(do|does|did|are|is|am|was|were|can|could|will|would|have|has|should|may)\b", re.I)


def check_face(face: str, english: str, signs: list[dict]) -> str:
    """The model puts question brows on statements now and then; keep them only for real questions."""
    question = english.strip().endswith("?") or bool(QUESTION_START.match(english))
    if face == "brows down" and not any(s["gloss"] in WH for s in signs):
        return ""
    if face == "brows up" and not question:
        return ""
    return face


def clean(signs: list[dict], face: str) -> list[dict]:
    """Fix the model's known slips (see the benchmark notes in docs/OPEN_PALM_PLAN.md)."""
    out: list[dict] = []
    for s in signs:
        gloss = re.sub(r"[^A-Z0-9\-]", "", str(s.get("gloss", "")).upper()).strip("-")
        if not gloss or gloss in FILLER:
            continue
        spell = bool(s.get("spell"))
        if gloss in RENAME:
            out += [{"gloss": g, "spell": False} for g in RENAME[gloss]]
        elif gloss.startswith("NOT-") and gloss not in KEEP_COMPOUND:
            out += [{"gloss": gloss[4:], "spell": False}, {"gloss": "NOT", "spell": False}]  # NOT-HUNGRY -> HUNGRY NOT
        else:
            out.append({"gloss": gloss, "spell": spell})
    # ASL puts the question word last in what/where/who... questions.
    if face == "brows down":
        wh = [s for s in out if s["gloss"] in WH]
        out = [s for s in out if s["gloss"] not in WH] + wh[:1]
    deduped = [s for i, s in enumerate(out) if i == 0 or s["gloss"] != out[i - 1]["gloss"]]
    return deduped


def load_env() -> None:
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8-sig").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


load_env()
app = FastAPI(title="Open Palm laptop server")


@app.get("/api/health")
async def health() -> dict:
    model_ready = False
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            tags = (await client.get("http://127.0.0.1:11434/api/tags")).json()
        model_ready = any(m.get("name") == MODEL for m in tags.get("models", []))
    except httpx.HTTPError:
        pass
    return {"ok": True, "elevenlabs": bool(os.environ.get("ELEVENLABS_API_KEY")), "model": MODEL, "model_ready": model_ready}


@app.post("/api/translate")
async def translate(request: Request) -> dict:
    text = str((await request.json()).get("text", "")).strip()[:300]
    if not text:
        raise HTTPException(400, "no text")
    body = {"model": MODEL, "stream": False, "format": SCHEMA, "keep_alive": "60m", "think": False,
            "options": {"temperature": 0}, "messages": messages(text)}
    t0 = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.post(OLLAMA, json=body)
        res.raise_for_status()
        answer = json.loads(res.json()["message"]["content"])
    except (httpx.HTTPError, KeyError, ValueError) as err:
        raise HTTPException(503, f"local model unavailable: {type(err).__name__}")
    face = answer.get("face", "") if answer.get("face") in ("brows down", "brows up", "head shake") else ""
    emotion = answer.get("emotion", "") if answer.get("emotion") in EMOTIONS else ""
    signs = clean(answer.get("signs", []), face)
    face = check_face(face, text, signs)
    ms = round((time.perf_counter() - t0) * 1000)
    print(f"[translate] {len(text)} chars -> {len(signs)} signs in {ms} ms")
    return {"signs": signs, "face": face, "emotion": emotion, "source": "AI · LOCAL", "ms": ms}


@app.on_event("startup")
async def warm_model() -> None:
    """Load the model into GPU memory now, so the first sentence isn't slow."""
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            await client.post(OLLAMA, json={"model": MODEL, "messages": [], "keep_alive": "60m"})
        print(f"[translate] {MODEL} loaded")
    except httpx.HTTPError:
        print(f"[translate] {MODEL} not loaded (is Ollama running?)")


@app.post("/api/stt")
async def stt(request: Request) -> dict:
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        raise HTTPException(503, "ELEVENLABS_API_KEY is not set in .env")
    pcm = await request.body()
    if len(pcm) < 16_000 * 2 // 5:  # under 0.2 s: nothing said
        return {"text": "", "ms": 0}
    if len(pcm) > MAX_AUDIO_BYTES:
        raise HTTPException(413, "audio longer than 30 s")
    t0 = time.perf_counter()
    async with httpx.AsyncClient(timeout=20) as client:
        res = await client.post(
            STT_URL,
            headers={"xi-api-key": key},
            data={"model_id": "scribe_v2", "file_format": "pcm_s16le_16", "language_code": "en",
                  "tag_audio_events": "false"},
            files={"file": ("speech.pcm", pcm, "application/octet-stream")},
        )
    ms = round((time.perf_counter() - t0) * 1000)
    if res.status_code != 200:
        # ElevenLabs' error text, without echoing anything we sent.
        raise HTTPException(502, f"ElevenLabs {res.status_code}: {res.text[:200]}")
    # Sound labels such as "[static]" or "(laughs)" are not words to sign.
    text = re.sub(r"\[[^\]]*\]|\([^)]*\)", " ", res.json().get("text", ""))
    text = re.sub(r"\s+", " ", text).strip()
    print(f"[stt] {len(pcm) / 32000:.1f} s audio -> {len(text)} chars in {ms} ms")
    return {"text": text, "ms": ms}


# ---- conversation prep (CREAO agent) and opt-in history ------------------------
# A CREAO run takes ~45 s, so prep is a background job: POST starts it, the
# phone polls GET. The result is cleaned like /api/translate and saved as the
# phrasebook, which the phone uses instantly during the conversation.
# History is text only, opt-in from the phone, kept in tmp/ on this laptop.

CREAO_URL = "https://agent.creao.ai/api/v1/runs"
DATA = ROOT / "tmp" / "open_palm"
HISTORY = DATA / "history.jsonl"
PHRASEBOOK = DATA / "phrasebook.json"
jobs: dict[str, dict] = {}
PREP_SENTENCES = 6


def creao_headers() -> dict:
    key = os.environ.get("CREAO_API_KEY")
    if not key:
        raise HTTPException(503, "CREAO_API_KEY is not set in .env")
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def history_summary(limit: int = 30) -> str:
    if not HISTORY.exists():
        return ""
    rows = [json.loads(line) for line in HISTORY.read_text(encoding="utf-8").splitlines() if line.strip()]
    sentences = [r["text"] for r in rows if r.get("kind") == "sentence"][-limit:]
    hard = [r["text"] for r in rows if r.get("kind") == "hard_sign"]
    hard = sorted(set(hard), key=lambda s: -hard.count(s))[:10]
    parts = []
    if sentences:
        parts.append("HISTORY: " + " | ".join(dict.fromkeys(sentences)))
    if hard:
        parts.append("HARD SIGNS: " + ", ".join(hard))
    return "\n".join(parts)


def extract_json(text: str) -> dict | None:
    """The agent's JSON, whether bare, wrapped in {"response": ...} or inside a code fence."""
    for candidate in (text, re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M)):
        try:
            data = json.loads(candidate)
        except (ValueError, TypeError):
            match = re.search(r"\{.*\}", candidate or "", re.S)
            if not match:
                continue
            try:
                data = json.loads(match.group(0))
            except ValueError:
                continue
        if isinstance(data, dict) and isinstance(data.get("response"), str):
            return extract_json(data["response"])
        if isinstance(data, dict):
            return data
    return None


async def run_prep(job_id: str, scenario: str) -> None:
    job = jobs[job_id]
    app_id = os.environ.get("CREAO_PREP_APP_ID", "")
    # Kept short on purpose: fewer sentences to rehearse, and a faster run.
    text = (f"{scenario}\n\nGive exactly {PREP_SENTENCES} sentences and at most 4 practice signs. "
            'Give each sentence an "emotion" too: "happy", "sad", "surprised" or "".'
            + ("\n\n" + history_summary() if job["use_history"] else ""))
    # The field CREAO reads isn't documented; this combination reached the agent in testing.
    body = {"appId": app_id, "input": text, "message": text, "prompt": text,
            "inputs": {"details": text, "input": text}, "text": text}
    t0 = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            run = (await client.post(CREAO_URL, json=body, headers=creao_headers())).json()
            run_id = run["id"]
            while time.perf_counter() - t0 < 240:
                await asyncio.sleep(3)
                data = (await client.get(f"{CREAO_URL}/{run_id}", headers=creao_headers())).json()
                if data.get("status") not in ("pending", "running", "queued", "in_progress"):
                    break
            if data.get("status") != "completed":
                raise RuntimeError(f"run ended as {data.get('status')}")
            result = data.get("result") or {}
            plan = extract_json(result.get("text", "")) or extract_json(result.get("chatText", ""))
            if not plan or "sentences" not in plan:  # the JSON may be in an attached file
                for art in result.get("artifacts", []):
                    if art.get("type") == "application/json":
                        # CREAO answers with a redirect to a pre-signed S3 link, which
                        # refuses requests that still carry the CREAO Authorization header.
                        res = await client.get(art["url"], headers=creao_headers())
                        if res.is_redirect:
                            res = await client.get(res.headers["location"])
                        plan = extract_json(res.text)
                        if plan and "sentences" in plan:
                            break
        if not plan or "sentences" not in plan:
            raise RuntimeError("no sentences in the agent's answer")
    except Exception as err:  # noqa: BLE001 - any failure is reported to the phone
        job.update(status="failed", error=f"{type(err).__name__}: {str(err)[:160]}")
        print(f"[prep] {job_id} failed: {job['error']}")
        return
    sentences = []
    for s in plan.get("sentences", [])[:PREP_SENTENCES + 2]:
        face = s.get("face", "") if s.get("face") in ("brows down", "brows up", "head shake") else ""
        signs = clean(s.get("signs", []), face)
        if s.get("english") and signs:
            emotion = s.get("emotion", "") if s.get("emotion") in EMOTIONS else ""
            face = check_face(face, str(s["english"]), signs)
            sentences.append({"english": str(s["english"])[:120], "signs": signs, "face": face, "emotion": emotion})
    book = {"title": str(plan.get("title") or scenario)[:80], "scenario": scenario, "sentences": sentences,
            "practice": [str(p).upper() for p in plan.get("practice", [])][:4], "source": "AI · CREAO",
            "ms": round((time.perf_counter() - t0) * 1000)}
    DATA.mkdir(parents=True, exist_ok=True)
    PHRASEBOOK.write_text(json.dumps(book, indent=1), encoding="utf-8")
    job.update(status="done", phrasebook=book)
    print(f"[prep] {job_id}: {len(sentences)} sentences in {book['ms']} ms")


@app.post("/api/prepare")
async def prepare(request: Request) -> dict:
    payload = await request.json()
    scenario = str(payload.get("scenario", "")).strip()[:500]
    if not scenario:
        raise HTTPException(400, "describe the conversation")
    if not os.environ.get("CREAO_PREP_APP_ID"):
        raise HTTPException(503, "CREAO_PREP_APP_ID is not set in .env")
    creao_headers()
    if any(j["status"] == "running" for j in jobs.values()):
        raise HTTPException(429, "a prep run is already going")
    job_id = f"{len(jobs) + 1}"
    jobs[job_id] = {"status": "running", "started": time.time(), "use_history": bool(payload.get("use_history"))}
    asyncio.create_task(run_prep(job_id, scenario))
    return {"job": job_id}


@app.get("/api/prepare/{job_id}")
def prepare_status(job_id: str) -> dict:
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "no such job")
    return {**job, "elapsed_s": round(time.time() - job["started"])}


@app.get("/api/phrasebook")
def phrasebook() -> dict:
    if PHRASEBOOK.exists():
        return json.loads(PHRASEBOOK.read_text(encoding="utf-8"))
    return {"title": "", "sentences": [], "practice": []}


@app.post("/api/history")
async def history(request: Request) -> dict:
    """Opt-in from the phone: a signed sentence or a sign the user opened HOW for. Text only."""
    payload = await request.json()
    kind = payload.get("kind")
    text = str(payload.get("text", "")).strip()[:200]
    if kind not in ("sentence", "hard_sign") or not text:
        raise HTTPException(400, "kind must be sentence or hard_sign")
    DATA.mkdir(parents=True, exist_ok=True)
    with HISTORY.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"kind": kind, "text": text, "at": int(time.time())}) + "\n")
    return {"ok": True}


@app.delete("/api/history")
def forget() -> dict:
    HISTORY.unlink(missing_ok=True)
    return {"ok": True}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")
