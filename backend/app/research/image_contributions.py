from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal, Self

from pydantic import Field, model_validator

from app.models.enums import IMAGE_CONTRIBUTION_STATUSES, IMAGE_ORIGINS
from app.models.open_work import TASK_KEY_COLUMN_CHARS

from .base import ContractModel
from .crafts import SLUG_MAX_CHARS
from .image_screens import ScreenSummary

__all__ = [
    "AI_GENERATED",
    "BATCH_PICTURES_MAX",
    "IMAGE_TERMS_VERSION",
    "ORIGIN_LABELS",
    "PICTURE_SLOTS",
    "BatchPicture",
    "ImageBatch",
    "ImageContributionStatus",
    "ImageContributionView",
    "ImageDeclaration",
    "ImageOrigin",
    "ImageQueue",
    "PictureSlot",
    "PictureTarget",
    "SharedDeclaration",
    "declaration_problem",
    "shown_label",
    "target_problem",
]

IMAGE_TERMS_VERSION = "2026-11-19"
IMAGE_TERMS_VERSIONS = (IMAGE_TERMS_VERSION,)
IMAGE_TEXT_MAX_CHARS = 300
GENERATOR_MAX_CHARS = 120
PROMPT_MAX_CHARS = 4000
REVIEW_NOTE_MAX_CHARS = 500
CLAIMS_MAX = 20
BATCH_PICTURES_MAX = 10
AI_GENERATED = "AI_GENERATED"
PICTURE_SLOTS = ("MASTHEAD", "RECORD")
ORIGIN_LABELS = {
    "PHOTOGRAPH": "Photograph",
    "DRAWING": "Drawing",
    AI_GENERATED: "Illustration, made with {tool}",
}
AI_NEEDS = "An AI-made image names its tool and model, its prompt and the facts it shows"
ONLY_AI_CARRIES = "Only an AI-made image carries a tool and a prompt"
EACH_FACT_ONCE = "Each fact is named once"
ONE_TARGET = "A picture shows one stage, one material or one picture slot, not several"

ImageOrigin = Literal[*IMAGE_ORIGINS]
ImageContributionStatus = Literal[*IMAGE_CONTRIBUTION_STATUSES]
TermsVersion = Literal[*IMAGE_TERMS_VERSIONS]
PictureSlot = Literal[*PICTURE_SLOTS]


def shown_label(origin: str, generator: str | None) -> str:
    return ORIGIN_LABELS[origin].format(tool=generator or "")


def declaration_problem(
    origin: str, generator: str | None, prompt: str | None, claim_ids: list[uuid.UUID]
) -> str | None:
    if origin == AI_GENERATED and not (generator and prompt and claim_ids):
        return AI_NEEDS
    if origin != AI_GENERATED and (generator or prompt):
        return ONLY_AI_CARRIES
    if len(set(claim_ids)) != len(claim_ids):
        return EACH_FACT_ONCE
    return None


def target_problem(stage_id: uuid.UUID | None, material_id: uuid.UUID | None, slot: str | None) -> str | None:
    return ONE_TARGET if sum(target is not None for target in (stage_id, material_id, slot)) > 1 else None


class PictureTarget(ContractModel):
    stage_id: uuid.UUID | None = None
    material_id: uuid.UUID | None = None
    slot: PictureSlot | None = None
    task_key: str | None = Field(default=None, min_length=1, max_length=TASK_KEY_COLUMN_CHARS)

    @model_validator(mode="after")
    def _one_target(self) -> Self:
        problem = target_problem(self.stage_id, self.material_id, self.slot)
        if problem:
            raise ValueError(problem)
        return self


class ImageDeclaration(PictureTarget):
    craft_slug: str = Field(min_length=1, max_length=SLUG_MAX_CHARS)
    claim_ids: list[uuid.UUID] = Field(default_factory=list, max_length=CLAIMS_MAX)
    origin: ImageOrigin
    generator: str | None = Field(default=None, min_length=2, max_length=GENERATOR_MAX_CHARS)
    prompt: str | None = Field(default=None, min_length=1, max_length=PROMPT_MAX_CHARS)
    caption: str = Field(min_length=3, max_length=IMAGE_TEXT_MAX_CHARS)
    alt_text: str = Field(min_length=3, max_length=IMAGE_TEXT_MAX_CHARS)
    rights_confirmed: Literal[True]
    terms_version: TermsVersion

    @model_validator(mode="after")
    def _origin_is_declared(self) -> Self:
        problem = declaration_problem(self.origin, self.generator, self.prompt, self.claim_ids)
        if problem:
            raise ValueError(problem)
        return self


class SharedDeclaration(ContractModel):
    origin: ImageOrigin
    generator: str | None = Field(default=None, min_length=2, max_length=GENERATOR_MAX_CHARS)
    rights_confirmed: Literal[True]
    terms_version: TermsVersion


class BatchPicture(PictureTarget):
    claim_ids: list[uuid.UUID] = Field(default_factory=list, max_length=CLAIMS_MAX)
    prompt: str | None = Field(default=None, min_length=1, max_length=PROMPT_MAX_CHARS)
    caption: str = Field(min_length=3, max_length=IMAGE_TEXT_MAX_CHARS)
    alt_text: str = Field(min_length=3, max_length=IMAGE_TEXT_MAX_CHARS)

    def declared(self, craft_slug: str, shared: SharedDeclaration) -> ImageDeclaration:
        return ImageDeclaration(
            craft_slug=craft_slug,
            **shared.model_dump(by_alias=False),
            **self.model_dump(by_alias=False),
        )


class ImageBatch(SharedDeclaration):
    craft_slug: str = Field(min_length=1, max_length=SLUG_MAX_CHARS)
    pictures: list[BatchPicture] = Field(min_length=1, max_length=BATCH_PICTURES_MAX)

    @model_validator(mode="after")
    def _each_picture_is_declared(self) -> Self:
        for position, picture in enumerate(self.pictures, start=1):
            problem = declaration_problem(self.origin, self.generator, picture.prompt, picture.claim_ids)
            if problem:
                raise ValueError(f"Picture {position}: {problem}")
        return self

    def shared(self) -> SharedDeclaration:
        return SharedDeclaration(
            origin=self.origin,
            generator=self.generator,
            rights_confirmed=self.rights_confirmed,
            terms_version=self.terms_version,
        )

    def declarations(self) -> list[ImageDeclaration]:
        shared = self.shared()
        return [picture.declared(self.craft_slug, shared) for picture in self.pictures]


class ImageContributionView(ContractModel):
    id: uuid.UUID
    craft_slug: str
    craft_name: str
    stage_id: uuid.UUID | None
    material_id: uuid.UUID | None
    slot: PictureSlot | None
    task_key: str | None
    claim_ids: list[uuid.UUID]
    origin: ImageOrigin
    label: str
    generator: str | None
    prompt: str | None
    caption: str
    alt_text: str
    status: ImageContributionStatus
    ai_marked: bool
    mime: str | None
    width: int | None
    height: int | None
    file_url: str | None
    screen: ScreenSummary | None
    created_at: datetime
    reviewed_at: datetime | None
    review_note: str | None


class ImageQueue(ContractModel):
    status: ImageContributionStatus
    items: list[ImageContributionView]
