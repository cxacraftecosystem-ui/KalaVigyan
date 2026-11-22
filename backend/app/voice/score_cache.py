from __future__ import annotations

import hashlib
import logging
import uuid
from typing import Literal

from pydantic import AwareDatetime, Field, ValidationError

from app.research.base import ContractModel
from app.research.blocks import BLOCK_ID_MAX_CHARS, BLOCK_ID_PATTERN
from app.research.vocabulary import AnswerLanguage
from app.schemas.film import (
    SCORE_CUE_SECONDS_MAX,
    SCORE_CUE_SECONDS_MIN,
    SCORE_CUES_MAX,
    SCORE_MUSIC_SECONDS_MAX,
    SCORE_MUSIC_SECONDS_MIN,
)
from app.services.naming import score_key, score_manifest_key

from .narration_cache import NarrationObjects
from .score_prompts import SCORE_PROMPT_VERSION

__all__ = [
    "CLIP_LEAF",
    "UNNAMED_LEAF",
    "ScoreClip",
    "ScoreManifest",
    "ScoredCue",
    "ScoredMusic",
    "score_cache_id",
    "store_clip",
    "store_score",
    "stored_clip",
    "stored_score",
]

logger = logging.getLogger(__name__)

CLIP_LEAF = "clip.json"
UNNAMED_LEAF = "unnamed.json"
MANIFEST_TYPE = "application/json"
HEX_64 = r"^[0-9a-f]{64}$"
ScoreTask = Literal["MUSIC", "SOUND_EFFECT"]


class ScoreClip(ContractModel):
    schema_version: Literal[1]
    cache_id: str = Field(pattern=HEX_64)
    task: ScoreTask
    model: str = Field(min_length=1, max_length=120)
    duration_seconds: float = Field(gt=0)
    key: str = Field(min_length=1)


class ScoredMusic(ContractModel):
    key: str = Field(min_length=1)
    duration_seconds: float = Field(ge=SCORE_MUSIC_SECONDS_MIN, le=SCORE_MUSIC_SECONDS_MAX)
    model: str = Field(min_length=1, max_length=120)


class ScoredCue(ContractModel):
    block_id: str = Field(min_length=1, max_length=BLOCK_ID_MAX_CHARS, pattern=BLOCK_ID_PATTERN)
    offset_seconds: float = Field(ge=0)
    key: str = Field(min_length=1)
    duration_seconds: float = Field(ge=SCORE_CUE_SECONDS_MIN, le=SCORE_CUE_SECONDS_MAX)
    model: str = Field(min_length=1, max_length=120)


class ScoreManifest(ContractModel):
    schema_version: Literal[1]
    answer_id: uuid.UUID
    language: AnswerLanguage
    scenes_hash: str = Field(pattern=HEX_64)
    music: ScoredMusic | None
    cues: list[ScoredCue] = Field(max_length=SCORE_CUES_MAX)
    created_at: AwareDatetime


def score_cache_id(task: str, model: str, prompt: str, seconds: float) -> str:
    parts = ("kalavigyan-score", SCORE_PROMPT_VERSION, task, model, prompt, f"{seconds:g}")
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


async def stored_score(
    objects: NarrationObjects, answer_id: uuid.UUID, language: str
) -> ScoreManifest | None:
    raw = await objects.get(score_manifest_key(answer_id, language))
    if raw is None:
        return None
    try:
        manifest = ScoreManifest.model_validate_json(raw)
    except ValidationError as error:
        logger.error(
            "score of answer %s in %s is off its stored shape and is made again: %s",
            answer_id,
            language,
            error,
        )
        return None
    if manifest.answer_id != answer_id or manifest.language != language:
        logger.error("score of answer %s in %s holds another score and is made again", answer_id, language)
        return None
    return manifest


async def store_score(objects: NarrationObjects, manifest: ScoreManifest) -> None:
    body = manifest.model_dump_json(by_alias=True).encode("utf-8")
    key = score_manifest_key(manifest.answer_id, manifest.language)
    await objects.put(key, body, content_type=MANIFEST_TYPE)


async def stored_clip(objects: NarrationObjects, cache_id: str) -> ScoreClip | None:
    raw = await objects.get(score_key(cache_id, CLIP_LEAF))
    if raw is None:
        return None
    try:
        clip = ScoreClip.model_validate_json(raw)
    except ValidationError as error:
        logger.error("score clip %s is off its stored shape and is made again: %s", cache_id, error)
        return None
    if clip.cache_id != cache_id:
        logger.error("score clip %s holds the record of %s and is made again", cache_id, clip.cache_id)
        return None
    return clip


async def store_clip(objects: NarrationObjects, clip: ScoreClip) -> None:
    body = clip.model_dump_json(by_alias=True).encode("utf-8")
    await objects.put(score_key(clip.cache_id, CLIP_LEAF), body, content_type=MANIFEST_TYPE)
