from __future__ import annotations

from typing import Annotated, Self

from pydantic import AfterValidator, Field, model_validator

from app.research.base import ContractModel
from app.research.colours import ColourWord
from app.research.vocabulary import MaterialKind, ReactionKind, StageType

from .fields import (
    ClaimId,
    ClaimIds,
    CommunityId,
    MaterialId,
    NameList,
    NameText,
    PlaceId,
    ReactionId,
    StageId,
    ToolId,
    distinct,
)
from .limits import AFTER_COLOURS_MAX, AFTER_TEXT_MAX_CHARS
from .vocabulary import CuratedMaterialRole, GroupKind, PlaceKind, PlaceRole

__all__ = [
    "WIKIDATA_PATTERN",
    "After",
    "Community",
    "Material",
    "MaterialAlternative",
    "MaterialUse",
    "Place",
    "Reaction",
    "Species",
    "Stage",
    "Timing",
    "Tool",
    "ToolUse",
]

WIKIDATA_PATTERN = r"^Q[1-9]\d*$"


class Place(ContractModel):
    id: PlaceId
    name: NameText
    kind: PlaceKind
    district: str | None = Field(default=None, min_length=1, max_length=120)
    state: str | None = Field(default=None, min_length=1, max_length=120)
    country: str = Field(min_length=1, max_length=120)
    wikidata: str | None = Field(default=None, pattern=WIKIDATA_PATTERN)
    role: PlaceRole
    claim_ids: ClaimIds


class Community(ContractModel):
    id: CommunityId
    kind: GroupKind
    name: NameText
    local_names: NameList = Field(default_factory=list)
    honours: NameList = Field(default_factory=list)
    place_id: PlaceId | None = None
    claim_ids: ClaimIds

    @model_validator(mode="after")
    def _honours_only_for_people(self) -> Self:
        if self.honours and self.kind != "PERSON":
            raise ValueError(f"{self.id} lists honours, which only a PERSON carries")
        return self


class Timing(ContractModel):
    text: str = Field(min_length=1, max_length=200)
    claim_id: ClaimId


class MaterialUse(ContractModel):
    material_id: MaterialId
    claim_id: ClaimId


class ToolUse(ContractModel):
    tool_id: ToolId
    claim_id: ClaimId


class After(ContractModel):
    text: str = Field(min_length=1, max_length=AFTER_TEXT_MAX_CHARS)
    colours: Annotated[list[ColourWord], Field(max_length=AFTER_COLOURS_MAX), AfterValidator(distinct)] = (
        Field(default_factory=list)
    )
    claim_id: ClaimId


class Stage(ContractModel):
    id: StageId
    name: NameText
    local_name: str | None = Field(default=None, min_length=1, max_length=300)
    stage_type: StageType
    order: int | None = Field(default=None, ge=1)
    order_claim_id: ClaimId | None = None
    duration: Timing | None = None
    season: Timing | None = None
    materials: list[MaterialUse] = Field(default_factory=list)
    tools: list[ToolUse] = Field(default_factory=list)
    claim_ids: ClaimIds
    after: After | None = None
    why_claim_id: ClaimId | None = None

    @model_validator(mode="after")
    def _order_rests_on_a_claim(self) -> Self:
        if (self.order is None) != (self.order_claim_id is None):
            raise ValueError(f"stage {self.id} gives order and orderClaimId together, or neither")
        return self


class MaterialAlternative(ContractModel):
    material_id: MaterialId
    claim_id: ClaimId


class Material(ContractModel):
    id: MaterialId
    name: NameText
    kind: MaterialKind
    role: CuratedMaterialRole
    local_names: NameList = Field(default_factory=list)
    botanical_name: str | None = Field(default=None, min_length=1, max_length=200)
    pubchem_cid: int | None = Field(default=None, ge=1)
    claim_ids: ClaimIds
    alternatives: list[MaterialAlternative] = Field(default_factory=list)


class Tool(ContractModel):
    id: ToolId
    name: NameText
    local_names: NameList = Field(default_factory=list)
    claim_ids: ClaimIds


class Species(ContractModel):
    name: NameText
    formula: str | None = Field(default=None, min_length=1, max_length=100)


class Reaction(ContractModel):
    id: ReactionId
    kind: ReactionKind
    stage_id: StageId | None = None
    reactants: list[Species] = Field(min_length=1)
    products: list[Species] = Field(min_length=1)
    claim_ids: ClaimIds
