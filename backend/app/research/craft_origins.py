from __future__ import annotations

import uuid
from collections.abc import Mapping
from types import MappingProxyType
from typing import Literal, Self

from pydantic import Field, model_validator

from .base import ContractModel
from .blocks import ExplainerSentence

__all__ = [
    "AI_GENERATED",
    "AI_MEDIA_KINDS",
    "DAY_PATTERN",
    "GENERATED_KINDS",
    "ORIGIN_BASES",
    "ItemOrigin",
    "PageAiMedia",
]

AI_MEDIA_KINDS = ("IMAGE", "VIDEO")
ORIGIN_BASES = ("CURATED", "STORED", "READERS")
GENERATED_KINDS = ("MODEL", "AI_IMAGE", "AI_VIDEO")
AI_GENERATED: Mapping[str, str] = MappingProxyType({"IMAGE": "AI_IMAGE", "VIDEO": "AI_VIDEO"})
DAY_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$"


class ItemOrigin(ContractModel):
    basis: Literal[*ORIGIN_BASES]
    generated: Literal[*GENERATED_KINDS] | None
    model: str | None = Field(min_length=1, max_length=120)
    generated_on: str | None = Field(pattern=DAY_PATTERN)

    @model_validator(mode="after")
    def _generated_with_its_model_and_day(self) -> Self:
        if (self.generated is None) != (self.model is None) or (self.generated is None) != (
            self.generated_on is None
        ):
            raise ValueError("a generated item names its model and day, and only a generated one")
        return self


class PageAiMedia(ContractModel):
    asset_id: uuid.UUID
    kind: Literal[*AI_MEDIA_KINDS]
    url: str = Field(pattern=r"^/api/crafts/media/[0-9a-f-]{36}$")
    mime: str = Field(min_length=1, max_length=100)
    width: int | None = Field(ge=1)
    height: int | None = Field(ge=1)
    duration_seconds: float | None = Field(gt=0)
    alt_text: str = Field(min_length=1, max_length=600)
    sentences: list[ExplainerSentence] = Field(min_length=1)
    stage_id: uuid.UUID | None
    origin: ItemOrigin

    @model_validator(mode="after")
    def _generated_media_named_so(self) -> Self:
        if self.origin.generated != AI_GENERATED[self.kind]:
            raise ValueError(f"AI {self.kind.lower()} {self.asset_id} is labelled {AI_GENERATED[self.kind]}")
        if self.kind == "VIDEO" and self.duration_seconds is None:
            raise ValueError(f"AI video {self.asset_id} gives its length")
        return self
