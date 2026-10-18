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
  GET  /api/health  -> which keys/models are available (never the keys themselves)

The plugin reaches this through the Vite dev server's /api proxy, so the phone
only needs port 5173. Audio is forwarded and dropped: nothing is stored or logged.
Keys come from .env in the repo root (ELEVENLABS_API_KEY). The model only orders
signs; the plugin builds every card from its own checked data.

Run (from the repo root):  uv run tools/open_palm_server.py
"""

from __future__ import annotations

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

WH = {"WHO", "WHAT", "WHERE", "WHEN", "WHY", "HOW", "WHICH"}
FILLER = {"IS", "ARE", "AM", "WAS", "WERE", "THE", "A", "AN", "DO", "DOES", "DID", "TO", "BE", "OF", "WILL"}
# Compounds the model invents -> the sign names our vocabulary uses.
RENAME = {"I": ["ME"], "NOT-LIKE": ["DONT-LIKE"], "NOT-KNOW": ["DONT-KNOW"], "DO-NOT-KNOW": ["DONT-KNOW"],
          "NOT-WANT": ["DONT-WANT"], "DONT-UNDERSTAND": ["NOT-UNDERSTAND"], "SIGN-LANGUAGE": ["SIGN-LANGUAGE"]}
KEEP_COMPOUND = {"NOT-UNDERSTAND", "DONT-KNOW", "DONT-LIKE", "DONT-WANT", "THANK-YOU", "I-LOVE-YOU", "SIGN-LANGUAGE"}


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
    body = {"model": MODEL, "stream": False, "format": bench.SCHEMA, "keep_alive": "60m", "think": False,
            "options": {"temperature": 0}, "messages": bench.messages(text)}
    t0 = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.post(OLLAMA, json=body)
        res.raise_for_status()
        answer = json.loads(res.json()["message"]["content"])
    except (httpx.HTTPError, KeyError, ValueError) as err:
        raise HTTPException(503, f"local model unavailable: {type(err).__name__}")
    face = answer.get("face", "") if answer.get("face") in ("brows down", "brows up", "head shake") else ""
    signs = clean(answer.get("signs", []), face)
    ms = round((time.perf_counter() - t0) * 1000)
    print(f"[translate] {len(text)} chars -> {len(signs)} signs in {ms} ms")
    return {"signs": signs, "face": face, "source": "AI · LOCAL", "ms": ms}


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


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")
