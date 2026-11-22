from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import CTE, ColumnElement, and_, distinct, func, select, union_all
from sqlalchemy.dialects.postgresql import aggregate_order_by
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Answer, Claim, ClaimSource, Concept, CuratedCategoryClaim, Source, WebFetch
from app.research.open_work import TASK_ITEMS_MAX, Items
from app.research.open_work_links import ARCHIVED_URL_KEY, SourceLink
from app.research.retrieval import SHOWN_CLAIM_STATUSES, VISIBLE_SENSITIVITY
from app.research.vocabulary import FACT_LEVELS
from app.retrieval.citation_access import reader_fact

__all__ = ["Owners", "SubjectCounts", "owned_claims", "owned_facts", "subject_counts"]

CONCEPT_SUBJECT = "CONCEPT"
ONE_SOURCE = 1

FieldItems = dict[uuid.UUID, dict[str | None, Items]]


@dataclass(frozen=True)
class Owners:
    crafts: tuple[uuid.UUID, ...]
    categories: tuple[uuid.UUID, ...]


@dataclass(frozen=True)
class SubjectCounts:
    one_source: FieldItems = field(default_factory=dict)
    differing: FieldItems = field(default_factory=dict)
    links: dict[uuid.UUID, list[SourceLink]] = field(default_factory=dict)
    demand: dict[uuid.UUID, int] = field(default_factory=dict)


async def subject_counts(session: AsyncSession, owners: Owners) -> SubjectCounts:
    owned = owned_facts(owners)
    per_fact = _per_fact(owned)
    return SubjectCounts(
        one_source=await _field_items(session, per_fact, per_fact.c.sources == ONE_SOURCE),
        differing=await _field_items(session, per_fact, per_fact.c.differ.is_(True)),
        links=await _source_links(session, owned),
        demand=await _demand(session, owners.crafts),
    )


def owned_facts(owners: Owners) -> CTE:
    return owned_claims(owners, and_(*reader_fact()))


def owned_claims(owners: Owners, condition: ColumnElement[bool]) -> CTE:
    columns = (Claim.id.label("claim"), Claim.field.label("field"), Claim.fields, Claim.sourcesDiffer)
    of_crafts = (
        select(Concept.craftId.label("owner"), *columns)
        .join(Concept, and_(Claim.subjectType == CONCEPT_SUBJECT, Claim.subjectId == Concept.id))
        .where(
            Concept.craftId.in_(owners.crafts),
            Concept.sensitivity == VISIBLE_SENSITIVITY,
            *_fact_conditions(),
            condition,
        )
    )
    of_categories = (
        select(CuratedCategoryClaim.categoryId.label("owner"), *columns)
        .join(Claim, Claim.id == CuratedCategoryClaim.claimId)
        .where(CuratedCategoryClaim.categoryId.in_(owners.categories), *_fact_conditions(), condition)
    )
    return union_all(of_crafts, of_categories).cte("owned")


def _fact_conditions() -> list[ColumnElement[bool]]:
    return [
        Claim.status.in_(SHOWN_CLAIM_STATUSES),
        Claim.evidenceLevel.in_(FACT_LEVELS),
        Claim.sensitivity == VISIBLE_SENSITIVITY,
    ]


def _per_fact(owned: CTE) -> Any:
    sources = func.count(distinct(ClaimSource.sourceId)).label("sources")
    return (
        select(owned.c.owner, owned.c.claim, owned.c.field, owned.c.sourcesDiffer.label("differ"), sources)
        .join(ClaimSource, ClaimSource.claimId == owned.c.claim)
        .group_by(owned.c.owner, owned.c.claim, owned.c.field, owned.c.sourcesDiffer)
        .subquery("per_fact")
    )


async def _field_items(session: AsyncSession, per_fact: Any, condition: ColumnElement[bool]) -> FieldItems:
    ids = func.array_agg(aggregate_order_by(per_fact.c.claim, per_fact.c.claim))
    rows = await session.execute(
        select(per_fact.c.owner, per_fact.c.field, func.count(), ids[1:TASK_ITEMS_MAX])
        .where(condition)
        .group_by(per_fact.c.owner, per_fact.c.field)
    )
    found: FieldItems = defaultdict(dict)
    for owner, discipline, count, first in rows.all():
        found[owner][discipline] = Items(count=int(count), ids=tuple(str(claim_id) for claim_id in first))
    return dict(found)


async def _source_links(session: AsyncSession, owned: CTE) -> dict[uuid.UUID, list[SourceLink]]:
    cited = (
        select(owned.c.owner, ClaimSource.sourceId)
        .join(ClaimSource, ClaimSource.claimId == owned.c.claim)
        .distinct()
        .subquery("cited")
    )
    rows = (
        await session.execute(
            select(
                cited.c.owner,
                Source.id,
                Source.url,
                Source.snapshotKey,
                Source.externalIds[ARCHIVED_URL_KEY].astext,
            )
            .join(Source, Source.id == cited.c.sourceId)
            .where(Source.url.is_not(None))
            .order_by(cited.c.owner, Source.id)
        )
    ).all()
    statuses = await _last_statuses(session, sorted({row[2] for row in rows}))
    found: dict[uuid.UUID, list[SourceLink]] = defaultdict(list)
    for owner, source_id, url, snapshot, archived_url in rows:
        archived = snapshot is not None or archived_url is not None
        found[owner].append(SourceLink(str(source_id), archived=archived, last_status=statuses.get(url)))
    return dict(found)


async def _last_statuses(session: AsyncSession, urls: Sequence[str]) -> dict[str, int | None]:
    if not urls:
        return {}
    rows = await session.execute(
        select(WebFetch.url, WebFetch.status)
        .where(WebFetch.url.in_(list(urls)))
        .distinct(WebFetch.url)
        .order_by(WebFetch.url, WebFetch.fetchedAt.desc().nulls_last(), WebFetch.createdAt.desc())
    )
    return {str(url): status for url, status in rows.all()}


async def _demand(session: AsyncSession, crafts: Sequence[uuid.UUID]) -> dict[uuid.UUID, int]:
    if not crafts:
        return {}
    rows = await session.execute(
        select(Answer.craftId, func.count()).where(Answer.craftId.in_(list(crafts))).group_by(Answer.craftId)
    )
    return {craft_id: int(count) for craft_id, count in rows.all()}
