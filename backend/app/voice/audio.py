from __future__ import annotations

import math
import struct

from app.core.errors import InvalidInput, Refused
from app.schemas.voice import RELAY_MAX_AUDIO_BYTES, RELAY_MAX_TURN_SECONDS, RELAY_MAX_WAV_BYTES

from .audio_decode import Measure

__all__ = ["WAV_TYPE", "upload_seconds", "wav_seconds"]

WAV_TYPE = "audio/wav"
TOO_LONG = "too_long"
PCM = 1
FLOAT = 3
EXTENSIBLE = 0xFFFE
SAMPLE_BITS = frozenset({8, 16, 24, 32})
SAMPLE_RATES = range(8_000, 192_001)
MAX_CHANNELS = 8
FMT_BYTES = 16
EXTENSIBLE_FMT_BYTES = 26


async def upload_seconds(content: bytes, content_type: str, measure: Measure) -> int:
    if content_type == WAV_TYPE:
        if len(content) > RELAY_MAX_WAV_BYTES:
            raise _too_long()
        seconds = wav_seconds(content)
    else:
        if len(content) > RELAY_MAX_AUDIO_BYTES:
            raise _too_long()
        seconds = await measure(content)
    if seconds > RELAY_MAX_TURN_SECONDS:
        raise _too_long()
    return max(1, math.ceil(seconds))


def wav_seconds(content: bytes) -> float:
    if len(content) < 12 or content[:4] != b"RIFF" or content[8:12] != b"WAVE":
        raise InvalidInput("The recording is not a RIFF WAVE file")
    fmt, data_bytes = _wav_chunks(content)
    if len(fmt) < FMT_BYTES:
        raise InvalidInput("The WAV format chunk is too short")
    kind, channels, rate, _, _, bits = struct.unpack_from("<HHIIHH", fmt)
    if kind == EXTENSIBLE and len(fmt) >= EXTENSIBLE_FMT_BYTES:
        kind = struct.unpack_from("<H", fmt, 24)[0]
    if kind not in (PCM, FLOAT) or bits not in SAMPLE_BITS:
        raise InvalidInput("A WAV recording must be uncompressed PCM")
    if rate not in SAMPLE_RATES or not 1 <= channels <= MAX_CHANNELS:
        raise InvalidInput("The WAV recording has an impossible sample rate or channel count")
    return data_bytes / (rate * channels * (bits // 8))


def _wav_chunks(content: bytes) -> tuple[bytes, int]:
    fmt: bytes | None = None
    position = 12
    while position + 8 <= len(content):
        name = content[position : position + 4]
        size = int.from_bytes(content[position + 4 : position + 8], "little")
        body = position + 8
        if name == b"fmt ":
            fmt = content[body : body + size]
        elif name == b"data":
            if fmt is None:
                raise InvalidInput("The WAV data comes before its format")
            return fmt, min(size, len(content) - body)
        position = body + size + (size & 1)
    raise InvalidInput("The WAV file holds no audio data")


def _too_long() -> Refused:
    return Refused(TOO_LONG, "That recording is too long.")
