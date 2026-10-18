"""Synthetic G2 mic clips: 16 kHz, signed 16-bit, mono, little-endian PCM (the format core/stt.py expects).

Generated in code so no binary audio is committed. None of this is real speech: the speech-to-text provider is
always mocked in tests/e2e, so the clip content only matters for byte counts and format edge cases.
"""

from __future__ import annotations

import math
import struct

RATE = 16_000
BYTES_PER_SECOND = RATE * 2


def silence(seconds: float) -> bytes:
    return b"\x00\x00" * int(RATE * seconds)


def tone(seconds: float, hz: float = 440.0, amp: float = 0.3) -> bytes:
    n = int(RATE * seconds)
    return b"".join(struct.pack("<h", int(amp * 32767 * math.sin(2 * math.pi * hz * i / RATE))) for i in range(n))


def odd_length(seconds: float = 1.0) -> bytes:
    """Half a sample at the end: not valid s16le."""
    return tone(seconds) + b"\x7f"


def wav_file(seconds: float = 1.0) -> bytes:
    """A RIFF/WAV container sent where raw PCM is expected (a plausible plugin/bridge mistake)."""
    data = tone(seconds)
    header = b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVEfmt " + struct.pack(
        "<IHHIIHH", 16, 1, 1, RATE, BYTES_PER_SECOND, 2, 16) + b"data" + struct.pack("<I", len(data))
    return header + data


def not_audio() -> bytes:
    """Clearly not audio (e.g. a JSON body posted to /audio by mistake), padded past the 0.3 s minimum."""
    return (b'{"phase":"start"}' * 1000)[: BYTES_PER_SECOND]
