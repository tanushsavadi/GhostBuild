from __future__ import annotations

from ghostbuild_core import stt


def test_silence_and_short_clips_skip_the_provider(monkeypatch):
    monkeypatch.delenv("GB_STT_FAKE", raising=False)
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    assert stt.transcribe(b"") == ""
    assert stt.transcribe(b"\x00" * int(stt.BYTES_PER_SECOND * 0.2)) == ""  # < 0.3 s: no call, no key needed


def test_fake_mode_for_dev(monkeypatch):
    monkeypatch.setenv("GB_STT_FAKE", "which leg is longer")
    assert stt.available()
    assert stt.transcribe(b"\x00" * stt.BYTES_PER_SECOND) == "which leg is longer"


def test_multipart_carries_pcm_format_and_bytes():
    body, ctype = stt._multipart({"model_id": "scribe_v1", "file_format": "pcm_s16le_16"}, b"\x01\x02")
    boundary = ctype.split("boundary=")[1]
    assert body.startswith(f"--{boundary}".encode()) and body.endswith(f"--{boundary}--\r\n".encode())
    assert b'name="file_format"\r\n\r\npcm_s16le_16' in body and b"\x01\x02" in body
