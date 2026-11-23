from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol

from app.providers.elevenlabs import (
    ELEVENLABS_SERVICE,
    NARRATION_MODEL,
    TTS_LANGUAGES,
    TimedSpeech,
    speech_seconds,
)
from app.providers.gemini_media import SERVICE as GEMINI_SERVICE, SPEECH_LANGUAGES, SPEECH_MODEL, SPEECH_VOICE
from app.research.vocabulary import ANSWER_LANGUAGES
from app.schemas.listen import ListenOffer, ListenSentence, ListenVoiceName, ListenWord

from .audio import WAV_TYPE
from .narration import NarrationPart, part_duration, part_words
from .narration_cache import AUDIO_TYPE
from .read_aloud import sentence_timed, wav_frames

__all__ = [
    "ElevenLabsVoice",
    "GeminiVoice",
    "ListenVoice",
    "Narrator",
    "ReadAloud",
    "SpokenPart",
    "listen_offer",
    "untagged",
]

NARRATION_TAG_BRACKETS = str.maketrans("[]", "()")


class Narrator(Protocol):
    async def narration(
        self, text: str, *, voice_id: str, language: str, previous_text: str = "", next_text: str = ""
    ) -> TimedSpeech: ...


class ReadAloud(Protocol):
    async def read_aloud(self, text: str, *, voice: str) -> bytes: ...


@dataclass(frozen=True)
class SpokenPart:
    audio: bytes
    duration_seconds: float
    billed_seconds: int
    words: list[ListenWord] = field(default_factory=list)
    sentences: list[ListenSentence] = field(default_factory=list)


class ListenVoice(Protocol):
    @property
    def name(self) -> ListenVoiceName: ...

    @property
    def model(self) -> str: ...

    @property
    def voice_id(self) -> str: ...

    @property
    def audio_type(self) -> str: ...

    @property
    def extension(self) -> str: ...

    @property
    def service(self) -> str: ...

    def speaks(self, language: str) -> bool: ...

    async def spoken(self, parts: Sequence[NarrationPart], index: int) -> SpokenPart: ...


@dataclass(frozen=True)
class ElevenLabsVoice:
    narrator: Narrator
    voice_id: str
    name: ListenVoiceName = "ELEVENLABS"
    model: str = NARRATION_MODEL
    audio_type: str = AUDIO_TYPE
    extension: str = "mp3"
    service: str = ELEVENLABS_SERVICE

    def speaks(self, language: str) -> bool:
        return language in TTS_LANGUAGES

    async def spoken(self, parts: Sequence[NarrationPart], index: int) -> SpokenPart:
        part = parts[index]
        speech = await self.narrator.narration(
            untagged(part.text),
            voice_id=self.voice_id,
            language=part.language,
            previous_text=untagged(parts[index - 1].text) if index else "",
            next_text=untagged(parts[index + 1].text) if index + 1 < len(parts) else "",
        )
        return SpokenPart(
            audio=speech.audio,
            duration_seconds=part_duration(speech),
            billed_seconds=speech_seconds(len(speech.audio)),
            words=part_words(part, speech),
        )


@dataclass(frozen=True)
class GeminiVoice:
    reader: ReadAloud
    voice_id: str = SPEECH_VOICE
    name: ListenVoiceName = "GEMINI"
    model: str = SPEECH_MODEL
    audio_type: str = WAV_TYPE
    extension: str = "wav"
    service: str = GEMINI_SERVICE

    def speaks(self, language: str) -> bool:
        return language in SPEECH_LANGUAGES

    async def spoken(self, parts: Sequence[NarrationPart], index: int) -> SpokenPart:
        part = parts[index]
        spoken = [
            wav_frames(await self.reader.read_aloud(sentence.text, voice=self.voice_id))
            for sentence in part.sentences
        ]
        timed = sentence_timed(part, spoken)
        return SpokenPart(
            audio=timed.audio,
            duration_seconds=timed.duration_seconds,
            billed_seconds=timed.billed_seconds,
            sentences=timed.sentences,
        )


def listen_offer(voices: Sequence[ListenVoice]) -> ListenOffer:
    languages = [code for code in ANSWER_LANGUAGES if any(voice.speaks(code) for voice in voices)]
    return ListenOffer(languages=languages, voice=voices[0].name if languages else None)


def untagged(text: str) -> str:
    return text.translate(NARRATION_TAG_BRACKETS)
