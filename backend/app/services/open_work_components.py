from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import ColumnElement, Select, func, select, union
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Concept,
    CraftLocation,
    KnowledgePiece,
    KnowledgePieceSubject as Subject,
    Material,
    Process,
    ProcessStage,
    StageMaterial,
)
from app.models.enums import DISTRICT_PLACE_PREFIX

__all__ = ["CraftPiece", "craft_component_kinds", "craft_pieces", "registered_pieces"]

DISTRICT_KEY_PREFIX = f"{DISTRICT_PLACE_PREFIX}:"


@dataclass(frozen=True)
class CraftPiece:
    craft_id: uuid.UUID
    label: str
    kind: str
    field: str
    fields: tuple[str, ...]

    def filed_under(self) -> tuple[str, ...]:
        return (self.field, *(other for other in self.fields if other != self.field))


async def craft_pieces(session: AsyncSession, craft_ids: Sequence[uuid.UUID]) -> list[CraftPiece]:
    if not craft_ids:
        return []
    crafts = list(craft_ids)
    rows = await session.execute(
        union(
            _own(crafts),
            _linked(crafts),
            _by_own_concept(crafts),
            _by_stage_concept(crafts),
            _by_material(crafts, Material.conceptId, Subject.conceptId),
            _by_material(crafts, Material.compoundId, Subject.compoundId),
            _by_district(crafts),
        )
    )
    return [
        CraftPiece(craft_id, str(label), kind, facet, tuple(fields or ()))
        for craft_id, label, kind, facet, fields in rows.all()
    ]


async def craft_component_kinds(
    session: AsyncSession, craft_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, frozenset[str]]:
    found: dict[uuid.UUID, set[str]] = defaultdict(set)
    for piece in await craft_pieces(session, craft_ids):
        found[piece.craft_id].add(piece.kind)
    return {craft_id: frozenset(kinds) for craft_id, kinds in found.items()}


def registered_pieces() -> list[ColumnElement[bool]]:
    return [
        KnowledgePiece.label.is_not(None),
        KnowledgePiece.hiddenAt.is_(None),
        KnowledgePiece.supersededById.is_(None),
    ]


def _piece_columns() -> tuple[Any, ...]:
    return (KnowledgePiece.label, KnowledgePiece.kind, KnowledgePiece.facet, KnowledgePiece.fields)


def _keyed(craft: Any) -> Select[Any]:
    return (
        select(craft.label("craft"), *_piece_columns())
        .select_from(Subject)
        .join(KnowledgePiece, KnowledgePiece.id == Subject.pieceId)
    )


def _own(crafts: list[uuid.UUID]) -> Select[Any]:
    return select(KnowledgePiece.craftId.label("craft"), *_piece_columns()).where(
        KnowledgePiece.craftId.in_(crafts), *registered_pieces()
    )


def _linked(crafts: list[uuid.UUID]) -> Select[Any]:
    return (
        select(Subject.craftId.label("craft"), *_piece_columns())
        .join(KnowledgePiece, KnowledgePiece.id == Subject.pieceId)
        .where(Subject.craftId.in_(crafts), *registered_pieces())
    )


def _by_own_concept(crafts: list[uuid.UUID]) -> Select[Any]:
    return (
        _keyed(Concept.craftId)
        .join(Concept, Concept.id == Subject.conceptId)
        .where(Concept.craftId.in_(crafts), *registered_pieces())
    )


def _by_stage_concept(crafts: list[uuid.UUID]) -> Select[Any]:
    return (
        _keyed(Process.craftId)
        .join(ProcessStage, ProcessStage.conceptId == Subject.conceptId)
        .join(Process, Process.id == ProcessStage.processId)
        .where(Process.craftId.in_(crafts), *registered_pieces())
    )


def _by_material(crafts: list[uuid.UUID], material_key: Any, subject_key: Any) -> Select[Any]:
    return (
        _keyed(Process.craftId)
        .join(Material, material_key == subject_key)
        .join(StageMaterial, StageMaterial.materialId == Material.id)
        .join(ProcessStage, ProcessStage.id == StageMaterial.stageId)
        .join(Process, Process.id == ProcessStage.processId)
        .where(Process.craftId.in_(crafts), *registered_pieces())
    )


def _by_district(crafts: list[uuid.UUID]) -> Select[Any]:
    place = func.concat(DISTRICT_KEY_PREFIX, CraftLocation.districtLgd)
    return (
        _keyed(CraftLocation.craftId)
        .join(CraftLocation, place == Subject.placeKey)
        .where(
            CraftLocation.craftId.in_(crafts), CraftLocation.districtLgd.is_not(None), *registered_pieces()
        )
    )
