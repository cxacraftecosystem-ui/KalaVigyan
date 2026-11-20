from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from types import MappingProxyType
from typing import Any

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.curation.limits import CURATED_QUOTE_MIN_CHARS, DISCIPLINE_CLAIMS_MIN, SECTION_SENTENCES_MIN
from app.models import (
    ArtisanContribution,
    Claim,
    ComponentProposal,
    ImageContribution,
    LayoutProposal,
    StructureProposal,
    TaskReservation,
)
from app.models.enums import DISCIPLINES
from app.models.knowledge import QUOTE_MAX_CHARS
from app.models.open_work import LIVE_PROPOSALS
from app.research.coverage import FieldCount, FieldCoverage
from app.research.open_work import (
    NO_ITEMS,
    RESERVATION_TIME,
    CoverageTargets,
    FieldStanding,
    Hold,
    Items,
    OpenTask,
    OpenWork,
    QueueStanding,
    SubjectStanding,
    TaskKey,
    Viewer,
    WorkFilters,
)
from app.research.open_work_links import DEAD_SOURCE, UNARCHIVED_SOURCE, sources_in_state
from app.research.open_work_tasks import chosen_tasks, open_tasks, reviewed_queues, subject_tasks

from .claim_holds import held_in_queue
from .coverage import owners_of, subject_coverage
from .open_work_components import craft_component_kinds
from .open_work_counts import SubjectCounts, subject_counts
from .open_work_healing import Healing, subject_healing, with_healing
from .open_work_pages import monograph_layouts
from .open_work_subjects import CATEGORY, WorkSubject, subject_by_key, work_subjects

__all__ = [
    "RESERVATION_MINUTES",
    "SUBJECT_TARGETS",
    "list_open_work",
    "live_holds",
    "open_task",
    "proposed_tasks",
    "review_queues",
    "subject_standings",
]

CRAFT_TARGETS = CoverageTargets(
    core_fields=DISCIPLINES,
    facts_min=DISCIPLINE_CLAIMS_MIN,
    section_sentences_min=SECTION_SENTENCES_MIN,
    quote_chars_min=CURATED_QUOTE_MIN_CHARS,
    quote_chars_max=QUOTE_MAX_CHARS,
    components=True,
)
SUBJECT_TARGETS: Mapping[str, CoverageTargets] = MappingProxyType(
    {
        "craft": CRAFT_TARGETS,
        "family": CRAFT_TARGETS,
        CATEGORY: replace(CRAFT_TARGETS, components=False),
    }
)
RESERVATION_MINUTES = int(RESERVATION_TIME.total_seconds() // 60)
PENDING = "PENDING"
FACT_REVIEW_STATUSES = ("PROPOSED", "IN_REVIEW")


@dataclass(frozen=True)
class _Gathered:
    counts: SubjectCounts
    coverage: Mapping[uuid.UUID, FieldCoverage]
    kinds: Mapping[uuid.UUID, frozenset[str]]
    layouts: Mapping[str, bool]
    site: str
    healing: Mapping[uuid.UUID, Healing]


async def list_open_work(
    session: AsyncSession, filters: WorkFilters, viewer: Viewer, *, site: str, now: datetime
) -> OpenWork:
    subjects = await work_subjects(session, filters.subject_filter())
    standings = await subject_standings(session, subjects, site=site)
    reviewed = reviewed_queues(viewer.review_role) if filters.subject_filter() is None else ()
    queues = await review_queues(session, reviewed)
    kept = chosen_tasks(
        open_tasks(standings, queues, viewer),
        filters,
        holds=await live_holds(session, now=now),
        closed=await proposed_tasks(session),
        viewer=viewer,
        now=now,
    )
    return OpenWork(
        filters=filters, total=len(kept), reservation_minutes=RESERVATION_MINUTES, tasks=kept[: filters.limit]
    )


async def open_task(session: AsyncSession, key: TaskKey, *, site: str) -> OpenTask | None:
    if key.subject_kind is None or key.slug is None:
        return None
    subject = await subject_by_key(session, key.subject_kind, key.slug)
    standings = await subject_standings(session, [subject], site=site)
    wanted = key.text()
    return next((task for task in subject_tasks(standings[0]) if task.key == wanted), None)


async def subject_standings(
    session: AsyncSession, subjects: Sequence[WorkSubject], *, site: str
) -> list[SubjectStanding]:
    owners = owners_of(subjects)
    gathered = _Gathered(
        counts=await subject_counts(session, owners),
        coverage=await subject_coverage(session, subjects),
        kinds=await craft_component_kinds(session, owners.crafts),
        layouts=monograph_layouts(),
        site=site,
        healing=await subject_healing(session, owners),
    )
    return [
        with_healing(_standing(subject, gathered), gathered.healing.get(subject.id)) for subject in subjects
    ]


async def review_queues(session: AsyncSession, queues: Sequence[str]) -> dict[str, QueueStanding]:
    waiting: dict[str, tuple[Any, ColumnElement[bool]]] = {
        "FACTS": (Claim.createdAt, or_(Claim.status.in_(FACT_REVIEW_STATUSES), held_in_queue())),
        "TESTIMONY": (ArtisanContribution.createdAt, ArtisanContribution.status == PENDING),
        "IMAGES": (ImageContribution.createdAt, ImageContribution.status == PENDING),
        "COMPONENTS": (ComponentProposal.createdAt, ComponentProposal.status == PENDING),
        "LAYOUTS": (LayoutProposal.createdAt, LayoutProposal.status == PENDING),
        "STRUCTURE": (StructureProposal.createdAt, StructureProposal.status == PENDING),
    }
    return {queue: await _queue(session, *waiting[queue]) for queue in queues}


async def live_holds(session: AsyncSession, *, now: datetime) -> dict[str, Hold]:
    rows = await session.execute(
        select(TaskReservation.taskKey, TaskReservation.userId, TaskReservation.expiresAt).where(
            TaskReservation.endedAt.is_(None), TaskReservation.expiresAt > now
        )
    )
    return {key: Hold(user_id=user_id, expires_at=expires) for key, user_id, expires in rows.all()}


async def proposed_tasks(session: AsyncSession) -> frozenset[str]:
    keys = await session.scalars(
        select(ComponentProposal.taskKey).where(
            ComponentProposal.taskKey.is_not(None), ComponentProposal.status.in_(LIVE_PROPOSALS)
        )
    )
    return frozenset(key for key in keys.all() if key is not None)


async def _queue(session: AsyncSession, created: Any, condition: ColumnElement[bool]) -> QueueStanding:
    count, oldest = (await session.execute(select(func.count(), func.min(created)).where(condition))).one()
    return QueueStanding(count=int(count), oldest=oldest)


def _standing(subject: WorkSubject, gathered: _Gathered) -> SubjectStanding:
    counts = gathered.counts
    links = counts.links.get(subject.id, [])
    return SubjectStanding(
        subject=subject.task_subject(gathered.site),
        targets=SUBJECT_TARGETS[subject.kind],
        fields=_fields(subject.id, counts, gathered.coverage.get(subject.id)),
        component_kinds=gathered.kinds.get(subject.id, frozenset()),
        new_form=subject.slug in gathered.layouts,
        layout=gathered.layouts.get(subject.slug, False),
        dead_sources=sources_in_state(links, DEAD_SOURCE),
        unarchived_sources=sources_in_state(links, UNARCHIVED_SOURCE),
        gi=subject.gi,
        curated=subject.curated,
        demand=counts.demand.get(subject.id, 0),
    )


def _fields(
    owner: uuid.UUID, counts: SubjectCounts, coverage: FieldCoverage | None
) -> dict[str | None, FieldStanding]:
    held = (
        {count.field: count for count in coverage.fields if count.claims or count.sections}
        if coverage
        else {}
    )
    one_source = counts.one_source.get(owner, {})
    differing = counts.differing.get(owner, {})
    filed: set[str | None] = {*held, *one_source, *differing}
    return {
        discipline: _field_standing(
            held.get(discipline) if discipline else None,
            one_source.get(discipline, NO_ITEMS),
            differing.get(discipline, NO_ITEMS),
        )
        for discipline in filed
    }


def _field_standing(count: FieldCount | None, one_source: Items, differing: Items) -> FieldStanding:
    return FieldStanding(
        facts=count.claims if count is not None else 0,
        section_sentences=count.sentences if count is not None else 0,
        one_source=one_source,
        differing=differing,
    )
