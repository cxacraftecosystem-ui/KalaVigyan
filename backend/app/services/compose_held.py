from __future__ import annotations

import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from app.research.page_proposals import PageComponent

__all__ = [
    "About",
    "Composition",
    "CraftHeld",
    "HeldAfter",
    "HeldCompound",
    "HeldFact",
    "HeldMaterial",
    "HeldReaction",
    "HeldSpecies",
    "HeldStage",
    "HeldTiming",
    "NamedCompound",
    "composed",
    "refused",
]


@dataclass(frozen=True)
class HeldFact:
    id: uuid.UUID
    text: str


@dataclass(frozen=True)
class HeldTiming:
    text: str
    claim_id: uuid.UUID


@dataclass(frozen=True)
class HeldAfter:
    text: str
    colours: tuple[str, ...]
    claim_id: uuid.UUID
    tokens: tuple[str, ...] = ()


@dataclass(frozen=True)
class HeldStage:
    key: str
    name: str
    stage_type: str
    claim_ids: tuple[uuid.UUID, ...] = ()
    material_keys: tuple[str, ...] = ()
    after: HeldAfter | None = None
    duration: HeldTiming | None = None


@dataclass(frozen=True)
class HeldCompound:
    cid: int
    name: str
    formula: str | None = None


@dataclass(frozen=True)
class NamedCompound:
    compound: HeldCompound
    claim_ids: tuple[uuid.UUID, ...] = ()


@dataclass(frozen=True)
class HeldMaterial:
    key: str
    name: str
    kind: str
    claim_ids: tuple[uuid.UUID, ...] = ()
    compound: HeldCompound | None = None
    tokens: tuple[str, ...] = ()
    alternatives: tuple[tuple[str, uuid.UUID], ...] = ()
    role: str | None = None
    local_names: tuple[str, ...] = ()
    botanical_name: str | None = None


@dataclass(frozen=True)
class HeldSpecies:
    name: str
    formula: str | None = None


@dataclass(frozen=True)
class HeldReaction:
    key: str
    kind: str
    stage_key: str | None
    reactants: tuple[HeldSpecies, ...]
    products: tuple[HeldSpecies, ...]
    claim_ids: tuple[uuid.UUID, ...] = ()
    coefficients: tuple[int, ...] | None = None

    def balanced(self) -> bool:
        species = (*self.reactants, *self.products)
        counted = self.coefficients is not None and len(self.coefficients) == len(species)
        return counted and all(each.formula for each in species)


@dataclass(frozen=True)
class CraftHeld:
    slug: str
    name: str
    facts: Mapping[uuid.UUID, HeldFact] = field(default_factory=dict)
    stages: tuple[HeldStage, ...] = ()
    materials: tuple[HeldMaterial, ...] = ()
    reactions: tuple[HeldReaction, ...] = ()

    def stated(self, claim_ids: Iterable[uuid.UUID]) -> tuple[uuid.UUID, ...]:
        return tuple(dict.fromkeys(claim for claim in claim_ids if claim in self.facts))

    def stage(self, key: str | None) -> HeldStage | None:
        return next((stage for stage in self.stages if stage.key == key), None)

    def material(self, key: str | None) -> HeldMaterial | None:
        return next((material for material in self.materials if material.key == key), None)

    def label_root(self) -> str:
        return self.slug.lower()


@dataclass(frozen=True)
class About:
    stage: str | None = None
    reaction: str | None = None
    material: str | None = None
    compound: int | None = None


@dataclass(frozen=True)
class Composition:
    components: tuple[PageComponent, ...] = ()
    missing: tuple[str, ...] = ()
    left_out: tuple[str, ...] = ()

    @property
    def composed(self) -> bool:
        return bool(self.components) and not self.missing


def refused(*missing: str) -> Composition:
    return Composition(missing=tuple(dict.fromkeys(missing)))


def composed(*components: PageComponent, left_out: Iterable[str] = ()) -> Composition:
    return Composition(components=components, left_out=tuple(dict.fromkeys(left_out)))
