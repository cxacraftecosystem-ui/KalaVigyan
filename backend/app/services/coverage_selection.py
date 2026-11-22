from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import ColumnElement, Select, and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Claim, Concept, Craft, EnrichmentJob
from app.research.crafts import CraftRef
from app.research.planning import FACET_COVERED_MIN_CLAIMS
from app.research.retrieval import HIDDEN_CLAIM_STATUSES, VISIBLE_SENSITIVITY
from app.research.vocabulary import CONCEPT_TYPE_DISCIPLINES
from app.research.write_back import WRITE_BACK_ORIGIN

__all__ = [
    "ENRICHMENT_COOLDOWN",
    "FRUITLESS_BACKOFF",
    "SHARED_CLAIM_WEIGHT",
    "STANDARD_QUESTIONS",
    "CraftToEnrich",
    "StandardQuestion",
    "least_covered_crafts",
    "open_questions",
    "weighted_claims",
]

ENRICHMENT_COOLDOWN = timedelta(days=7)
FRUITLESS_BACKOFF = timedelta(days=28)
ACTIVE_CRAFT = "ACTIVE"
FINISHED_JOB = "SUCCEEDED"
CONCEPT_SUBJECT = "CONCEPT"
SHARED_CLAIM_WEIGHT = 0.5

FieldCounts = Mapping[str | None, int]


@dataclass(frozen=True)
class StandardQuestion:
    facet: str
    template: str

    @property
    def field(self) -> str:
        return CONCEPT_TYPE_DISCIPLINES[self.facet]

    def text_for(self, craft_name: str) -> str:
        return self.template.format(name=craft_name)


STANDARD_QUESTIONS: tuple[StandardQuestion, ...] = (
    StandardQuestion("MATERIAL", "What raw materials, dyes and chemicals are used in {name}?"),
    StandardQuestion("PROCESS_STAGE", "What are the stages of making {name}, in order?"),
    StandardQuestion("MECHANISM", "What chemical or physical changes take place while {name} is made?"),
    StandardQuestion("TOOL", "What tools and equipment are used to make {name}?"),
    StandardQuestion("ENVIRONMENTAL_CONDITION", "How do local water, soil and climate affect {name}?"),
    StandardQuestion("HISTORICAL_CONTEXT", "Where and when did {name} develop, and how has it changed?"),
)


@dataclass(frozen=True)
class CraftToEnrich:
    craft_id: uuid.UUID
    slug: str
    name: str
    claims: float
    field_claims: Mapping[str, float] = field(default_factory=dict)
    resting: frozenset[str] = frozenset()

    @property
    def ref(self) -> CraftRef:
        return CraftRef(slug=self.slug, name=self.name, path=f"/crafts/{self.slug}")


def open_questions(craft: CraftToEnrich) -> list[StandardQuestion]:
    return [
        question
        for question in STANDARD_QUESTIONS
        if question.facet not in craft.resting
        and craft.field_claims.get(question.field, 0) < FACET_COVERED_MIN_CLAIMS
    ]


def weighted_claims(own: FieldCounts, shared: FieldCounts) -> tuple[float, dict[str, float]]:
    fields = {name for name in (*own, *shared) if name is not None}
    by_field = {name: own.get(name, 0) + SHARED_CLAIM_WEIGHT * shared.get(name, 0) for name in sorted(fields)}
    total = sum(own.values()) + SHARED_CLAIM_WEIGHT * sum(shared.values())
    return total, by_field


async def least_covered_crafts(session: AsyncSession, *, now: datetime, limit: int) -> list[CraftToEnrich]:
    if limit < 1:
        raise ValueError(f"Pick at least one craft, not {limit}")
    recent = select(EnrichmentJob.id).where(
        EnrichmentJob.craftId == Craft.id, EnrichmentJob.createdAt >= now - ENRICHMENT_COOLDOWN
    )
    rows = await session.execute(
        select(Craft.id, Craft.slug, Craft.name, Craft.subCategoryId).where(
            Craft.status == ACTIVE_CRAFT, Craft.isCatchAll.is_(False), ~recent.exists()
        )
    )
    own = await _counts(session, Concept.craftId, Concept.craftId.is_not(None))
    shared = await _counts(
        session, Concept.subCategoryId, and_(Concept.craftId.is_(None), Concept.subCategoryId.is_not(None))
    )
    resting = await _resting(session, now)
    crafts = [
        _to_enrich(
            row, own.get(row.id, {}), shared.get(row.subCategoryId, {}), resting.get(row.id, frozenset())
        )
        for row in rows
    ]
    crafts.sort(key=lambda craft: (craft.claims, craft.slug))
    return [craft for craft in crafts if open_questions(craft)][:limit]


def _to_enrich(row: Any, own: FieldCounts, shared: FieldCounts, resting: frozenset[str]) -> CraftToEnrich:
    total, by_field = weighted_claims(own, shared)
    return CraftToEnrich(row.id, row.slug, row.name, total, by_field, resting)


async def _counts(
    session: AsyncSession, owner: Any, condition: ColumnElement[bool]
) -> dict[uuid.UUID, dict[str | None, int]]:
    visible = and_(
        Claim.subjectType == CONCEPT_SUBJECT,
        Claim.subjectId == Concept.id,
        Claim.status.not_in(HIDDEN_CLAIM_STATUSES),
        Claim.sensitivity == VISIBLE_SENSITIVITY,
    )
    statement = (
        select(owner.label("owner"), Claim.field, func.count(Claim.id).label("claims"))
        .join(Claim, visible)
        .where(condition, Concept.sensitivity == VISIBLE_SENSITIVITY)
        .group_by(owner, Claim.field)
    )
    counts: dict[uuid.UUID, dict[str | None, int]] = {}
    for row in await session.execute(statement):
        counts.setdefault(row.owner, {})[row.field] = int(row.claims)
    return counts


async def _resting(session: AsyncSession, now: datetime) -> dict[uuid.UUID, frozenset[str]]:
    since = now - FRUITLESS_BACKOFF
    finished = select(EnrichmentJob.id, EnrichmentJob.craftId, EnrichmentJob.facets).where(
        EnrichmentJob.createdAt >= since,
        EnrichmentJob.status == FINISHED_JOB,
        EnrichmentJob.startedAt.is_not(None),
        EnrichmentJob.finishedAt.is_not(None),
    )
    jobs = (await session.execute(finished)).all()
    added = {(row.id, row.field) for row in (await session.execute(_fields_added(since))).all()}
    resting: dict[uuid.UUID, set[str]] = {}
    for job in jobs:
        for facet in job.facets:
            if (job.id, CONCEPT_TYPE_DISCIPLINES.get(str(facet))) not in added:
                resting.setdefault(job.craftId, set()).add(str(facet))
    return {craft_id: frozenset(facets) for craft_id, facets in resting.items()}


def _fields_added(since: datetime) -> Select[tuple[uuid.UUID, str | None]]:
    written = and_(
        Claim.subjectType == CONCEPT_SUBJECT,
        Claim.subjectId == Concept.id,
        Claim.origin == WRITE_BACK_ORIGIN,
        Claim.createdAt >= EnrichmentJob.startedAt,
        Claim.createdAt <= EnrichmentJob.finishedAt,
    )
    return (
        select(EnrichmentJob.id, Claim.field)
        .join(Concept, Concept.craftId == EnrichmentJob.craftId)
        .join(Claim, written)
        .where(EnrichmentJob.createdAt >= since)
        .distinct()
    )
