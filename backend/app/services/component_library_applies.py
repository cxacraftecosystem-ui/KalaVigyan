from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import ColumnElement, CompoundSelect, Select, func, select, union

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
from app.models.science import live_process

__all__ = ["APPLIED_CRAFT", "APPLIED_PIECE", "DISTRICT_KEY_PREFIX", "applies_to", "registered_pieces"]

DISTRICT_KEY_PREFIX = f"{DISTRICT_PLACE_PREFIX}:"
APPLIED_CRAFT = "craft"
APPLIED_PIECE = "piece"


def registered_pieces() -> list[ColumnElement[bool]]:
    return [
        KnowledgePiece.label.is_not(None),
        KnowledgePiece.hiddenAt.is_(None),
        KnowledgePiece.supersededById.is_(None),
    ]


def applies_to(craft_ids: Sequence[uuid.UUID]) -> CompoundSelect[Any]:
    crafts = list(craft_ids)
    own = select(KnowledgePiece.craftId.label(APPLIED_CRAFT), KnowledgePiece.id.label(APPLIED_PIECE))
    by_concept = _keyed(Concept.craftId).join(Concept, Concept.id == Subject.conceptId)
    return union(
        own.where(KnowledgePiece.craftId.in_(crafts)),
        _keyed(Subject.craftId).where(Subject.craftId.in_(crafts)),
        by_concept.where(Concept.craftId.in_(crafts)),
        _by_stage_concept(crafts),
        _by_material(crafts, Material.conceptId, Subject.conceptId),
        _by_material(crafts, Material.compoundId, Subject.compoundId),
        _by_district(crafts),
    )


def _keyed(craft: Any) -> Select[Any]:
    return select(craft.label(APPLIED_CRAFT), Subject.pieceId.label(APPLIED_PIECE)).select_from(Subject)


def _by_stage_concept(crafts: list[uuid.UUID]) -> Select[Any]:
    return (
        _keyed(Process.craftId)
        .join(ProcessStage, ProcessStage.conceptId == Subject.conceptId)
        .join(Process, Process.id == ProcessStage.processId)
        .where(Process.craftId.in_(crafts), live_process())
    )


def _by_material(crafts: list[uuid.UUID], material_key: Any, subject_key: Any) -> Select[Any]:
    return (
        _keyed(Process.craftId)
        .join(Material, material_key == subject_key)
        .join(StageMaterial, StageMaterial.materialId == Material.id)
        .join(ProcessStage, ProcessStage.id == StageMaterial.stageId)
        .join(Process, Process.id == ProcessStage.processId)
        .where(Process.craftId.in_(crafts), live_process())
    )


def _by_district(crafts: list[uuid.UUID]) -> Select[Any]:
    place = func.concat(DISTRICT_KEY_PREFIX, CraftLocation.districtLgd)
    return (
        _keyed(CraftLocation.craftId)
        .join(CraftLocation, place == Subject.placeKey)
        .where(CraftLocation.craftId.in_(crafts), CraftLocation.districtLgd.is_not(None))
    )
