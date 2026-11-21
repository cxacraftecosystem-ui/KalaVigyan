from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import ColumnElement, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput
from app.models import Claim, Concept, CraftCategory, CuratedCategoryClaim
from app.models.enums import CLAIM_STATUSES
from app.research.candidate_gates import HeldFact
from app.research.knowledge_writes import ProposalSubject
from app.research.retrieval import VISIBLE_SENSITIVITY
from app.retrieval.statements import CraftScope, scope_claims

from . import knowledge_view

__all__ = [
    "CLOSED_STATUSES",
    "HELD_STATUSES",
    "FactSubject",
    "SqlHeldFacts",
    "craft_subject",
    "proposal_subject",
    "subject_claims",
]

HELD_STATUSES = ("DRAFT", "PROPOSED", "IN_REVIEW", "APPROVED")
CLOSED_STATUSES = tuple(status for status in CLAIM_STATUSES if status not in HELD_STATUSES)
CRAFT = "craft"
CATEGORY = "category"
SHARED = "shared"
TWINS_MAX = 5


@dataclass(frozen=True)
class FactSubject:
    kind: str
    name: str | None
    slug: str | None = None
    craft_id: uuid.UUID | None = None
    sub_category_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None


SHARED_SUBJECT = FactSubject(kind=SHARED, name=None)


async def proposal_subject(session: AsyncSession, subject: ProposalSubject) -> FactSubject:
    if subject.kind == CRAFT:
        return await craft_subject(session, subject.slug)
    category = await session.scalar(
        select(CraftCategory).where(func.lower(CraftCategory.slug) == subject.slug.lower())
    )
    if category is None:
        raise InvalidInput(f"No category has the slug {subject.slug!r}")
    return FactSubject(kind=CATEGORY, name=category.name, slug=category.slug, category_id=category.id)


async def craft_subject(session: AsyncSession, slug: str | None) -> FactSubject:
    if slug is None:
        return SHARED_SUBJECT
    craft = await knowledge_view.resolve_craft(session, slug)
    if craft is None:
        raise InvalidInput(f"No craft has the slug {slug!r}")
    return FactSubject(
        kind=CRAFT, name=craft.name, slug=craft.slug, craft_id=craft.id, sub_category_id=craft.subCategoryId
    )


class SqlHeldFacts:
    def __init__(
        self, session: AsyncSession, subject: FactSubject, *, statuses: Sequence[str] = HELD_STATUSES
    ) -> None:
        self._session = session
        self._subject = subject
        self._statuses = tuple(statuses)

    async def nearest(self, field: str | None, vector: Sequence[float], limit: int) -> list[HeldFact]:
        distance = Claim.embedding.cosine_distance(list(vector))
        rows = await self._session.execute(
            select(Claim.id, Claim.text, Claim.status, (1 - distance).label("similarity"))
            .where(*self._conditions(field), Claim.embedding.is_not(None))
            .order_by(distance, Claim.id)
            .limit(limit)
        )
        return [
            HeldFact(id=row.id, text=row.text, similarity=_bounded(row.similarity), status=row.status)
            for row in rows
        ]

    async def twins(self, field: str | None, statement: str) -> list[HeldFact]:
        folded = statement.strip().rstrip(" .").lower()
        rows = await self._session.execute(
            select(Claim.id, Claim.text, Claim.status)
            .where(*self._conditions(field), func.lower(func.rtrim(Claim.text, " .")) == folded)
            .order_by(Claim.createdAt, Claim.id)
            .limit(TWINS_MAX)
        )
        return [HeldFact(id=row.id, text=row.text, similarity=1.0, status=row.status) for row in rows]

    def _conditions(self, field: str | None) -> list[ColumnElement[bool]]:
        conditions = [
            subject_claims(self._subject),
            Claim.status.in_(self._statuses),
            Claim.sensitivity == VISIBLE_SENSITIVITY,
        ]
        if field is not None:
            conditions.append(or_(Claim.field == field, Claim.fields.contains([field])))
        return conditions


def subject_claims(subject: FactSubject) -> ColumnElement[bool]:
    if subject.kind == CRAFT:
        return scope_claims(CraftScope(craft_id=subject.craft_id, sub_category_id=subject.sub_category_id))
    shared = [Concept.craftId.is_(None), Concept.subCategoryId.is_(None)]
    if subject.kind == SHARED:
        return and_(Claim.subjectType == "CONCEPT", Claim.subjectId.in_(select(Concept.id).where(*shared)))
    named = select(Concept.id).where(*shared, func.lower(Concept.name) == (subject.name or "").lower())
    curated = select(CuratedCategoryClaim.claimId).where(
        CuratedCategoryClaim.categoryId == subject.category_id
    )
    return or_(Claim.id.in_(curated), and_(Claim.subjectType == "CONCEPT", Claim.subjectId.in_(named)))


def _bounded(similarity: float) -> float:
    return max(-1.0, min(1.0, float(similarity)))
