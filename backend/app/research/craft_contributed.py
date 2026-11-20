from __future__ import annotations

import uuid
from typing import Literal, Self

from pydantic import Field, model_validator

from app.models.enums import IMAGE_ORIGINS

from .base import ContractModel
from .blocks import ExplainerSentence, require_facts
from .image_contributions import AI_GENERATED, GENERATOR_MAX_CHARS, IMAGE_TEXT_MAX_CHARS, shown_label
from .image_intake import AVIF, JPEG, PNG, SVG, WEBP

__all__ = [
    "CONTRIBUTED_CREDIT",
    "CONTRIBUTED_MIMES",
    "CONTRIBUTED_PATH",
    "CONTRIBUTED_PER_CHAPTER_MAX",
    "ContributedPlate",
    "contributed_credit",
    "contributed_url",
]

CONTRIBUTED_CREDIT = "Contributed to KalaVigyan"
CONTRIBUTED_PATH = "/api/crafts/contributed/{id}"
CONTRIBUTED_MIMES = (PNG, JPEG, WEBP, AVIF, SVG)
CONTRIBUTED_PER_CHAPTER_MAX = 6


def contributed_credit(origin: str, made_with: str | None) -> str:
    if origin == AI_GENERATED:
        return shown_label(origin, made_with)
    return CONTRIBUTED_CREDIT


def contributed_url(contribution_id: uuid.UUID) -> str:
    return CONTRIBUTED_PATH.format(id=contribution_id)


class ContributedPlate(ContractModel):
    contribution_id: uuid.UUID
    url: str = Field(pattern=r"^/api/crafts/contributed/[0-9a-f-]{36}$")
    mime: Literal[*CONTRIBUTED_MIMES]
    width: int = Field(ge=1)
    height: int = Field(ge=1)
    origin: Literal[*IMAGE_ORIGINS]
    made_with: str | None = Field(min_length=2, max_length=GENERATOR_MAX_CHARS)
    caption: str = Field(min_length=1, max_length=IMAGE_TEXT_MAX_CHARS)
    alt_text: str = Field(min_length=1, max_length=IMAGE_TEXT_MAX_CHARS)
    credit: str = Field(min_length=1, max_length=GENERATOR_MAX_CHARS + 40)
    stage_id: uuid.UUID | None
    sentences: list[ExplainerSentence]

    @model_validator(mode="after")
    def _credited_without_a_name(self) -> Self:
        owner = f"contributed picture {self.contribution_id}"
        if self.url != contributed_url(self.contribution_id):
            raise ValueError(f"{owner} is served from its own address")
        if (self.origin == AI_GENERATED) != (self.made_with is not None):
            raise ValueError(f"{owner} names the tool it was made with exactly when an AI made it")
        if self.credit != contributed_credit(self.origin, self.made_with):
            raise ValueError(f"{owner} is credited {contributed_credit(self.origin, self.made_with)!r}")
        require_facts(owner, self.sentences)
        return self
