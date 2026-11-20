from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import ColumnElement, CompoundSelect, Select, and_, false, func, or_, select, union
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AdminDistrict,
    Compound,
    Concept,
    Craft,
    CraftLocation,
    KnowledgePiece,
    KnowledgePieceSubject as Subject,
    Material,
    Process,
    ProcessStage,
    StageMaterial,
)
from app.models.enums import DISTRICT_PLACE_PREFIX
from app.research.knowledge_api import (
    COMPONENTS_LIMIT_MAX,
    ComponentSubject,
    ComponentSummary,
    CraftComponents,
)
from app.retrieval.statements import TEXT_SEARCH_CONFIG, lexical_rank, text_query
from app.retrieval.text import or_tsquery

from .knowledge_api import known_craft

__all__ = ["APPLIED_CRAFT", "APPLIED_PIECE", "applies_to", "library_components", "registered_pieces"]

OPEN_CONCEPT = "OPEN"
DISTRICT_KEY_PREFIX = f"{DISTRICT_PLACE_PREFIX}:"
LABEL_SEPARATORS = "/-"
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


async def library_components(
    session: AsyncSession,
    *,
    slug: str | None = None,
    field: str | None = None,
    kind: str | None = None,
    query: str | None = None,
    limit: int = COMPONENTS_LIMIT_MAX,
) -> CraftComponents:
    conditions = registered_pieces()
    if slug is not None:
        craft = await known_craft(session, slug)
        applying = applies_to([craft.id]).subquery()
        conditions.append(KnowledgePiece.id.in_(select(applying.c[APPLIED_PIECE])))
    if field is not None:
        conditions.append(or_(KnowledgePiece.facet == field, KnowledgePiece.fields.any(field)))
    if kind is not None:
        conditions.append(KnowledgePiece.kind == kind)
    rows = (await session.execute(_listing(conditions, query).limit(limit))).all()
    subjects = await _subjects(session, [piece.id for piece, _ in rows])
    return CraftComponents(
        craft_slug=slug,
        field=field,
        kind=kind,
        query=query,
        components=[_summary(piece, owner, subjects.get(piece.id, [])) for piece, owner in rows],
    )


def _listing(conditions: list[ColumnElement[bool]], query: str | None) -> Select[Any]:
    statement = (
        select(KnowledgePiece, Craft.slug)
        .outerjoin(Craft, Craft.id == KnowledgePiece.craftId)
        .where(*conditions)
    )
    terms = or_tsquery(query) if query else None
    if query and terms is None:
        return statement.where(false())
    if terms is None:
        return statement.order_by(KnowledgePiece.label)
    document = _document()
    asked = text_query(terms)
    return statement.where(document.op("@@")(asked)).order_by(
        lexical_rank(document, asked).desc(), KnowledgePiece.label
    )


def _document() -> ColumnElement[Any]:
    words = func.concat_ws(
        " ",
        func.translate(KnowledgePiece.label, LABEL_SEPARATORS, " " * len(LABEL_SEPARATORS)),
        KnowledgePiece.title,
        KnowledgePiece.description,
    )
    return func.to_tsvector(TEXT_SEARCH_CONFIG, words)


def _keyed(craft: Any) -> Select[Any]:
    return select(craft.label(APPLIED_CRAFT), Subject.pieceId.label(APPLIED_PIECE)).select_from(Subject)


def _by_stage_concept(crafts: list[uuid.UUID]) -> Select[Any]:
    return (
        _keyed(Process.craftId)
        .join(ProcessStage, ProcessStage.conceptId == Subject.conceptId)
        .join(Process, Process.id == ProcessStage.processId)
        .where(Process.craftId.in_(crafts))
    )


def _by_material(crafts: list[uuid.UUID], material_key: Any, subject_key: Any) -> Select[Any]:
    return (
        _keyed(Process.craftId)
        .join(Material, material_key == subject_key)
        .join(StageMaterial, StageMaterial.materialId == Material.id)
        .join(ProcessStage, ProcessStage.id == StageMaterial.stageId)
        .join(Process, Process.id == ProcessStage.processId)
        .where(Process.craftId.in_(crafts))
    )


def _by_district(crafts: list[uuid.UUID]) -> Select[Any]:
    place = func.concat(DISTRICT_KEY_PREFIX, CraftLocation.districtLgd)
    return (
        _keyed(CraftLocation.craftId)
        .join(CraftLocation, place == Subject.placeKey)
        .where(CraftLocation.craftId.in_(crafts), CraftLocation.districtLgd.is_not(None))
    )


async def _subjects(
    session: AsyncSession, piece_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, list[ComponentSubject]]:
    if not piece_ids:
        return {}
    rows = await session.execute(
        select(
            Subject,
            Craft.slug.label("craft_slug"),
            Craft.name.label("craft_name"),
            Concept.name.label("concept"),
            Compound.name.label("compound"),
            AdminDistrict.name.label("district"),
        )
        .outerjoin(Craft, Craft.id == Subject.craftId)
        .outerjoin(Concept, and_(Concept.id == Subject.conceptId, Concept.sensitivity == OPEN_CONCEPT))
        .outerjoin(Compound, Compound.id == Subject.compoundId)
        .outerjoin(AdminDistrict, func.concat(DISTRICT_KEY_PREFIX, AdminDistrict.lgd) == Subject.placeKey)
        .where(Subject.pieceId.in_(list(piece_ids)))
        .order_by(Subject.pieceId, Subject.kind, Subject.createdAt)
    )
    found: dict[uuid.UUID, list[ComponentSubject]] = {}
    for row in rows.all():
        shown = _subject(row[0], row)
        if shown is not None:
            found.setdefault(row[0].pieceId, []).append(shown)
    return found


def _subject(subject: Subject, names: Any) -> ComponentSubject | None:
    if subject.craftId is not None and names.craft_slug and names.craft_name:
        return ComponentSubject(kind=subject.kind, key=names.craft_slug, name=names.craft_name)
    if subject.conceptId is not None and names.concept:
        return ComponentSubject(kind=subject.kind, key=str(subject.conceptId), name=names.concept)
    if subject.compoundId is not None and names.compound:
        return ComponentSubject(kind=subject.kind, key=str(subject.compoundId), name=names.compound)
    if subject.placeKey is not None:
        return ComponentSubject(
            kind=subject.kind, key=subject.placeKey, name=names.district or subject.placeKey
        )
    return None


def _summary(piece: KnowledgePiece, owner: str | None, subjects: list[ComponentSubject]) -> ComponentSummary:
    return ComponentSummary(
        label=piece.label,
        title=piece.title,
        description=piece.description,
        kind=piece.kind,
        field=piece.facet,
        fields=piece.fields,
        craft_slug=owner,
        subjects=subjects,
    )
