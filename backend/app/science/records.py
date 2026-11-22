from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass

from app.research.citations import Citation, SourceRef
from app.research.crafts import CraftRef

__all__ = [
    "CompoundRecord",
    "ConditionRecord",
    "KnownClaim",
    "MaterialRecord",
    "ProcessRecord",
    "ProcessRecords",
    "ReactionRecord",
    "ReadingRecord",
    "SpeciesRecord",
    "StageRecord",
]


@dataclass(frozen=True)
class KnownClaim:
    id: uuid.UUID
    text: str
    level: str
    citations: tuple[Citation, ...]


@dataclass(frozen=True)
class ProcessRecord:
    id: uuid.UUID
    name: str
    variant: str | None


@dataclass(frozen=True)
class StageRecord:
    id: uuid.UUID
    process_id: uuid.UUID
    ordinal: int
    name: str
    stage_type: str
    claim_ids: tuple[uuid.UUID, ...]
    ordered: bool = True


@dataclass(frozen=True)
class CompoundRecord:
    id: uuid.UUID
    name: str
    formula: str | None
    pubchem_cid: int | None
    source_id: uuid.UUID | None = None


@dataclass(frozen=True)
class MaterialRecord:
    id: uuid.UUID
    stage_id: uuid.UUID
    name: str
    kind: str
    role: str
    quantity_text: str | None
    compound: CompoundRecord | None
    claim_ids: tuple[uuid.UUID, ...]
    material_id: uuid.UUID | None = None
    concept_id: uuid.UUID | None = None


@dataclass(frozen=True)
class SpeciesRecord:
    role: str
    formula: str | None
    name: str | None
    compound_id: uuid.UUID | None


@dataclass(frozen=True)
class ReactionRecord:
    id: uuid.UUID
    stage_id: uuid.UUID
    ordinal: int
    kind: str
    label: str
    species: tuple[SpeciesRecord, ...]
    balanced: bool
    coefficients: tuple[int, ...] | None
    checker_version: str | None
    delta_h: tuple[float, uuid.UUID] | None
    citations: tuple[tuple[uuid.UUID, str], ...]


@dataclass(frozen=True)
class ReadingRecord:
    claim_id: uuid.UUID
    citation_id: str
    stated: str
    low: float | None
    high: float | None
    unit: str


@dataclass(frozen=True)
class ConditionRecord:
    owner_id: uuid.UUID
    key: str
    label: str
    quantity: str
    readings: tuple[ReadingRecord, ...]


@dataclass(frozen=True)
class ProcessRecords:
    craft: CraftRef
    processes: tuple[ProcessRecord, ...]
    stages: tuple[StageRecord, ...]
    materials: tuple[MaterialRecord, ...]
    reactions: tuple[ReactionRecord, ...]
    conditions: tuple[ConditionRecord, ...]
    claims: Mapping[uuid.UUID, KnownClaim]
    sources: Mapping[str, SourceRef]
