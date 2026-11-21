from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import ColumnElement, Select, and_, false, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AdminDistrict,
    Compound,
    Concept,
    Craft,
    KnowledgePiece,
    KnowledgePieceSubject as Subject,
)
from app.research.knowledge_api import (
    COMPONENTS_LIMIT_MAX,
    ComponentSubject,
    ComponentSummary,
    CraftComponents,
)
from app.retrieval.statements import TEXT_SEARCH_CONFIG, lexical_rank, text_query
from app.retrieval.text import or_tsquery

from .component_library_applies import (
    APPLIED_CRAFT,
    APPLIED_PIECE,
    DISTRICT_KEY_PREFIX,
    applies_to,
    registered_pieces,
)
from .component_places_held import held_pieces, piece_facts
from .knowledge_api import known_craft

__all__ = ["APPLIED_CRAFT", "APPLIED_PIECE", "applies_to", "library_components", "registered_pieces"]

OPEN_CONCEPT = "OPEN"
LABEL_SEPARATORS = "/-"


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
    craft = None if slug is None else await known_craft(session, slug)
    if craft is not None:
        applying = applies_to([craft.id]).subquery()
        conditions.append(KnowledgePiece.id.in_(select(applying.c[APPLIED_PIECE])))
    if field is not None:
        conditions.append(or_(KnowledgePiece.facet == field, KnowledgePiece.fields.any(field)))
    if kind is not None:
        conditions.append(KnowledgePiece.kind == kind)
    listing = _listing(conditions, query)
    rows = (await session.execute(listing if craft is not None else listing.limit(limit))).all()
    if craft is not None:
        held = await held_pieces(session, [(craft.id, piece_facts(piece)) for piece, _ in rows])
        rows = [row for row in rows if (craft.id, row[0].id) in held][:limit]
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
