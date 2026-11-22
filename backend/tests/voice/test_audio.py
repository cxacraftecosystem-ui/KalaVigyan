import io
import struct
import wave
from collections.abc import Awaitable, Callable, Sequence

import pytest

from app.core.errors import InvalidInput, Refused
from app.voice.audio import upload_seconds, wav_seconds
from app.voice.audio_decode import DECODE_ARGS, FFMPEG, decoded_seconds


def wav(seconds: float, *, rate: int = 16_000, channels: int = 1, width: int = 2) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as out:
        out.setnchannels(channels)
        out.setsampwidth(width)
        out.setframerate(rate)
        out.writeframes(b"\x00" * int(seconds * rate) * channels * width)
    return buffer.getvalue()


def test_a_wav_lasts_its_frames_over_its_rate() -> None:
    assert wav_seconds(wav(2.5)) == pytest.approx(2.5)
    assert wav_seconds(wav(1.0, rate=48_000, channels=2)) == pytest.approx(1.0)


async def test_a_wav_is_charged_its_length_rounded_up_without_decoding() -> None:
    assert await upload_seconds(wav(12.2), "audio/wav", never_decoded) == 13
    assert await upload_seconds(wav(60.0, rate=8_000), "audio/wav", never_decoded) == 60


async def test_a_wav_over_a_minute_is_refused_whatever_its_size() -> None:
    with pytest.raises(Refused) as refused:
        await upload_seconds(wav(61.0, rate=8_000, width=1), "audio/wav", never_decoded)
    assert refused.value.reason == "too_long"


def test_a_wav_that_lies_about_its_data_size_is_measured_by_what_it_holds() -> None:
    honest = wav(3.0)
    swollen = honest[:40] + struct.pack("<I", 0xFFFFFFFF) + honest[44:]
    assert wav_seconds(swollen) == pytest.approx(3.0)


def test_a_compressed_wav_or_a_stray_file_is_refused() -> None:
    compressed = bytearray(wav(1.0))
    compressed[20:22] = struct.pack("<H", 0x55)
    for body in (bytes(compressed), b"OggS" + b"\x00" * 64, b"RIFF\x00\x00\x00\x00WAVE"):
        with pytest.raises(InvalidInput):
            wav_seconds(body)


async def test_compressed_audio_is_charged_its_decoded_length_rounded_up() -> None:
    assert await upload_seconds(b"x", "audio/webm", lasting(0.2)) == 1
    assert await upload_seconds(b"x" * 1_000, "audio/ogg", lasting(12.3)) == 13


async def test_a_low_rate_upload_decoding_past_a_minute_is_refused_before_speech_to_text() -> None:
    with pytest.raises(Refused) as refused:
        await upload_seconds(b"x" * 300_000, "audio/webm", lasting(400.0))
    assert refused.value.reason == "too_long"


async def test_compressed_audio_above_the_byte_ceiling_is_refused_without_decoding() -> None:
    with pytest.raises(Refused):
        await upload_seconds(b"x" * 300_001, "audio/webm", never_decoded)


async def test_the_decoder_s_last_progress_time_is_the_recording_s_length() -> None:
    progress = b"frame=0\nout_time_us=5000000\nprogress=continue\nout_time_us=12340000\nprogress=end\n"
    asked: list[tuple[str, ...]] = []

    async def run(argv: Sequence[str], content: bytes) -> tuple[int, bytes]:
        asked.append(tuple(argv))
        assert content == b"opus"
        return 0, progress

    assert await decoded_seconds(b"opus", run=run) == 12.34
    assert asked == [(FFMPEG, *DECODE_ARGS)] and "pipe:0" in DECODE_ARGS


async def test_audio_the_decoder_cannot_read_or_that_holds_no_sound_is_refused() -> None:
    async def failing(argv: Sequence[str], content: bytes) -> tuple[int, bytes]:
        return 1, b""

    async def silent(argv: Sequence[str], content: bytes) -> tuple[int, bytes]:
        return 0, b"out_time_us=0\nprogress=end\n"

    for run in (failing, silent):
        with pytest.raises(InvalidInput):
            await decoded_seconds(b"junk", run=run)


def lasting(seconds: float) -> Callable[[bytes], Awaitable[float]]:
    async def measure(content: bytes) -> float:
        return seconds

    return measure


async def never_decoded(content: bytes) -> float:
    raise AssertionError("this upload is measured without decoding")
