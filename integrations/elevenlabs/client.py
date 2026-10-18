"""Bounded ElevenLabs transports. No recording, automatic retries, or provider-body logging.

Official references (checked 2026-10-17):
https://elevenlabs.io/docs/api-reference/speech-to-text/v-1-speech-to-text-realtime
https://elevenlabs.io/docs/api-reference/text-to-speech/convert
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import re
from urllib.parse import urlencode

import httpx


class VoiceProviderError(Exception):
    """Safe, credential-free message suitable for a client error response."""


class ElevenLabsStt:
    """One deliberate PTT utterance, signed PCM16 little-endian mono at 16 kHz.

    Only a committed transcript can become a command. Never act on partials.
    Manual commits keep an utterance atomic: no background VAD-triggered actions.
    The provider may retain audio according to the account's policy; GhostBuild
    itself never records it. Do not promise provider zero retention without the
    appropriate ElevenLabs account entitlement.
    """
    name = "elevenlabs"
    origin = "elevenlabs_stt"
    URL = "wss://api.elevenlabs.io/v1/speech-to-text/realtime"

    def __init__(self, api_key: str, *, url: str | None = None,
                 model: str = "scribe_v2_realtime", timeout_s: float = 5.0):
        self.api_key = api_key
        self.base = url or self.URL
        self.model = model
        self.timeout_s = timeout_s
        self._ws = None
        self._bytes = 0
        self._finalized = False

    def endpoint(self) -> str:
        return self.base + "?" + urlencode({"model_id": self.model,
            "audio_format": "pcm_16000", "commit_strategy": "manual"})

    async def start(self) -> None:
        from websockets.asyncio.client import connect
        try:
            self._ws = await asyncio.wait_for(connect(self.endpoint(),
                additional_headers={"xi-api-key": self.api_key}, max_size=2**20,
                close_timeout=1), self.timeout_s)
        except Exception:
            raise VoiceProviderError("ElevenLabs speech connection unavailable") from None

    async def feed(self, frame: bytes) -> None:
        if self._ws is None or self._finalized:
            raise VoiceProviderError("Speech session is not listening")
        if len(frame) % 2 or self._bytes + len(frame) > 640_000:
            raise VoiceProviderError("Invalid or oversized PCM audio")
        if not frame:
            return
        self._bytes += len(frame)
        await asyncio.wait_for(self._ws.send(json.dumps({
            "message_type": "input_audio_chunk", "audio_base_64": base64.b64encode(frame).decode("ascii"),
            "sample_rate": 16000, "commit": False})), self.timeout_s)

    async def finalize(self) -> str:
        if self._ws is None or self._finalized:
            raise VoiceProviderError("Speech session has already ended")
        self._finalized = True
        if self._bytes < 9600:  # <300 ms: tap/noise never issues a command
            return ""
        try:
            async with asyncio.timeout(7):
                # Scribe starts processing after two seconds of input. Pad short
                # intentional commands with silence so "next" does not hang.
                # This generates no speech and never changes the heard words.
                padding = b"\0" * max(0, 64_000 - self._bytes)
                await self._ws.send(json.dumps({"message_type": "input_audio_chunk",
                    "audio_base_64": base64.b64encode(padding).decode("ascii"),
                    "sample_rate": 16000, "commit": True}))
                while True:
                    raw = await self._ws.recv()
                    ev = json.loads(raw)
                    if not isinstance(ev, dict):
                        raise VoiceProviderError("Invalid speech response")
                    kind = ev.get("message_type", "")
                    if kind == "committed_transcript":
                        text = ev.get("text")
                        if not isinstance(text, str):
                            raise VoiceProviderError("Invalid speech transcript")
                        return text.strip()[:300]
                    if kind not in ("session_started", "partial_transcript", "warning"):
                        # Includes auth_error, quota_exceeded, rate_limited, input_error.
                        # Provider error strings may contain secrets or user audio: never relay.
                        raise VoiceProviderError("ElevenLabs speech unavailable; use touch")
        except VoiceProviderError:
            raise
        except Exception:
            raise VoiceProviderError("ElevenLabs speech response unavailable") from None

    async def close(self) -> None:
        ws, self._ws = self._ws, None
        if ws is not None:
            try:
                await asyncio.wait_for(ws.close(), 2)
            except Exception:
                pass


def elevenlabs_factory() -> ElevenLabsStt:
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not key:
        raise VoiceProviderError("ELEVENLABS_API_KEY not configured")
    return ElevenLabsStt(key, model=os.environ.get("ELEVENLABS_STT_MODEL", "scribe_v2_realtime"))


async def synthesize(text: str, *, consent: bool = False,
                     transport: httpx.AsyncBaseTransport | None = None) -> bytes:
    """Return one MP3 reply for phone/earbuds; cancellation closes the HTTP request.

    Caller enforces the feature flag, request cooldown, and stops previous playback.
    No automatic retry: an uncertain POST must not cause duplicate paid generation.
    Explicitly asking again is the bounded retry mechanism for 429/timeouts.
    """
    if consent is not True:
        raise VoiceProviderError("Enable spoken replies to send text to ElevenLabs")
    text = text.strip()
    if not text or len(text) > 500:
        raise VoiceProviderError("Spoken reply must contain 1 to 500 characters")
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    voice = os.environ.get("ELEVENLABS_VOICE_ID", "").strip()
    if not key or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", voice):
        raise VoiceProviderError("ElevenLabs spoken replies are not configured")
    model = os.environ.get("ELEVENLABS_TTS_MODEL", "eleven_flash_v2_5")
    try:
        async with asyncio.timeout(12):
            async with httpx.AsyncClient(timeout=10, transport=transport) as client:
                async with client.stream("POST", f"https://api.elevenlabs.io/v1/text-to-speech/{voice}",
                    params={"output_format": "mp3_22050_32"},
                    headers={"xi-api-key": key, "Accept": "audio/mpeg"},
                    json={"text": text, "model_id": model}) as response:
                    if response.status_code == 429:
                        raise VoiceProviderError("Spoken replies rate limited; wait and try again")
                    if response.status_code != 200:
                        raise VoiceProviderError("Spoken replies unavailable; use text")
                    if not response.headers.get("content-type", "").lower().startswith("audio/"):
                        raise VoiceProviderError("Invalid spoken reply response")
                    output = bytearray()
                    async for chunk in response.aiter_bytes():
                        output.extend(chunk)
                        if len(output) > 2_000_000:
                            raise VoiceProviderError("Spoken reply exceeds audio limit")
                    if not output:
                        raise VoiceProviderError("Empty spoken reply")
                    return bytes(output)
    except VoiceProviderError:
        raise
    except Exception:
        raise VoiceProviderError("Spoken replies unavailable; use text") from None
