from __future__ import annotations

import logging
from datetime import datetime
from typing import Literal, Protocol, Self

from pydantic import Field, ValidationError, model_validator

from app.research.base import ContractModel, empty
from app.research.vocabulary import AnswerLanguage
from app.schemas.listen import ListenSentence, ListenWord
from app.services.naming import narration_key
from app.services.object_store import PresignedGet

__all__ = [
    "AUDIO_TYPE",
    "MANIFEST_LEAF",
    "NarratedPart",
    "NarrationManifest",
    "NarrationObjects",
    "store_manifest",
    "stored_manifest",
]

logger = logging.getLogger(__name__)

AUDIO_TYPE = "audio/mpeg"
MANIFEST_TYPE = "application/json"
MANIFEST_LEAF = "narration.json"


class NarrationObjects(Protocol):
    async def get(self, key: str) -> bytes | None: ...

    async def put(self, key: str, body: bytes, *, content_type: str) -> None: ...

    def presigned_get(self, key: str, *, disposition: str, seconds: int, now: datetime) -> PresignedGet: ...


class NarratedPart(ContractModel):
    key: str = Field(min_length=1)
    language: AnswerLanguage
    duration_seconds: float = Field(gt=0)
    words: list[ListenWord] = Field(default_factory=list)
    sentences: list[ListenSentence] = Field(default_factory=list, exclude_if=empty)

    @model_validator(mode="after")
    def _timed_by_words_or_by_sentences(self) -> Self:
        if bool(self.words) == bool(self.sentences):
            raise ValueError(f"narrated part {self.key} is timed by its words or by its sentences")
        return self


class NarrationManifest(ContractModel):
    schema_version: Literal[1]
    cache_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    model: str = Field(min_length=1)
    voice_id: str = Field(min_length=1)
    language: AnswerLanguage
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    parts: list[NarratedPart] = Field(min_length=1)


async def stored_manifest(objects: NarrationObjects, cache_id: str) -> NarrationManifest | None:
    raw = await objects.get(narration_key(cache_id, MANIFEST_LEAF))
    if raw is None:
        return None
    try:
        manifest = NarrationManifest.model_validate_json(raw)
    except ValidationError as error:
        logger.error("narration %s is off its stored shape and is made again: %s", cache_id, error)
        return None
    if manifest.cache_id != cache_id:
        logger.error("narration %s holds the manifest of %s and is made again", cache_id, manifest.cache_id)
        return None
    return manifest


async def store_manifest(objects: NarrationObjects, manifest: NarrationManifest) -> None:
    body = manifest.model_dump_json(by_alias=True).encode("utf-8")
    await objects.put(narration_key(manifest.cache_id, MANIFEST_LEAF), body, content_type=MANIFEST_TYPE)
