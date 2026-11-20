from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace

from sqlalchemy import CTE, ColumnElement, and_, exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Claim, ClaimSource
from app.models.enums import DISCIPLINES
from app.research.open_work import NO_ITEMS, Items, OpenTask, SubjectStanding, task_key
from app.research.open_work_tasks import subject_priority

from .claim_holds import corroborated_claim, held_claim
from .open_work_counts import Owners, owned_claims
from .open_work_healing_texts import Wording, corroborate_wording, resource_wording, rotten_wording
from .upkeep_links import rotten_source_ids

__all__ = [
    "CORROBORATE_FACT",
    "FIND_ANOTHER_SOURCE",
    "HEALING_KINDS",
    "RESOURCE_FACT",
    "Healing",
    "healing_tasks",
    "rests_on_rot",
    "subject_healing",
    "with_healing",
]

RESOURCE_FACT = "RESOURCE_FACT"
CORROBORATE_FACT = "CORROBORATE_FACT"
FIND_ANOTHER_SOURCE = "FIND_ANOTHER_SOURCE"
HEALING_KINDS = (RESOURCE_FACT, CORROBORATE_FACT, FIND_ANOTHER_SOURCE)
FIELD_RANK = {discipline: rank for rank, discipline in enumerate(DISCIPLINES)}

FieldItems = dict[uuid.UUID, dict[str | None, Items]]


@dataclass(frozen=True)
class Healing:
    held: Mapping[str | None, Items] = field(default_factory=dict)
    failing: Mapping[str | None, Items] = field(default_factory=dict)
    rotten_facts: Items = NO_ITEMS
    rotten_sources: Items = NO_ITEMS


def rests_on_rot() -> ColumnElement[bool]:
    rotten = rotten_source_ids()
    cites_rot = exists().where(ClaimSource.claimId == Claim.id, ClaimSource.sourceId.in_(rotten))
    cites_other = exists().where(ClaimSource.claimId == Claim.id, ClaimSource.sourceId.not_in(rotten))
    return and_(cites_rot, ~cites_other)


async def subject_healing(session: AsyncSession, owners: Owners) -> dict[uuid.UUID, Healing]:
    held = await _by_field(session, owned_claims(owners, held_claim()))
    failing = await _by_field(session, owned_claims(owners, corroborated_claim()))
    rotten = owned_claims(owners, and_(~held_claim(), rests_on_rot()))
    facts, sources = await _rotten_facts(session, rotten), await _rotten_sources(session, rotten)
    return {
        owner: Healing(
            held=held.get(owner, {}),
            failing=failing.get(owner, {}),
            rotten_facts=facts.get(owner, NO_ITEMS),
            rotten_sources=sources.get(owner, NO_ITEMS),
        )
        for owner in {*held, *failing, *facts}
    }


def with_healing(standing: SubjectStanding, healing: Healing | None) -> SubjectStanding:
    if healing is None:
        return standing
    return replace(standing, healing=tuple(healing_tasks(standing, healing)))


def healing_tasks(standing: SubjectStanding, healing: Healing) -> list[OpenTask]:
    found = [
        _task(standing, RESOURCE_FACT, discipline, resource_wording(standing.subject.name, discipline, items))
        for discipline, items in _ordered(healing.held)
    ]
    found += [
        _task(
            standing,
            CORROBORATE_FACT,
            discipline,
            corroborate_wording(standing.subject.name, discipline, items),
        )
        for discipline, items in _ordered(healing.failing)
    ]
    if healing.rotten_facts.count:
        wording = rotten_wording(standing.subject.name, healing.rotten_facts, healing.rotten_sources)
        found.append(_task(standing, FIND_ANOTHER_SOURCE, None, wording))
    return found


def _task(standing: SubjectStanding, kind: str, discipline: str | None, wording: Wording) -> OpenTask:
    return OpenTask(
        key=task_key(kind, standing.subject, discipline),
        kind=kind,
        priority=subject_priority(standing),
        subject=standing.subject,
        field=discipline,
        needed=wording.needed,
        acceptance=wording.acceptance,
        count=wording.facts.count,
        fact_ids=[uuid.UUID(claim_id) for claim_id in wording.facts.ids],
        source_ids=list(wording.sources.ids),
    )


def _ordered(by_field: Mapping[str | None, Items]) -> list[tuple[str | None, Items]]:
    ranked = sorted(by_field, key=lambda discipline: FIELD_RANK.get(discipline or "", len(FIELD_RANK)))
    return [(discipline, by_field[discipline]) for discipline in ranked if by_field[discipline].count]


async def _by_field(session: AsyncSession, owned: CTE) -> FieldItems:
    rows = await session.execute(
        select(owned.c.owner, owned.c.field, owned.c.claim)
        .distinct()
        .order_by(owned.c.owner, owned.c.field, owned.c.claim)
    )
    grouped: dict[uuid.UUID, dict[str | None, list[str]]] = defaultdict(lambda: defaultdict(list))
    for owner, discipline, claim_id in rows.all():
        grouped[owner][discipline].append(str(claim_id))
    return {
        owner: {discipline: Items.of(ids) for discipline, ids in fields.items()}
        for owner, fields in grouped.items()
    }


async def _rotten_facts(session: AsyncSession, owned: CTE) -> dict[uuid.UUID, Items]:
    rows = await session.execute(
        select(owned.c.owner, owned.c.claim).distinct().order_by(owned.c.owner, owned.c.claim)
    )
    return _grouped((owner, str(claim_id)) for owner, claim_id in rows.all())


async def _rotten_sources(session: AsyncSession, owned: CTE) -> dict[uuid.UUID, Items]:
    rows = await session.execute(
        select(owned.c.owner, ClaimSource.sourceId)
        .join(ClaimSource, ClaimSource.claimId == owned.c.claim)
        .where(ClaimSource.sourceId.in_(rotten_source_ids()))
        .distinct()
        .order_by(owned.c.owner, ClaimSource.sourceId)
    )
    return _grouped((owner, str(source_id)) for owner, source_id in rows.all())


def _grouped(pairs: Iterable[tuple[uuid.UUID, str]]) -> dict[uuid.UUID, Items]:
    grouped: dict[uuid.UUID, list[str]] = defaultdict(list)
    for owner, item in pairs:
        grouped[owner].append(item)
    return {owner: Items.of(items) for owner, items in grouped.items()}
