"""Speech-to-text for hold-to-talk on G2. Server-side only: the key never reaches the plugin.

Input is the G2 mic format: 16 kHz, signed 16-bit, mono, little-endian PCM.
Provider: ElevenLabs Speech-to-Text (POST /v1/speech-to-text, file_format=pcm_s16le_16).
  ELEVENLABS_API_KEY     required for real transcription
  ELEVENLABS_STT_MODEL   default scribe_v1
  GB_STT_FAKE            dev only: return this text instead of calling the provider
"""

from __future__ import annotations

import json
import os
import urllib.request
import uuid

URL = "https://api.elevenlabs.io/v1/speech-to-text"
BYTES_PER_SECOND = 16_000 * 2
MIN_SECONDS = 0.3


def available() -> bool:
    return bool(os.environ.get("GB_STT_FAKE") or os.environ.get("ELEVENLABS_API_KEY"))


def _multipart(fields: dict[str, str], file_bytes: bytes) -> tuple[bytes, str]:
    boundary = f"gb{uuid.uuid4().hex}"
    out = bytearray()
    for name, value in fields.items():
        out += f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode()
    out += (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="ptt.pcm"\r\n'
            "Content-Type: application/octet-stream\r\n\r\n").encode()
    out += file_bytes + f"\r\n--{boundary}--\r\n".encode()
    return bytes(out), f"multipart/form-data; boundary={boundary}"


def transcribe(pcm: bytes, timeout: float = 15.0) -> str:
    """Blocking HTTP call: run it in a worker thread, never on the live loop. Returns '' for silence."""
    if len(pcm) < BYTES_PER_SECOND * MIN_SECONDS:
        return ""
    fake = os.environ.get("GB_STT_FAKE")
    if fake:
        return fake
    body, ctype = _multipart(
        {"model_id": os.environ.get("ELEVENLABS_STT_MODEL", "scribe_v1"), "file_format": "pcm_s16le_16",
         "language_code": "en", "tag_audio_events": "false"},
        pcm,
    )
    req = urllib.request.Request(URL, data=body, method="POST",
                                 headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"], "Content-Type": ctype})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return (json.loads(resp.read() or b"{}").get("text") or "").strip()
