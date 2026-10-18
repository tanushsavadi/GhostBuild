"""LOCAL protocol and HTTP fakes only: these are not live ElevenLabs evidence."""
import asyncio
import base64
import json
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from websockets.asyncio.server import serve

from integrations.elevenlabs.client import ElevenLabsStt, VoiceProviderError, synthesize

PCM = b"\x00\x01" * 4800


def test_realtime_documented_pcm_protocol_commits_once_and_ignores_partials():
    seen = {}

    async def handler(ws):
        seen["key"] = ws.request.headers["xi-api-key"]
        seen["query"] = parse_qs(urlsplit(ws.request.path).query)
        seen["audio"] = bytearray()
        seen["commits"] = 0
        await ws.send(json.dumps({"message_type": "session_started"}))
        async for raw in ws:
            ev = json.loads(raw)
            assert ev["message_type"] == "input_audio_chunk" and ev["sample_rate"] == 16000
            seen["audio"].extend(base64.b64decode(ev["audio_base_64"]))
            if ev["commit"]:
                seen["commits"] += 1
                await ws.send(json.dumps({"message_type": "partial_transcript", "text": "done"}))
                await ws.send(json.dumps({"message_type": "committed_transcript", "text": "where is that?"}))

    async def run():
        async with serve(handler, "127.0.0.1", 0) as srv:
            stt = ElevenLabsStt("test-only-key", url=f"ws://127.0.0.1:{srv.sockets[0].getsockname()[1]}/realtime")
            await stt.start()
            await stt.feed(PCM)
            assert await stt.finalize() == "where is that?"
            with pytest.raises(VoiceProviderError):
                await stt.finalize()
            await stt.close()

    asyncio.run(run())
    assert seen["audio"] == PCM + b"\0" * (64_000 - len(PCM)) and seen["commits"] == 1
    assert seen["key"] == "test-only-key"
    assert seen["query"] == {"model_id": ["scribe_v2_realtime"], "audio_format": ["pcm_16000"], "commit_strategy": ["manual"]}


@pytest.mark.parametrize("event", [
    {"message_type": "rate_limited", "error": "secret-do-not-echo"},
    {"message_type": "auth_error", "error": "secret-do-not-echo"},
    {"message_type": "committed_transcript", "text": None},
    ["malformed"],
])
def test_provider_errors_fail_closed_without_relaying_provider_text(event):
    async def handler(ws):
        async for raw in ws:
            if json.loads(raw).get("commit"):
                await ws.send(json.dumps(event))

    async def run():
        async with serve(handler, "127.0.0.1", 0) as srv:
            stt = ElevenLabsStt("test-key", url=f"ws://127.0.0.1:{srv.sockets[0].getsockname()[1]}/realtime")
            await stt.start()
            await stt.feed(PCM)
            with pytest.raises(VoiceProviderError) as err:
                await stt.finalize()
            assert "secret-do-not-echo" not in str(err.value)
            await stt.close()
    asyncio.run(run())


def test_short_clip_not_committed_and_invalid_pcm_rejected():
    async def handler(ws):
        async for raw in ws:
            assert json.loads(raw).get("commit") is not True

    async def run():
        async with serve(handler, "127.0.0.1", 0) as srv:
            stt = ElevenLabsStt("test-key", url=f"ws://127.0.0.1:{srv.sockets[0].getsockname()[1]}/realtime")
            await stt.start()
            with pytest.raises(VoiceProviderError):
                await stt.feed(b"x")
            with pytest.raises(VoiceProviderError):
                await stt.feed(b"\0" * 640002)
            await stt.feed(b"\0" * 100)
            assert await stt.finalize() == ""
            await stt.close()
    asyncio.run(run())


def test_unreachable_provider_has_safe_error():
    async def run():
        with pytest.raises(VoiceProviderError, match="unavailable"):
            await ElevenLabsStt("test-key", url="ws://127.0.0.1:1/realtime").start()
    asyncio.run(run())


@pytest.fixture
def tts_env(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-only-key")
    monkeypatch.setenv("ELEVENLABS_VOICE_ID", "configured-stock-voice")
    monkeypatch.delenv("ELEVENLABS_TTS_MODEL", raising=False)


@pytest.mark.asyncio
async def test_tts_actual_http_shape_with_mock_transport(tts_env):
    def handler(request):
        assert str(request.url) == "https://api.elevenlabs.io/v1/text-to-speech/configured-stock-voice?output_format=mp3_22050_32"
        assert request.headers["xi-api-key"] == "test-only-key"
        assert json.loads(request.content) == {"text": "Documented current step", "model_id": "eleven_flash_v2_5"}
        return httpx.Response(200, content=b"MP3-FAKE", headers={"content-type": "audio/mpeg"})
    assert await synthesize("Documented current step", consent=True, transport=httpx.MockTransport(handler)) == b"MP3-FAKE"


@pytest.mark.asyncio
@pytest.mark.parametrize("status,ctype,body", [(429, "application/json", b"secret"), (401, "application/json", b"secret"), (503, "text/html", b"secret"), (200, "text/html", b"secret"), (200, "audio/mpeg", b"")])
async def test_tts_errors_mask_body_and_do_not_retry(tts_env, status, ctype, body):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(status, content=body, headers={"content-type": ctype})
    with pytest.raises(VoiceProviderError) as err:
        await synthesize("Current context", consent=True, transport=httpx.MockTransport(handler))
    assert "secret" not in str(err.value) and len(calls) == 1


@pytest.mark.asyncio
async def test_tts_consent_configuration_length_and_cancellation(tts_env, monkeypatch):
    def forbidden(request):
        pytest.fail("must not call provider")
    transport = httpx.MockTransport(forbidden)
    for text, consent in [("hello", False), ("", True), ("x" * 501, True)]:
        with pytest.raises(VoiceProviderError):
            await synthesize(text, consent=consent, transport=transport)
    monkeypatch.delenv("ELEVENLABS_VOICE_ID")
    with pytest.raises(VoiceProviderError):
        await synthesize("hello", consent=True, transport=transport)
    monkeypatch.setenv("ELEVENLABS_VOICE_ID", "stock")
    entered = asyncio.Event()
    cancelled = asyncio.Event()
    async def pending(request):
        entered.set()
        try:
            await asyncio.Future()
        finally:
            cancelled.set()
    task = asyncio.create_task(synthesize("hello", consent=True, transport=httpx.MockTransport(pending)))
    await asyncio.wait_for(entered.wait(), 1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert cancelled.is_set()
