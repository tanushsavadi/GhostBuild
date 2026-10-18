# /// script
# requires-python = ">=3.10"
# dependencies = ["fastapi>=0.110", "uvicorn>=0.29", "httpx>=0.27"]
# ///
"""Open Palm laptop server: keeps the API keys off the phone.

  POST /api/stt     body = raw PCM (16 kHz, 16-bit, mono, little-endian, as the
                    G2 microphone delivers it) -> ElevenLabs speech-to-text
                    -> {"text": "...", "ms": 812}
  GET  /api/health  -> which keys are configured (never the keys themselves)

The plugin reaches this through the Vite dev server's /api proxy, so the phone
only needs port 5173. Audio is forwarded and dropped: nothing is stored or logged.
Keys come from .env in the repo root (ELEVENLABS_API_KEY).

Run (from the repo root):  uv run tools/open_palm_server.py
"""

from __future__ import annotations

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
def health() -> dict:
    return {"ok": True, "elevenlabs": bool(os.environ.get("ELEVENLABS_API_KEY"))}


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
