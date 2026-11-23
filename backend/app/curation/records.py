from __future__ import annotations

from typing import Annotated, Self

from pydantic import AfterValidator, Field, model_validator

from app.research.base import ContractModel, HttpsUrl, PartialDate
from app.research.chapter_keys import PLACEMENT_NEEDS_MATERIAL, PLACEMENT_NEEDS_STAGE

from .fields import (
    ClaimId,
    ClaimIds,
    MaterialId,
    NameList,
    NameText,
    PictureId,
    PlaceId,
    StageId,
    TermId,
    distinct,
)
from .limits import YEAR_MAX, YEAR_MIN
from .parts import LANGUAGE_PATTERN
from .vocabulary import ChapterKey, EnvironmentFactor, PictureRole

__all__ = [
    "SCRIPT_PATTERN",
    "EnvironmentLink",
    "Focal",
    "GiRecord",
    "Market",
    "NativeName",
    "Picture",
    "Placement",
    "Price",
    "Term",
    "Workforce",
]

SCRIPT_PATTERN = r"^[A-Z][a-z]{3}$"


class EnvironmentLink(ContractModel):
    factor: EnvironmentFactor
    place_id: PlaceId | None = None
    claim_ids: ClaimIds


class GiRecord(ContractModel):
    application_number: str | None = Field(default=None, min_length=1, max_length=40)
    certificate_number: str | None = Field(default=None, min_length=1, max_length=40)
    filed_on: PartialDate | None = None
    registered_on: PartialDate | None = None
    journal_issue: str | None = Field(default=None, min_length=1, max_length=100)
    proprietors: NameList = Field(default_factory=list)
    authorised_user_count: int | None = Field(default=None, ge=0)
    claim_ids: ClaimIds


class Price(ContractModel):
    claim_id: ClaimId
    date: PartialDate
    place_id: PlaceId


class Workforce(ContractModel):
    claim_id: ClaimId
    year: int = Field(ge=YEAR_MIN, le=YEAR_MAX)


class Market(ContractModel):
    gi: GiRecord | None = None
    prices: list[Price] = Field(default_factory=list)
    workforce: list[Workforce] = Field(default_factory=list)
    imitation: Annotated[list[ClaimId], AfterValidator(distinct)] = Field(default_factory=list)


class Term(ContractModel):
    id: TermId
    term: NameText
    meaning: str = Field(min_length=1, max_length=600)
    language: str | None = Field(default=None, pattern=LANGUAGE_PATTERN)
    script: str | None = Field(default=None, pattern=SCRIPT_PATTERN)
    claim_ids: ClaimIds


class NativeName(ContractModel):
    text: NameText
    language: str = Field(pattern=LANGUAGE_PATTERN)
    script: str | None = Field(default=None, pattern=SCRIPT_PATTERN)
    claim_id: ClaimId


class Placement(ContractModel):
    chapter: ChapterKey
    role: PictureRole
    stage_id: StageId | None = None
    material_id: MaterialId | None = None

    @model_validator(mode="after")
    def _names_its_stage_or_material(self) -> Self:
        if (self.role in PLACEMENT_NEEDS_STAGE) != (self.stage_id is not None):
            raise ValueError(f"a {self.role} placement names a stageId only when its role needs a stage")
        if (self.role in PLACEMENT_NEEDS_MATERIAL) != (self.material_id is not None):
            raise ValueError(
                f"a {self.role} placement names a materialId only when its role needs a material"
            )
        return self


class Focal(ContractModel):
    x: float = Field(ge=0, lt=1)
    y: float = Field(ge=0, lt=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def _inside_the_picture(self) -> Self:
        if self.x + self.width > 1 or self.y + self.height > 1:
            raise ValueError(
                "the focal box ends outside the picture (x + width and y + height are at most 1)"
            )
        return self


class Picture(ContractModel):
    id: PictureId
    url: HttpsUrl
    page_url: HttpsUrl
    author: NameText
    licence: str = Field(min_length=1, max_length=200)
    licence_url: HttpsUrl | None = None
    caption: NameText
    claim_ids: Annotated[list[ClaimId], AfterValidator(distinct)] = Field(default_factory=list)
    stage_id: StageId | None = None
    placement: Placement | None = None
    focal: Focal | None = None
    width: int | None = Field(default=None, ge=1)
    height: int | None = Field(default=None, ge=1)
    stand_in: str | None = Field(default=None, min_length=1, max_length=300)

    @model_validator(mode="after")
    def _shows_a_claim_or_stage(self) -> Self:
        if not self.claim_ids and self.stage_id is None:
            raise ValueError(f"picture {self.id} names the claim or stage it shows")
        if (self.width is None) != (self.height is None):
            raise ValueError(f"picture {self.id} gives its width and height together, or neither")
        return self
