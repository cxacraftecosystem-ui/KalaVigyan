from __future__ import annotations

import uuid
from itertools import pairwise
from typing import Literal, Self

from pydantic import Field, model_validator

from app.research.base import ContractModel, HttpsUrl, absent, empty
from app.research.blocks import BLOCK_ID_MAX_CHARS, BLOCK_ID_PATTERN
from app.research.vocabulary import AnswerLanguage

__all__ = [
    "LISTEN_SCHEMA_VERSION",
    "LISTEN_VOICES",
    "ListenOffer",
    "ListenScript",
    "ListenSentence",
    "ListenTrack",
    "ListenVoiceName",
    "ListenWord",
]

LISTEN_SCHEMA_VERSION = 1
LISTEN_VOICES = ("ELEVENLABS", "GEMINI")
ListenVoiceName = Literal["ELEVENLABS", "GEMINI"]


class ListenWord(ContractModel):
    sentence_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    start: float = Field(ge=0)
    end: float = Field(ge=0)

    @model_validator(mode="after")
    def _ends_after_it_starts(self) -> Self:
        if self.end < self.start or any(ch.isspace() for ch in self.text):
            raise ValueError(f"word {self.text!r} is one word that ends after it starts")
        return self


class ListenSentence(ContractModel):
    sentence_id: str = Field(min_length=1)
    start: float = Field(ge=0)
    end: float = Field(ge=0)

    @model_validator(mode="after")
    def _ends_after_it_starts(self) -> Self:
        if self.end < self.start:
            raise ValueError(f"sentence {self.sentence_id} ends after it starts")
        return self


class ListenTrack(ContractModel):
    block_id: str = Field(min_length=1, max_length=BLOCK_ID_MAX_CHARS, pattern=BLOCK_ID_PATTERN)
    audio_url: HttpsUrl
    duration_seconds: float = Field(gt=0)
    words: list[ListenWord] = Field(default_factory=list)
    sentences: list[ListenSentence] = Field(default_factory=list, exclude_if=empty)

    @model_validator(mode="after")
    def _timed_in_reading_order_within_the_audio(self) -> Self:
        if bool(self.words) == bool(self.sentences):
            raise ValueError(f"track of block {self.block_id} is timed by its words or by its sentences")
        starts = [word.start for word in self.words] or [sentence.start for sentence in self.sentences]
        if any(later < earlier for earlier, later in pairwise(starts)):
            raise ValueError(f"track of block {self.block_id} times its words in reading order")
        if any(start > self.duration_seconds for start in starts):
            raise ValueError(f"track of block {self.block_id} times its words within its audio")
        return self


class ListenScript(ContractModel):
    schema_version: Literal[1]
    answer_id: uuid.UUID
    language: AnswerLanguage
    voice: ListenVoiceName
    tracks: list[ListenTrack] = Field(min_length=1)


class ListenOffer(ContractModel):
    languages: list[AnswerLanguage]
    voice: ListenVoiceName | None = Field(default=None, exclude_if=absent)
