from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import ColumnElement, Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models import (
    Claim,
    Concept,
    ConceptEdge,
    CraftCategory,
    CuratedCategoryClaim,
    TermConcept,
    TermCraft,
)
from app.research.retrieval import VISIBLE_SENSITIVITY

__all__ = ["linked_shared_concepts", "linked_shared_statement", "shared_concept"]

CONCEPT_SUBJECT = "CONCEPT"


def shared_concept() -> ColumnElement[bool]:
    return and_(Concept.craftId.is_(None), Concept.subCategoryId.is_(None))


async def linked_shared_concepts(
    session: AsyncSession, craft_ids: Sequence[uuid.UUID]
) -> tuple[uuid.UUID, ...]:
    if not craft_ids:
        return ()
    return tuple((await session.scalars(linked_shared_statement(craft_ids))).all())


def linked_shared_statement(craft_ids: Sequence[uuid.UUID]) -> Select[tuple[uuid.UUID]]:
    crafts = list(dict.fromkeys(craft_ids))
    return (
        select(Concept.id)
        .where(
            shared_concept(),
            Concept.sensitivity == VISIBLE_SENSITIVITY,
            or_(*(Concept.id.in_(linked) for linked in (_termed(crafts), *_edged(crafts)))),
            Concept.id.not_in(_family_subjects()),
            func.lower(Concept.name).not_in(select(func.lower(CraftCategory.name))),
        )
        .order_by(Concept.id)
    )


def _termed(crafts: list[uuid.UUID]) -> Select[tuple[uuid.UUID]]:
    return (
        select(TermConcept.conceptId)
        .join(TermCraft, TermCraft.termId == TermConcept.termId)
        .where(TermCraft.craftId.in_(crafts))
    )


def _edged(crafts: list[uuid.UUID]) -> tuple[Select[tuple[uuid.UUID]], Select[tuple[uuid.UUID]]]:
    owner = aliased(Concept, name="link_owner")
    owned = select(owner.id).where(owner.craftId.in_(crafts))
    return (
        select(ConceptEdge.dstId).where(ConceptEdge.srcId.in_(owned)),
        select(ConceptEdge.srcId).where(ConceptEdge.dstId.in_(owned)),
    )


def _family_subjects() -> Select[tuple[uuid.UUID]]:
    marked = aliased(Claim, name="family_marked")
    return (
        select(marked.subjectId)
        .join(CuratedCategoryClaim, CuratedCategoryClaim.claimId == marked.id)
        .where(marked.subjectType == CONCEPT_SUBJECT)
    )
