from __future__ import annotations

import io
import math
import wave
from collections.abc import Sequence
from dataclasses import dataclass

from app.core.errors import ExternalFailure
from app.providers.gemini_media import SERVICE
from app.schemas.listen import ListenSentence

from .narration import TIME_PLACES, NarrationPart

__all__ = [
    "SAMPLE_BYTES",
    "Pcm",
    "SentenceTimed",
    "sentence_timed",
    "wav_file",
    "wav_frames",
]

SAMPLE_BYTES = 2
MONO = 1


@dataclass(frozen=True)
class Pcm:
    frames: bytes
    rate: int

    @property
    def count(self) -> int:
        return len(self.frames) // SAMPLE_BYTES


@dataclass(frozen=True)
class SentenceTimed:
    audio: bytes
    sentences: list[ListenSentence]
    duration_seconds: float
    billed_seconds: int


def wav_frames(audio: bytes) -> Pcm:
    try:
        with wave.open(io.BytesIO(audio), "rb") as read:
            shape = (read.getnchannels(), read.getsampwidth(), read.getframerate())
            frames = read.readframes(read.getnframes())
    except (wave.Error, EOFError) as error:
        raise _off_contract(f"speech that is not a readable WAV file ({error})") from None
    if shape[:2] != (MONO, SAMPLE_BYTES) or shape[2] <= 0 or not frames:
        raise _off_contract(f"speech of {shape[0]} channels at {shape[1] * 8} bits, or none")
    return Pcm(frames=frames, rate=shape[2])


def wav_file(frames: bytes, rate: int) -> bytes:
    body = io.BytesIO()
    with wave.open(body, "wb") as written:
        written.setnchannels(MONO)
        written.setsampwidth(SAMPLE_BYTES)
        written.setframerate(rate)
        written.writeframes(frames)
    return body.getvalue()


def sentence_timed(part: NarrationPart, spoken: Sequence[Pcm]) -> SentenceTimed:
    rates = {pcm.rate for pcm in spoken}
    if len(rates) != 1 or len(spoken) != len(part.sentences):
        raise _off_contract("the sentences of one part read at different sample rates, or not each once")
    rate = rates.pop()
    sentences: list[ListenSentence] = []
    reached = 0
    for sentence, pcm in zip(part.sentences, spoken, strict=True):
        sentences.append(
            ListenSentence(
                sentence_id=sentence.sentence_id,
                start=round(reached / rate, TIME_PLACES),
                end=round((reached + pcm.count) / rate, TIME_PLACES),
            )
        )
        reached += pcm.count
    return SentenceTimed(
        audio=wav_file(b"".join(pcm.frames for pcm in spoken), rate),
        sentences=sentences,
        duration_seconds=round(reached / rate, TIME_PLACES),
        billed_seconds=math.ceil(reached / rate),
    )


def _off_contract(what: str) -> ExternalFailure:
    return ExternalFailure(f"Gemini answered off the documented shape: {what}", service=SERVICE)
