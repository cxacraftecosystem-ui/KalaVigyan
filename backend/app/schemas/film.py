from __future__ import annotations

import uuid
from collections.abc import Mapping
from datetime import date
from types import MappingProxyType
from typing import Literal, Self

from pydantic import AwareDatetime, Field, model_validator

from app.research.base import ContractModel, HttpsUrl
from app.research.blocks import BLOCK_ID_MAX_CHARS, BLOCK_ID_PATTERN
from app.research.vocabulary import AnswerLanguage

__all__ = [
    "FILM_SCENE_SECONDS",
    "FILM_SCORE_SCHEMA_VERSION",
    "SCORE_CUES_MAX",
    "SCORE_CUE_SECONDS_MAX",
    "SCORE_CUE_SECONDS_MIN",
    "SCORE_LABEL",
    "SCORE_MUSIC_SECONDS_MAX",
    "SCORE_MUSIC_SECONDS_MIN",
    "SCORE_POLL_SECONDS",
    "SCORE_POLL_SECONDS_MAX",
    "FilmOffer",
    "FilmScore",
    "FilmScoreMaking",
    "ScoreCue",
    "ScoreLabel",
    "ScoreMusic",
]

FILM_SCORE_SCHEMA_VERSION = 1
SCORE_LABEL = "AI music and sound"
SCORE_MUSIC_SECONDS_MIN = 10.0
SCORE_MUSIC_SECONDS_MAX = 300.0
SCORE_CUE_SECONDS_MIN = 0.5
SCORE_CUE_SECONDS_MAX = 30.0
SCORE_CUES_MAX = 12
SCORE_POLL_SECONDS = 5
SCORE_POLL_SECONDS_MAX = 60
FILM_SCENE_SECONDS: Mapping[str, float] = MappingProxyType({"step": 4.0, "picture": 3.0, "block": 6.0})


class ScoreMusic(ContractModel):
    audio_url: HttpsUrl
    duration_seconds: float = Field(ge=SCORE_MUSIC_SECONDS_MIN, le=SCORE_MUSIC_SECONDS_MAX)
    model: str = Field(min_length=1, max_length=120)


class ScoreCue(ContractModel):
    block_id: str = Field(min_length=1, max_length=BLOCK_ID_MAX_CHARS, pattern=BLOCK_ID_PATTERN)
    offset_seconds: float = Field(ge=0)
    audio_url: HttpsUrl
    duration_seconds: float = Field(ge=SCORE_CUE_SECONDS_MIN, le=SCORE_CUE_SECONDS_MAX)
    model: str = Field(min_length=1, max_length=120)


class ScoreLabel(ContractModel):
    text: Literal[SCORE_LABEL]
    models: list[str] = Field(min_length=1)
    generated_on: date


class FilmScore(ContractModel):
    schema_version: Literal[1]
    answer_id: uuid.UUID
    language: AnswerLanguage
    music: ScoreMusic | None
    cues: list[ScoreCue] = Field(max_length=SCORE_CUES_MAX)
    label: ScoreLabel
    url_expires_at: AwareDatetime

    @model_validator(mode="after")
    def _music_or_cues_labelled_by_their_models(self) -> Self:
        if self.music is None and not self.cues:
            raise ValueError(f"score of answer {self.answer_id} holds music or a cue")
        scenes = [cue.block_id for cue in self.cues]
        if len(set(scenes)) != len(scenes):
            raise ValueError(f"score of answer {self.answer_id} gives each scene one cue at most")
        made = [*([self.music.model] if self.music else []), *(cue.model for cue in self.cues)]
        if self.label.models != list(dict.fromkeys(made)):
            raise ValueError(
                f"score of answer {self.answer_id} names each model that made it, once, in order"
            )
        return self


class FilmScoreMaking(ContractModel):
    answer_id: uuid.UUID
    language: AnswerLanguage
    poll_after_seconds: int = Field(ge=1, le=SCORE_POLL_SECONDS_MAX)


class FilmOffer(ContractModel):
    score: bool
