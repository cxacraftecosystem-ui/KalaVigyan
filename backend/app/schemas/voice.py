from __future__ import annotations

import uuid
from collections.abc import Mapping
from datetime import datetime
from types import MappingProxyType
from typing import Annotated, Any, Literal, Self

from pydantic import Field, TypeAdapter, ValidationError, model_validator

from app.core.errors import InvalidInput
from app.research.base import ContractModel
from app.research.citations import AnswerSentence, SourceRef, cited_source_ids
from app.research.crafts import SLUG_MAX_CHARS, CraftRef
from app.research.stream import ErrorEvent, StatusEvent, sse_frame
from app.research.vocabulary import AnswerLanguage, TextDirection

__all__ = [
    "CLIENT_TOOL_NAMES",
    "MAX_SESSION_SECONDS",
    "MAX_SPOKEN_WORDS",
    "MAX_TURNS",
    "MIN_START_SECONDS",
    "RELAY_AUDIO_BITS_PER_SECOND",
    "RELAY_AUDIO_TYPES",
    "RELAY_EVENTS",
    "RELAY_MAX_AUDIO_BYTES",
    "RELAY_MAX_TURN_SECONDS",
    "RELAY_MAX_WAV_BYTES",
    "SPEECH_PATH_PATTERN",
    "TRANSCRIPT_RETENTION_DAYS",
    "VOICE_MODES",
    "VOICE_TRANSPORTS",
    "AgentSessionStarted",
    "ClientToolCall",
    "HeardEvent",
    "RelaySessionStarted",
    "SpokenEvent",
    "VoiceAvailability",
    "VoiceLanguageOption",
    "VoiceSentenceEvent",
    "VoiceSessionEnded",
    "VoiceSessionRequest",
    "VoiceSessionStarted",
    "VoiceTranscript",
    "VoiceTurnDone",
    "VoiceTurnView",
    "parse_relay_event",
    "relay_frame",
    "speech_path",
]

VOICE_MODES = ("VERIFIED", "HYBRID")
VOICE_TRANSPORTS = ("AGENT", "RELAY")
MAX_SESSION_SECONDS = 600
MAX_TURNS = 40
MAX_SPOKEN_WORDS = 60
MIN_START_SECONDS = 30
TRANSCRIPT_RETENTION_DAYS = 30
RELAY_MAX_TURN_SECONDS = 60
RELAY_AUDIO_BITS_PER_SECOND = 32_000
RELAY_MAX_AUDIO_BYTES = RELAY_MAX_TURN_SECONDS * RELAY_AUDIO_BITS_PER_SECOND // 8 * 5 // 4
RELAY_MAX_WAV_BYTES = 4 * 1024 * 1024
RELAY_AUDIO_TYPES = ("audio/webm", "audio/ogg", "audio/mp4", "audio/wav")
CLIENT_TOOL_NAMES = ("show_on_map", "open_stage", "show_sources", "offer_image")
UUID_TEXT = "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
SPEECH_PATH_PATTERN = rf"^/api/voice/session/{UUID_TEXT}/turns/{UUID_TEXT}/speech$"

VoiceLanguage = AnswerLanguage
VoiceMode = Literal[*VOICE_MODES]
VoiceTransport = Literal[*VOICE_TRANSPORTS]
Seconds = Annotated[int, Field(ge=0)]


class VoiceLanguageOption(ContractModel):
    code: VoiceLanguage
    label: str = Field(min_length=1)
    autonym: str = Field(min_length=1)
    script: str = Field(pattern=r"^[A-Z][a-z]{3}$")
    direction: TextDirection


class VoiceAvailability(ContractModel):
    configured: bool
    transport: VoiceTransport | None
    languages: list[VoiceLanguageOption]
    notice_version: str | None
    consent_required: bool
    remaining_seconds: Seconds | None

    @model_validator(mode="after")
    def _hidden_voice_offers_nothing(self) -> Self:
        if self.configured != (self.transport is not None) or self.configured != bool(self.languages):
            raise ValueError("voice is configured exactly when it names a transport and a language")
        if self.configured and self.notice_version is None:
            raise ValueError("configured voice names the voice notice version")
        if not self.configured and (self.consent_required or self.notice_version is not None):
            raise ValueError("unconfigured voice asks for nothing")
        return self


class VoiceSessionRequest(ContractModel):
    craft_slug: str | None = Field(default=None, min_length=1, max_length=SLUG_MAX_CHARS)
    mode: VoiceMode = "HYBRID"
    language: VoiceLanguage = "en"


class _SessionStarted(ContractModel):
    voice_session_id: uuid.UUID
    mode: VoiceMode
    language: VoiceLanguage
    craft: CraftRef | None
    max_duration_seconds: int = Field(ge=MIN_START_SECONDS, le=MAX_SESSION_SECONDS)
    remaining_seconds: Seconds | None
    max_turns: int = Field(ge=1, le=MAX_TURNS)
    expires_at: datetime


class AgentSessionStarted(_SessionStarted):
    transport: Literal["AGENT"]
    conversation_token: str = Field(min_length=1, max_length=4096)


class RelaySessionStarted(_SessionStarted):
    transport: Literal["RELAY"]
    max_turn_seconds: int = Field(ge=1, le=RELAY_MAX_TURN_SECONDS)
    max_audio_bytes: int = Field(ge=1, le=RELAY_MAX_AUDIO_BYTES)
    audio_bits_per_second: int = Field(ge=1, le=RELAY_AUDIO_BITS_PER_SECOND)
    audio_types: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def _known_audio_types(self) -> Self:
        if any(kind not in RELAY_AUDIO_TYPES for kind in self.audio_types):
            raise ValueError(f"relay audio is one of {', '.join(RELAY_AUDIO_TYPES)}")
        return self


VoiceSessionStarted = Annotated[AgentSessionStarted | RelaySessionStarted, Field(discriminator="transport")]


class VoiceSessionEnded(ContractModel):
    voice_session_id: uuid.UUID
    ended_at: datetime
    turn_count: int = Field(ge=0, le=MAX_TURNS)
    reserved_seconds: Seconds
    billed_seconds: Seconds | None


class _SlugParameters(ContractModel):
    craft_slug: str = Field(min_length=1, max_length=SLUG_MAX_CHARS)


class _StageParameters(ContractModel):
    stage_id: uuid.UUID


class _AnswerParameters(ContractModel):
    answer_id: uuid.UUID


class ShowOnMap(ContractModel):
    name: Literal["show_on_map"]
    parameters: _SlugParameters


class OpenStage(ContractModel):
    name: Literal["open_stage"]
    parameters: _StageParameters


class ShowSources(ContractModel):
    name: Literal["show_sources"]
    parameters: _AnswerParameters


class OfferImage(ContractModel):
    name: Literal["offer_image"]
    parameters: _StageParameters


ClientToolCall = Annotated[ShowOnMap | OpenStage | ShowSources | OfferImage, Field(discriminator="name")]


class VoiceTurnView(ContractModel):
    turn_id: uuid.UUID
    ordinal: int = Field(ge=1, le=MAX_TURNS)
    heard: str = Field(min_length=1, max_length=2000)
    answer_id: uuid.UUID | None
    sentences: list[AnswerSentence]
    spoken: str = Field(min_length=1)
    actions: list[ClientToolCall]

    @model_validator(mode="after")
    def _spoken_reply_says_the_cited_sentences(self) -> Self:
        _check_spoken(self.spoken)
        position = 0
        for sentence in self.sentences:
            found = self.spoken.find(sentence.text, position)
            if found < 0:
                raise ValueError(f"turn {self.ordinal} speaks sentence {sentence.id} word for word, in order")
            position = found + len(sentence.text)
        if self.answer_id is None and self.sentences:
            raise ValueError("cited sentences belong to an answer")
        return self


class VoiceTranscript(ContractModel):
    voice_session_id: uuid.UUID
    language: VoiceLanguage
    mode: VoiceMode
    craft: CraftRef | None
    retention_until: datetime
    turns: list[VoiceTurnView]
    sources: list[SourceRef]

    @model_validator(mode="after")
    def _turns_in_order_and_sources_cited(self) -> Self:
        if [turn.ordinal for turn in self.turns] != list(range(1, len(self.turns) + 1)):
            raise ValueError("turns are numbered 1, 2, 3, ... in order")
        cited = cited_source_ids(sentence for turn in self.turns for sentence in turn.sentences)
        if [source.id for source in self.sources] != cited:
            raise ValueError("sources lists every cited source once, in order of first citation")
        return self


class HeardEvent(ContractModel):
    text: str = Field(min_length=1, max_length=2000)
    language: VoiceLanguage


class VoiceSentenceEvent(ContractModel):
    sentence: AnswerSentence


class SpokenEvent(ContractModel):
    text: str = Field(min_length=1)
    speech_path: str = Field(pattern=SPEECH_PATH_PATTERN)

    @model_validator(mode="after")
    def _short_reply(self) -> Self:
        _check_spoken(self.text)
        return self


class VoiceTurnDone(ContractModel):
    turn_id: uuid.UUID
    answer_id: uuid.UUID | None
    billed_seconds: Seconds
    remaining_seconds: Seconds | None
    session_ended: bool


RELAY_EVENTS: Mapping[str, TypeAdapter[Any]] = MappingProxyType(
    {
        "heard": TypeAdapter(HeardEvent),
        "status": TypeAdapter(StatusEvent),
        "source": TypeAdapter(SourceRef),
        "sentence": TypeAdapter(VoiceSentenceEvent),
        "action": TypeAdapter(ClientToolCall),
        "spoken": TypeAdapter(SpokenEvent),
        "error": TypeAdapter(ErrorEvent),
        "done": TypeAdapter(VoiceTurnDone),
    }
)


def speech_path(voice_session_id: uuid.UUID, turn_id: uuid.UUID) -> str:
    return f"/api/voice/session/{voice_session_id}/turns/{turn_id}/speech"


def parse_relay_event(name: str, data: Any) -> Any:
    adapter = RELAY_EVENTS.get(name)
    if adapter is None:
        raise InvalidInput(f"Unknown voice turn event {name!r}")
    if isinstance(data, ContractModel):
        data = data.model_dump(mode="json", by_alias=True, exclude_unset=True)
    try:
        return adapter.validate_python(data)
    except ValidationError as exc:
        raise InvalidInput(f"The {name} event breaks the voice turn contract: {exc}") from exc


def relay_frame(name: str, data: Any) -> str:
    payload = parse_relay_event(name, data)
    return sse_frame(name, payload.model_dump(mode="json", by_alias=True, exclude_unset=True))


def _check_spoken(text: str) -> None:
    if len(text.split()) > MAX_SPOKEN_WORDS:
        raise ValueError(f"a spoken reply is at most {MAX_SPOKEN_WORDS} words")
