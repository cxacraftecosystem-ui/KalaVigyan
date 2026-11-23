from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from app.research.citations import SourceRef, cited_source_ids
from app.research.reactions import ReactionSpecies, mhchem_equation, reaction_level
from app.research.vocabulary import LEVEL_ORDER, weakest_level
from app.schemas.science import (
    CONDITION_QUANTITIES,
    CONDITION_UNITS,
    SCIENCE_SCHEMA_VERSION,
    UNAVAILABLE_LEVEL,
    CitedClaim,
    CompoundRef,
    ConditionReading,
    CraftProcess,
    DeltaH,
    ProcessStageView,
    ProcessView,
    ReactionView,
    StageCondition,
    StageMaterialView,
    process_claims,
    sources_differ,
)

from .reading_checks import reading_check
from .records import (
    ConditionRecord,
    KnownClaim,
    MaterialRecord,
    ProcessRecords,
    ReactionRecord,
    ReadingRecord,
    StageRecord,
)
from .units import Bounds

__all__ = ["condition_id", "craft_process", "ordered_claims"]


@dataclass(frozen=True)
class _Index:
    records: ProcessRecords
    materials: dict[uuid.UUID, list[MaterialRecord]]
    reactions: dict[uuid.UUID, list[ReactionRecord]]
    conditions: dict[uuid.UUID, list[ConditionRecord]]

    @classmethod
    def of(cls, records: ProcessRecords) -> _Index:
        materials: dict[uuid.UUID, list[MaterialRecord]] = defaultdict(list)
        reactions: dict[uuid.UUID, list[ReactionRecord]] = defaultdict(list)
        conditions: dict[uuid.UUID, list[ConditionRecord]] = defaultdict(list)
        for material in records.materials:
            materials[material.stage_id].append(material)
        for reaction in records.reactions:
            reactions[reaction.stage_id].append(reaction)
        for condition in records.conditions:
            conditions[condition.owner_id].append(condition)
        return cls(records, materials, reactions, conditions)

    def claim(self, claim_id: uuid.UUID) -> KnownClaim | None:
        return self.records.claims.get(claim_id)


def craft_process(records: ProcessRecords) -> CraftProcess:
    index = _Index.of(records)
    views = [
        ProcessView(
            id=process.id,
            name=process.name,
            variant=process.variant,
            stages=[
                _stage_view(stage, index)
                for stage in sorted(records.stages, key=lambda s: s.ordinal)
                if stage.process_id == process.id
            ],
        )
        for process in records.processes
    ]
    draft = CraftProcess.model_construct(
        schema_version=SCIENCE_SCHEMA_VERSION, craft=records.craft, processes=views, sources=[]
    )
    return CraftProcess(
        schema_version=SCIENCE_SCHEMA_VERSION,
        craft=records.craft,
        processes=views,
        sources=_cited_sources(process_claims(draft), records.sources),
    )


def ordered_claims(claims: Iterable[KnownClaim]) -> list[KnownClaim]:
    unique = {claim.id: claim for claim in claims}
    return sorted(unique.values(), key=lambda c: (LEVEL_ORDER[c.level], c.text, str(c.id)))


def condition_id(owner_id: uuid.UUID, key: str) -> str:
    return f"{owner_id}.{key}"


def _stage_view(stage: StageRecord, index: _Index) -> ProcessStageView:
    claims = _cited_claims(_known(stage.claim_ids, index), None)
    return ProcessStageView(
        id=stage.id,
        ordinal=stage.ordinal,
        ordered=stage.ordered,
        name=stage.name,
        stage_type=stage.stage_type,
        level=weakest_level(c.level for c in claims) if claims else UNAVAILABLE_LEVEL,
        claims=claims,
        materials=_present(
            _material_view(m, index) for m in sorted(index.materials[stage.id], key=_material_order)
        ),
        conditions=_conditions(stage.id, stage.stage_type, index),
        reactions=_present(
            _reaction_view(r, stage.stage_type, index)
            for r in sorted(index.reactions[stage.id], key=lambda r: (r.ordinal, r.label, str(r.id)))
        ),
    )


def _material_view(material: MaterialRecord, index: _Index) -> StageMaterialView | None:
    claims = _cited_claims(_known(material.claim_ids, index), None)
    if not claims:
        return None
    return StageMaterialView(
        id=material.id,
        name=material.name,
        kind=material.kind,
        role=material.role,
        quantity_text=material.quantity_text,
        compound=_compound(material),
        level=weakest_level(c.level for c in claims),
        claims=claims,
    )


def _conditions(owner_id: uuid.UUID, stage_type: str, index: _Index) -> list[StageCondition]:
    owned = sorted(
        index.conditions[owner_id],
        key=lambda c: (CONDITION_QUANTITIES.index(c.quantity), c.label, c.key),
    )
    return _present(_condition_view(condition, stage_type, index) for condition in owned)


def _condition_view(condition: ConditionRecord, stage_type: str, index: _Index) -> StageCondition | None:
    shown = [(r, index.claim(r.claim_id)) for r in condition.readings]
    shown = [(r, c) for r, c in shown if c is not None and r.citation_id in _citation_ids(c)]
    if not shown:
        return None
    claims = _cited_claims([claim for _, claim in shown], {(r.claim_id, r.citation_id) for r, _ in shown})
    order = {claim.id: position for position, claim in enumerate(claims)}
    readings = [
        _reading(reading, condition.quantity, stage_type)
        for reading, _ in sorted(shown, key=lambda pair: (order[pair[0].claim_id], pair[0].stated))
    ]
    return StageCondition(
        id=condition_id(condition.owner_id, condition.key),
        label=condition.label,
        quantity=condition.quantity,
        unit=CONDITION_UNITS[condition.quantity],
        readings=readings,
        sources_differ=sources_differ(condition.quantity, readings),
        level=weakest_level(c.level for c in claims),
        claims=claims,
    )


def _reading(reading: ReadingRecord, quantity: str, stage_type: str) -> ConditionReading:
    checked = reading_check(stage_type, quantity, Bounds(reading.low, reading.high), reading.unit)
    return ConditionReading(
        claim_id=reading.claim_id,
        min=checked.bounds.low,
        max=checked.bounds.high,
        stated=reading.stated,
        envelope=checked.envelope,
    )


def _reaction_view(reaction: ReactionRecord, stage_type: str, index: _Index) -> ReactionView | None:
    linked = [index.claim(claim_id) for claim_id, _ in reaction.citations]
    claims = _cited_claims([c for c in linked if c is not None], set(reaction.citations))
    if not claims:
        return None
    species = _species(reaction)
    level, reason = reaction_level([c.level for c in claims], balanced=reaction.balanced, species=species)
    shown_ids = {claim.id for claim in claims}
    delta_h = None
    if reaction.delta_h is not None and reaction.delta_h[1] in shown_ids:
        delta_h = DeltaH(kj_per_mol=reaction.delta_h[0], claim_id=reaction.delta_h[1])
    return ReactionView(
        id=reaction.id,
        kind=reaction.kind,
        label=reaction.label,
        species=species,
        balanced=reaction.balanced,
        equation=mhchem_equation(species),
        checker_version=reaction.checker_version,
        conditions=_conditions(reaction.id, stage_type, index),
        delta_h=delta_h,
        level=level,
        level_reason=reason,
        claims=claims,
    )


def _species(reaction: ReactionRecord) -> list[ReactionSpecies]:
    coefficients: Sequence[int | None] = [None] * len(reaction.species)
    if reaction.balanced:
        if reaction.coefficients is None or len(reaction.coefficients) != len(reaction.species):
            raise ValueError(f"balanced reaction {reaction.id} has no coefficient for each species")
        coefficients = reaction.coefficients
    return [
        ReactionSpecies(
            role=s.role, formula=s.formula, name=s.name, coefficient=coefficient, compound_id=s.compound_id
        )
        for s, coefficient in zip(reaction.species, coefficients, strict=True)
    ]


def _known(claim_ids: Iterable[uuid.UUID], index: _Index) -> list[KnownClaim]:
    return [claim for claim in (index.claim(i) for i in claim_ids) if claim is not None]


def _cited_claims(
    claims: Iterable[KnownClaim], linked: set[tuple[uuid.UUID, str]] | None
) -> list[CitedClaim]:
    cited = []
    for claim in ordered_claims(claims):
        citations = [c for c in claim.citations if linked is None or (claim.id, c.id) in linked]
        if citations:
            cited.append(CitedClaim(id=claim.id, text=claim.text, level=claim.level, citations=citations))
    return cited


def _citation_ids(claim: KnownClaim) -> set[str]:
    return {citation.id for citation in claim.citations}


def _cited_sources(claims: Iterable[CitedClaim], sources: Mapping[str, SourceRef]) -> list[SourceRef]:
    order = cited_source_ids(claims)
    missing = [source_id for source_id in order if source_id not in sources]
    if missing:
        raise ValueError(f"cited sources {', '.join(missing)} were not loaded")
    return [sources[source_id] for source_id in order]


def _compound(material: MaterialRecord) -> CompoundRef | None:
    found = material.compound
    if found is None:
        return None
    return CompoundRef(id=found.id, name=found.name, formula=found.formula, pubchem_cid=found.pubchem_cid)


def _material_order(material: MaterialRecord) -> tuple[str, str]:
    return material.name.casefold(), str(material.id)


def _present[T](views: Iterable[T | None]) -> list[T]:
    return [view for view in views if view is not None]
