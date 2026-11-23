from __future__ import annotations

import logging
import uuid
from collections.abc import Mapping
from typing import Any, Literal

from pydantic import AwareDatetime, Field, ValidationError

from app.models.enums import COVERAGE_CLASSES, ENVIRONMENT_FACTORS, PLACE_ROLES
from app.research.base import ContractModel
from app.research.vocabulary import Discipline, MaterialKind, MaterialRole, ReactionKind

__all__ = [
    "CURATED_PAGE_SCHEMA_VERSION",
    "CuratedPage",
    "IndexAfter",
    "IndexCommunity",
    "IndexConflict",
    "IndexEnvironment",
    "IndexFact",
    "IndexFocal",
    "IndexMaterial",
    "IndexNativeName",
    "IndexOverview",
    "IndexPicture",
    "IndexPlace",
    "IndexPlacement",
    "IndexQuestion",
    "IndexReaction",
    "IndexSearch",
    "IndexSection",
    "IndexSpecies",
    "IndexStage",
    "IndexTerm",
    "IndexTiming",
    "IndexTool",
    "stored_curated_page",
]

logger = logging.getLogger(__name__)

CURATED_PAGE_SCHEMA_VERSION = 1

ClaimIds = list[uuid.UUID]


class IndexSearch(ContractModel):
    query: str
    site: str


class IndexTiming(ContractModel):
    text: str
    claim_id: uuid.UUID


class IndexPlace(ContractModel):
    key: str
    name: str
    kind: str
    role: Literal[*PLACE_ROLES]
    district: str | None
    district_lgd: int | None
    state: str | None
    state_lgd: int | None
    country: str
    wikidata_id: str | None
    location_id: uuid.UUID | None
    concept_id: uuid.UUID
    claim_ids: ClaimIds


class IndexCommunity(ContractModel):
    key: str
    kind: str
    name: str
    local_names: list[str]
    honours: list[str]
    place_key: str | None
    concept_id: uuid.UUID
    claim_ids: ClaimIds


class IndexAfter(ContractModel):
    text: str
    colours: list[str] = Field(default_factory=list)
    claim_id: uuid.UUID


class IndexStage(ContractModel):
    key: str
    stage_id: uuid.UUID
    concept_id: uuid.UUID
    local_name: str | None
    order: int | None
    order_claim_id: uuid.UUID | None
    duration: IndexTiming | None
    season: IndexTiming | None
    claim_ids: ClaimIds
    after: IndexAfter | None = None
    why_claim_id: uuid.UUID | None = None


class IndexAlternative(ContractModel):
    key: str
    claim_id: uuid.UUID


class IndexMaterial(ContractModel):
    key: str
    material_id: uuid.UUID
    concept_id: uuid.UUID
    name: str
    kind: MaterialKind
    role: MaterialRole
    local_names: list[str]
    botanical_name: str | None
    pubchem_cid: int | None
    claim_ids: ClaimIds
    alternatives: list[IndexAlternative] = Field(default_factory=list)


class IndexTool(ContractModel):
    key: str
    material_id: uuid.UUID
    concept_id: uuid.UUID
    name: str
    local_names: list[str]
    claim_ids: ClaimIds


class IndexSpecies(ContractModel):
    name: str
    formula: str | None


class IndexReaction(ContractModel):
    key: str
    reaction_id: uuid.UUID | None
    stage_key: str | None
    kind: ReactionKind
    reactants: list[IndexSpecies]
    products: list[IndexSpecies]
    claim_ids: ClaimIds


class IndexTerm(ContractModel):
    key: str
    term_key: str | None
    term: str
    names: list[str]
    meaning: str
    language: str | None
    script: str | None
    concept_id: uuid.UUID
    claim_ids: ClaimIds


class IndexPlacement(ContractModel):
    chapter: str
    role: str
    stage_key: str | None = None
    material_key: str | None = None


class IndexFocal(ContractModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)


class IndexPicture(ContractModel):
    key: str
    media_ref_id: uuid.UUID
    caption: str
    stage_key: str | None
    claim_ids: ClaimIds
    placement: IndexPlacement | None = None
    focal: IndexFocal | None = None
    width: int | None = None
    height: int | None = None
    stand_in: str | None = None


class IndexNativeName(ContractModel):
    text: str
    language: str
    script: str | None
    claim_id: uuid.UUID


class IndexEnvironment(ContractModel):
    factor: Literal[*ENVIRONMENT_FACTORS]
    place_key: str | None
    claim_ids: ClaimIds


class IndexFact(ContractModel):
    label: str
    value: str
    claim_ids: ClaimIds


class IndexConflict(ContractModel):
    about: str
    claim_ids: ClaimIds


class IndexQuestion(ContractModel):
    key: str
    question: str
    settled_by: str | None
    claim_ids: ClaimIds


class IndexSection(ContractModel):
    discipline: Discipline
    piece_id: uuid.UUID


class IndexOverview(ContractModel):
    lede_piece_id: uuid.UUID | None = None
    sections: list[IndexSection] = Field(default_factory=list)
    key_facts: list[IndexFact] = Field(default_factory=list)

    def piece_ids(self) -> dict[str, uuid.UUID]:
        parts: dict[str, uuid.UUID] = {section.discipline: section.piece_id for section in self.sections}
        if self.lede_piece_id is not None:
            parts["lede"] = self.lede_piece_id
        return parts


class CuratedPage(ContractModel):
    schema_version: Literal[1] = CURATED_PAGE_SCHEMA_VERSION
    craft_slug: str
    version: int = Field(ge=1)
    curated_at: AwareDatetime
    coverage: Literal[*COVERAGE_CLASSES]
    searched: list[IndexSearch]
    process_id: uuid.UUID | None
    craft_concepts: dict[str, uuid.UUID]
    overview: IndexOverview
    conflicts: list[IndexConflict]
    open_questions: list[IndexQuestion]
    places: list[IndexPlace]
    communities: list[IndexCommunity]
    stages: list[IndexStage]
    materials: list[IndexMaterial]
    tools: list[IndexTool]
    reactions: list[IndexReaction]
    glossary: list[IndexTerm]
    pictures: list[IndexPicture]
    environment: list[IndexEnvironment]
    native_names: list[IndexNativeName] = Field(default_factory=list)
    claim_order: ClaimIds = Field(default_factory=list)

    def concept_kinds(self) -> dict[uuid.UUID, str]:
        kinds = dict.fromkeys(self.craft_concepts.values(), "CRAFT")
        for kind, entries in (
            ("PLACE", self.places),
            ("COMMUNITY", self.communities),
            ("STAGE", self.stages),
            ("MATERIAL", self.materials),
            ("TOOL", self.tools),
            ("TERM", self.glossary),
        ):
            kinds.update((entry.concept_id, kind) for entry in entries)
        return kinds

    def location_ids(self) -> set[uuid.UUID]:
        return {place.location_id for place in self.places if place.location_id is not None}

    def piece_ids(self) -> dict[str, uuid.UUID]:
        return self.overview.piece_ids()


def stored_curated_page(craft_id: uuid.UUID, page: Mapping[str, Any] | None) -> CuratedPage | None:
    if page is None:
        return None
    try:
        return CuratedPage.model_validate(page)
    except ValidationError:
        logger.warning("craft %s has a curated page index that no longer meets its model", craft_id)
        return None
