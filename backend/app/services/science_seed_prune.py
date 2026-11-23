from __future__ import annotations

import uuid
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.craft_text import fold
from app.models import (
    Compound,
    ConditionReading,
    ImageContribution,
    KnowledgePieceSubject,
    Material,
    ProcessCondition,
    Reaction,
    ReactionCitation,
    StageMaterial,
    UploadLink,
)
from app.services.claim_seed import seed_id
from app.services.curation_writes import delete_rows, keep_only

__all__ = [
    "SeedScope",
    "compound_key",
    "delete_unplanned_matter",
    "delete_unplanned_stage_rows",
    "seeded_compounds",
]

PlannedRows = Mapping[str, Sequence[Mapping[str, Any]]]
MATERIAL_USERS = (StageMaterial.materialId, ImageContribution.materialId, UploadLink.materialId)
COMPOUND_USERS = (Material.compoundId, KnowledgePieceSubject.compoundId)


@dataclass(frozen=True)
class SeedScope:
    stages: frozenset[uuid.UUID] = frozenset()
    materials: frozenset[uuid.UUID] = frozenset()


def compound_key(name: str) -> str:
    return "-".join(fold(name).split())


def seeded_compounds(
    stored: Iterable[tuple[uuid.UUID, str]], planned: Collection[uuid.UUID]
) -> list[uuid.UUID]:
    return [
        compound_id
        for compound_id, name in stored
        if compound_id not in planned and compound_id == seed_id("compound", compound_key(name))
    ]


async def delete_unplanned_stage_rows(
    session: AsyncSession, rows: PlannedRows, scope: SeedScope
) -> dict[str, int]:
    planned = _planned_ids(rows)
    stages = list(scope.stages)
    return {
        "readings": await delete_rows(
            session,
            ConditionReading,
            ConditionReading.conditionId.in_(planned["conditions"]),
            keep_only(ConditionReading.id, planned["readings"]),
        ),
        "reactionCitations": await delete_rows(
            session,
            ReactionCitation,
            ReactionCitation.reactionId.in_(planned["reactions"]),
            keep_only(ReactionCitation.id, planned["reactionCitations"]),
        ),
        "conditions": await delete_rows(
            session,
            ProcessCondition,
            ProcessCondition.stageId.in_(stages),
            keep_only(ProcessCondition.id, planned["conditions"]),
        ),
        "reactions": await delete_rows(
            session, Reaction, Reaction.stageId.in_(stages), keep_only(Reaction.id, planned["reactions"])
        ),
        "stageMaterials": await delete_rows(
            session,
            StageMaterial,
            StageMaterial.stageId.in_(stages),
            keep_only(StageMaterial.id, planned["stageMaterials"]),
        ),
    }


async def delete_unplanned_matter(
    session: AsyncSession, rows: PlannedRows, scope: SeedScope
) -> dict[str, int]:
    planned = _planned_ids(rows)
    materials = await _unused(session, Material, scope.materials - set(planned["materials"]), MATERIAL_USERS)
    deleted = {"materials": await _delete_ids(session, Material, materials)}
    stored = (await session.execute(select(Compound.id, Compound.name))).tuples().all()
    candidates = seeded_compounds(stored, set(planned["compounds"]))
    unused = await _unused(session, Compound, candidates, COMPOUND_USERS)
    named = await _named_in_species(session) if unused else set()
    deleted["compounds"] = await _delete_ids(session, Compound, [c for c in unused if str(c) not in named])
    return deleted


def _planned_ids(rows: PlannedRows) -> dict[str, list[uuid.UUID]]:
    return {name: [row["id"] for row in planned] for name, planned in rows.items()}


async def _unused(
    session: AsyncSession, model: Any, ids: Collection[uuid.UUID], users: Sequence[Any]
) -> list[uuid.UUID]:
    if not ids:
        return []
    unreferenced = [~exists().where(column == model.id) for column in users]
    found = await session.scalars(select(model.id).where(model.id.in_(list(ids)), *unreferenced))
    return sorted(found.all())


async def _named_in_species(session: AsyncSession) -> set[str]:
    listed = (await session.scalars(select(Reaction.species))).all()
    return {str(item["compoundId"]) for species in listed for item in species if item.get("compoundId")}


async def _delete_ids(session: AsyncSession, model: Any, ids: Sequence[uuid.UUID]) -> int:
    return await delete_rows(session, model, model.id.in_(list(ids))) if ids else 0
