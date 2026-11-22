from __future__ import annotations

import uuid
from collections.abc import Mapping
from datetime import datetime
from types import MappingProxyType
from typing import Annotated, Any, Literal, Self

from pydantic import Field, TypeAdapter, ValidationError, model_validator

from app.core.errors import InvalidInput
from app.research.base import ContractModel
from app.research.citations import AnswerSentence, SourceRef
from app.research.crafts import SLUG_MAX_CHARS, CraftRef
from app.research.stream import ErrorEvent, sse_frame
from app.research.testimony import InterviewTopic
from app.research.vocabulary import AnswerLanguage

from .voice import (
    MAX_SESSION_SECONDS,
    MAX_TURNS,
    MIN_START_SECONDS,
    RELAY_AUDIO_BITS_PER_SECOND,
    RELAY_AUDIO_TYPES,
    RELAY_MAX_AUDIO_BYTES,
    RELAY_MAX_TURN_SECONDS,
    VOICE_TRANSPORTS,
    VoiceLanguageOption,
)

__all__ = [
    "ARTISAN_EVENTS",
    "ARTISAN_SPEECH_PATH_PATTERN",
    "ARTISAN_STEPS",
    "ARTISAN_TRANSCRIPT_VERSION",
    "SPEAKERS",
    "AgentConversationStarted",
    "ArtisanTranscript",
    "ConversationAvailability",
    "ConversationEnded",
    "ConversationStartRequest",
    "ConversationStarted",
    "RelayConversationStarted",
    "TranscriptTurn",
    "TranscriptWord",
    "artisan_frame",
    "artisan_speech_path",
    "parse_artisan_event",
]

ARTISAN_TRANSCRIPT_VERSION = 1
ARTISAN_STEPS = ("transcribing", "thinking", "speaking")
SPEAKERS = ("KALAVIGYAN", "ARTISAN")
UUID_TEXT = "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
ARTISAN_SPEECH_PATH_PATTERN = rf"^/api/artisan/conversations/{UUID_TEXT}/turns/{UUID_TEXT}/speech$"
TEXT_MAX = 4000
QUESTION_TEXT_MAX = 1000

Topic = InterviewTopic
Transport = Literal[*VOICE_TRANSPORTS]
Seconds = Annotated[int, Field(ge=0)]
SpeechPath = Annotated[str, Field(pattern=ARTISAN_SPEECH_PATH_PATTERN)]


class ConversationAvailability(ContractModel):
    configured: bool
    transport: Transport | None
    languages: list[VoiceLanguageOption]
    notice_version: str | None
    consent_required: bool
    remaining_seconds: Seconds | None
    crafts: list[CraftRef]

    @model_validator(mode="after")
    def _hidden_offers_nothing(self) -> Self:
        if self.configured != (self.transport is not None) or self.configured != bool(self.languages):
            raise ValueError("conversations are configured exactly when they name a transport and a language")
        if self.configured and (self.notice_version is None or not self.crafts):
            raise ValueError("configured conversations name the recording notice and the artisan's crafts")
        if not self.configured and (
            self.consent_required or self.notice_version is not None or self.crafts or self.remaining_seconds
        ):
            raise ValueError("unconfigured conversations offer nothing")
        return self


class ConversationStartRequest(ContractModel):
    craft_slug: str = Field(min_length=1, max_length=SLUG_MAX_CHARS)
    language: str = Field(min_length=2, max_length=16)
    notice_version: str = Field(min_length=1, max_length=40)


class SpokenOpening(ContractModel):
    turn_id: uuid.UUID
    text: str = Field(min_length=1, max_length=TEXT_MAX)
    speech_path: SpeechPath


class _ConversationStarted(ContractModel):
    conversation_id: uuid.UUID
    voice_session_id: uuid.UUID
    craft: CraftRef
    language: AnswerLanguage
    max_duration_seconds: int = Field(ge=MIN_START_SECONDS, le=MAX_SESSION_SECONDS)
    remaining_seconds: Seconds | None
    max_turns: int = Field(ge=1, le=MAX_TURNS)
    expires_at: datetime


class RelayConversationStarted(_ConversationStarted):
    transport: Literal["RELAY"]
    max_turn_seconds: int = Field(ge=1, le=RELAY_MAX_TURN_SECONDS)
    max_audio_bytes: int = Field(ge=1, le=RELAY_MAX_AUDIO_BYTES)
    audio_bits_per_second: int = Field(ge=1, le=RELAY_AUDIO_BITS_PER_SECOND)
    audio_types: list[str] = Field(min_length=1)
    opening: SpokenOpening

    @model_validator(mode="after")
    def _known_audio_types(self) -> Self:
        if any(kind not in RELAY_AUDIO_TYPES for kind in self.audio_types):
            raise ValueError(f"relay audio is one of {', '.join(RELAY_AUDIO_TYPES)}")
        return self


class AgentConversationStarted(_ConversationStarted):
    transport: Literal["AGENT"]
    conversation_token: str = Field(min_length=1, max_length=4096)


ConversationStarted = Annotated[
    AgentConversationStarted | RelayConversationStarted, Field(discriminator="transport")
]


class ConversationEnded(ContractModel):
    conversation_id: uuid.UUID
    ended_at: datetime
    turn_count: int = Field(ge=0, le=MAX_TURNS)
    billed_seconds: Seconds | None
    extraction: Literal["PENDING", "NONE"]


class TranscriptWord(ContractModel):
    text: str = Field(min_length=1, max_length=200)
    start: float = Field(ge=0)
    end: float = Field(ge=0)


class TranscriptTurn(ContractModel):
    id: uuid.UUID
    ordinal: int = Field(ge=0)
    speaker: Literal[*SPEAKERS]
    text: str = Field(min_length=1, max_length=TEXT_MAX)
    english: str | None = Field(default=None, max_length=TEXT_MAX)
    topic: Topic | None = None
    answer_id: uuid.UUID | None = None
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)
    words: list[TranscriptWord] | None = None
    audio_id: uuid.UUID | None = None
    scrubbed: bool = False
    continued: bool = False

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.end_ms < self.start_ms:
            raise ValueError(f"turn {self.ordinal} ends after it starts")
        if self.speaker == "KALAVIGYAN" and (self.words or self.audio_id or self.scrubbed or self.continued):
            raise ValueError("KalaVigyan's turns keep no words, audio or scrubbing")
        if self.speaker == "ARTISAN" and (self.topic or self.answer_id):
            raise ValueError("an artisan's turn has no topic or answer")
        if self.scrubbed and (self.words is not None or self.audio_id is not None):
            raise ValueError("a scrubbed turn keeps no word timings and no recording")
        return self


class ArtisanTranscript(ContractModel):
    version: Literal[1] = ARTISAN_TRANSCRIPT_VERSION
    turns: list[TranscriptTurn] = Field(default_factory=list)

    @model_validator(mode="after")
    def _numbered_in_order(self) -> Self:
        if [turn.ordinal for turn in self.turns] != list(range(len(self.turns))):
            raise ValueError("transcript turns are numbered 0, 1, 2, ... in order")
        return self

    def turn(self, turn_id: uuid.UUID) -> TranscriptTurn | None:
        return next((turn for turn in self.turns if turn.id == turn_id), None)

    def before(self, ordinal: int) -> TranscriptTurn | None:
        earlier = [t for t in self.turns if t.ordinal < ordinal and t.speaker == "KALAVIGYAN"]
        return earlier[-1] if earlier else None


class HeardTurn(ContractModel):
    turn_id: uuid.UUID
    text: str = Field(min_length=1, max_length=TEXT_MAX)
    language: AnswerLanguage
    continued: bool


class StepEvent(ContractModel):
    step: Literal[*ARTISAN_STEPS]


class ReplyEvent(ContractModel):
    turn_id: uuid.UUID
    answer_id: uuid.UUID | None
    sentences: list[AnswerSentence]
    question: str = Field(min_length=1, max_length=QUESTION_TEXT_MAX)
    english: str = Field(min_length=1, max_length=QUESTION_TEXT_MAX)
    topic: Topic
    text: str = Field(min_length=1, max_length=TEXT_MAX)
    speech_path: SpeechPath

    @model_validator(mode="after")
    def _spoken_whole(self) -> Self:
        if not self.text.endswith(self.question):
            raise ValueError("the reply speaks its question last")
        if self.answer_id is None and self.sentences:
            raise ValueError("cited sentences belong to an answer")
        return self


class ClosingEvent(ContractModel):
    turn_id: uuid.UUID
    text: str = Field(min_length=1, max_length=TEXT_MAX)
    speech_path: SpeechPath


class TurnDone(ContractModel):
    turn_id: uuid.UUID
    billed_seconds: Seconds
    remaining_seconds: Seconds | None
    session_ended: bool


ARTISAN_EVENTS: Mapping[str, TypeAdapter[Any]] = MappingProxyType(
    {
        "heard": TypeAdapter(HeardTurn),
        "status": TypeAdapter(StepEvent),
        "source": TypeAdapter(SourceRef),
        "reply": TypeAdapter(ReplyEvent),
        "closing": TypeAdapter(ClosingEvent),
        "done": TypeAdapter(TurnDone),
        "error": TypeAdapter(ErrorEvent),
    }
)


def artisan_speech_path(conversation_id: uuid.UUID, turn_id: uuid.UUID) -> str:
    return f"/api/artisan/conversations/{conversation_id}/turns/{turn_id}/speech"


def parse_artisan_event(name: str, data: Any) -> Any:
    adapter = ARTISAN_EVENTS.get(name)
    if adapter is None:
        raise InvalidInput(f"Unknown conversation turn event {name!r}")
    if isinstance(data, ContractModel):
        data = data.model_dump(mode="json", by_alias=True, exclude_unset=True)
    try:
        return adapter.validate_python(data)
    except ValidationError as exc:
        raise InvalidInput(f"The {name} event breaks the conversation turn contract: {exc}") from exc


def artisan_frame(name: str, data: Any) -> str:
    payload = parse_artisan_event(name, data)
    return sse_frame(name, payload.model_dump(mode="json", by_alias=True, exclude_unset=True))
