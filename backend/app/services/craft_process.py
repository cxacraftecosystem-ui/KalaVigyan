from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Claim,
    ClaimSource,
    Compound,
    Concept,
    ConditionReading,
    Craft,
    Material,
    Process,
    ProcessCondition,
    ProcessStage,
    Reaction,
    ReactionCitation,
    StageMaterial,
)
from app.models.science import live_process
from app.research.citations import Citation, SourceRef
from app.research.crafts import CraftRef
from app.research.retrieval import OPEN_CHUNK_ACLS, VISIBLE_SENSITIVITY
from app.science.records import (
    CompoundRecord,
    ConditionRecord,
    KnownClaim,
    MaterialRecord,
    ProcessRecord,
    ProcessRecords,
    ReactionRecord,
    ReadingRecord,
    SpeciesRecord,
    StageRecord,
)
from app.services.knowledge_view import claims_by_id, craft_ref, source_ref

__all__ = ["process_records"]


@dataclass(frozen=True)
class _Rows:
    processes: Sequence[Process]
    stages: Sequence[ProcessStage]
    materials: Sequence[Any]
    reactions: Sequence[Reaction]
    reaction_links: Sequence[Any]
    conditions: Sequence[ProcessCondition]
    readings: Sequence[Any]


async def process_records(
    session: AsyncSession, craft: Craft, *, acls: Sequence[str] = OPEN_CHUNK_ACLS
) -> ProcessRecords:
    rows = await _load_rows(session, craft)
    concept_claims = await _concept_claims(session, _concept_ids(rows))
    wanted = [claim_id for ids in concept_claims.values() for claim_id in ids]
    wanted += [link.StageMaterial.claimId for link in rows.materials if link.StageMaterial.claimId]
    wanted += [link.claimId for link in rows.reaction_links]
    wanted += [reading.claimId for reading in rows.readings]
    claims, sources = await _known_claims(session, wanted, acls=acls)
    return ProcessRecords(
        craft=CraftRef.model_validate(craft_ref(craft)),
        processes=tuple(ProcessRecord(p.id, p.name, p.variant) for p in rows.processes),
        stages=tuple(_stage(stage, concept_claims) for stage in rows.stages),
        materials=tuple(_material(link, concept_claims) for link in rows.materials),
        reactions=tuple(_reactions(rows)),
        conditions=tuple(_conditions(rows)),
        claims=claims,
        sources=sources,
    )


async def _load_rows(session: AsyncSession, craft: Craft) -> _Rows:
    processes = (
        await session.scalars(
            select(Process)
            .where(Process.craftId == craft.id, live_process())
            .order_by(Process.name, Process.variant, Process.id)
        )
    ).all()
    stages = await _stage_rows(session, [p.id for p in processes])
    stage_ids = [stage.id for stage in stages]
    reactions = await _reaction_rows(session, stage_ids)
    reaction_ids = [reaction.id for reaction in reactions]
    conditions = await _condition_rows(session, stage_ids, reaction_ids)
    return _Rows(
        processes=processes,
        stages=stages,
        materials=await _materials(session, stage_ids),
        reactions=reactions,
        reaction_links=await _reaction_links(session, reaction_ids),
        conditions=conditions,
        readings=await _readings(session, [condition.id for condition in conditions]),
    )


async def _stage_rows(session: AsyncSession, process_ids: list[uuid.UUID]) -> Sequence[ProcessStage]:
    statement = (
        select(ProcessStage)
        .where(ProcessStage.processId.in_(process_ids))
        .order_by(ProcessStage.processId, ProcessStage.ordinal, ProcessStage.id)
    )
    return (await session.scalars(statement)).all()


async def _reaction_rows(session: AsyncSession, stage_ids: list[uuid.UUID]) -> Sequence[Reaction]:
    statement = (
        select(Reaction)
        .where(Reaction.stageId.in_(stage_ids))
        .order_by(Reaction.stageId, Reaction.ordinal, Reaction.id)
    )
    return (await session.scalars(statement)).all()


async def _condition_rows(
    session: AsyncSession, stage_ids: list[uuid.UUID], reaction_ids: list[uuid.UUID]
) -> Sequence[ProcessCondition]:
    statement = (
        select(ProcessCondition)
        .where(or_(ProcessCondition.stageId.in_(stage_ids), ProcessCondition.reactionId.in_(reaction_ids)))
        .order_by(ProcessCondition.id)
    )
    return (await session.scalars(statement)).all()


async def _materials(session: AsyncSession, stage_ids: list[uuid.UUID]) -> Sequence[Any]:
    statement = (
        select(StageMaterial, Material, Compound)
        .join(Material, Material.id == StageMaterial.materialId)
        .outerjoin(Compound, Compound.id == Material.compoundId)
        .where(StageMaterial.stageId.in_(stage_ids))
        .order_by(StageMaterial.stageId, Material.name, StageMaterial.id)
    )
    return (await session.execute(statement)).all()


async def _reaction_links(session: AsyncSession, reaction_ids: list[uuid.UUID]) -> Sequence[Any]:
    statement = (
        select(ReactionCitation.reactionId, ClaimSource.claimId, ClaimSource.id)
        .join(ClaimSource, ClaimSource.id == ReactionCitation.claimSourceId)
        .where(ReactionCitation.reactionId.in_(reaction_ids))
        .order_by(ReactionCitation.reactionId, ClaimSource.id)
    )
    return (await session.execute(statement)).all()


async def _readings(session: AsyncSession, condition_ids: list[uuid.UUID]) -> Sequence[Any]:
    statement = (
        select(ConditionReading, ClaimSource.claimId)
        .join(ClaimSource, ClaimSource.id == ConditionReading.claimSourceId)
        .where(ConditionReading.conditionId.in_(condition_ids))
        .order_by(ConditionReading.conditionId, ConditionReading.id)
    )
    return (await session.execute(statement)).all()


async def _concept_claims(
    session: AsyncSession, concept_ids: Iterable[uuid.UUID]
) -> dict[uuid.UUID, list[uuid.UUID]]:
    statement = (
        select(Claim.id, Claim.subjectId)
        .join(Concept, Concept.id == Claim.subjectId)
        .where(
            Claim.subjectType == "CONCEPT",
            Claim.subjectId.in_(list(concept_ids)),
            Concept.sensitivity == VISIBLE_SENSITIVITY,
        )
    )
    found: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
    for claim_id, concept_id in (await session.execute(statement)).all():
        found[concept_id].append(claim_id)
    return found


async def _known_claims(
    session: AsyncSession, claim_ids: Iterable[uuid.UUID], *, acls: Sequence[str]
) -> tuple[dict[uuid.UUID, KnownClaim], dict[str, SourceRef]]:
    views, sources = await claims_by_id(session, claim_ids, acls=acls)
    claims = {
        view.id: KnownClaim(
            id=view.id,
            text=view.text,
            level=view.level,
            citations=tuple(Citation.model_validate(citation) for citation in view.citations),
        )
        for view in views.values()
    }
    return claims, {str(sid): SourceRef.model_validate(source_ref(source)) for sid, source in sources.items()}


def _concept_ids(rows: _Rows) -> set[uuid.UUID]:
    ids = {stage.conceptId for stage in rows.stages if stage.conceptId}
    ids |= {link.Material.conceptId for link in rows.materials if link.Material.conceptId}
    return ids


def _stage(stage: ProcessStage, concept_claims: Mapping[uuid.UUID, list[uuid.UUID]]) -> StageRecord:
    claim_ids = tuple(concept_claims.get(stage.conceptId, [])) if stage.conceptId else ()
    return StageRecord(
        stage.id,
        stage.processId,
        stage.ordinal,
        stage.name,
        stage.stageType,
        claim_ids,
        ordered=stage.ordered,
    )


def _material(link: Any, concept_claims: Mapping[uuid.UUID, list[uuid.UUID]]) -> MaterialRecord:
    staged, material, compound = link.StageMaterial, link.Material, link.Compound
    claim_ids = [staged.claimId] if staged.claimId else []
    if material.conceptId:
        claim_ids += concept_claims.get(material.conceptId, [])
    return MaterialRecord(
        id=staged.id,
        stage_id=staged.stageId,
        name=material.name,
        kind=material.kind,
        role=staged.role,
        quantity_text=staged.quantityText,
        compound=None if compound is None else _compound(compound),
        claim_ids=tuple(claim_ids),
        material_id=material.id,
        concept_id=material.conceptId,
    )


def _compound(compound: Compound) -> CompoundRecord:
    return CompoundRecord(
        compound.id, compound.name, compound.formula, compound.pubchemCid, compound.sourceId
    )


def _reactions(rows: _Rows) -> list[ReactionRecord]:
    links: dict[uuid.UUID, list[tuple[uuid.UUID, str]]] = defaultdict(list)
    for reaction_id, claim_id, citation_id in rows.reaction_links:
        links[reaction_id].append((claim_id, str(citation_id)))
    return [
        ReactionRecord(
            id=reaction.id,
            stage_id=reaction.stageId,
            ordinal=reaction.ordinal,
            kind=reaction.kind,
            label=reaction.label,
            species=tuple(_species(item) for item in reaction.species),
            balanced=reaction.balanced,
            coefficients=tuple(reaction.coefficients) if reaction.coefficients else None,
            checker_version=reaction.checkerVersion,
            delta_h=_delta_h(reaction),
            citations=tuple(links[reaction.id]),
        )
        for reaction in rows.reactions
    ]


def _species(item: Mapping[str, Any]) -> SpeciesRecord:
    compound = item.get("compoundId")
    return SpeciesRecord(
        role=item["role"],
        formula=item.get("formula"),
        name=item.get("name"),
        compound_id=uuid.UUID(compound) if compound else None,
    )


def _delta_h(reaction: Reaction) -> tuple[float, uuid.UUID] | None:
    if reaction.deltaHKjMol is None or reaction.deltaHClaimId is None:
        return None
    return float(reaction.deltaHKjMol), reaction.deltaHClaimId


def _conditions(rows: _Rows) -> list[ConditionRecord]:
    readings: dict[uuid.UUID, list[ReadingRecord]] = defaultdict(list)
    for reading, claim_id in rows.readings:
        readings[reading.conditionId].append(
            ReadingRecord(
                claim_id=claim_id,
                citation_id=str(reading.claimSourceId),
                stated=reading.stated,
                low=_number(reading.statedMin),
                high=_number(reading.statedMax),
                unit=reading.statedUnit,
            )
        )
    return [
        ConditionRecord(
            owner_id=condition.stageId or condition.reactionId,
            key=condition.key,
            label=condition.label,
            quantity=condition.quantity,
            readings=tuple(readings[condition.id]),
        )
        for condition in rows.conditions
    ]


def _number(value: Decimal | None) -> float | None:
    return None if value is None else float(value)
