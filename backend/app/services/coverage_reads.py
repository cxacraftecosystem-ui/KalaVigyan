from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Collection, Sequence
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput
from app.models import Claim, ClaimSource, ConditionReading, Craft, KnowledgePiece, ProcessCondition
from app.models.science import shown_reading
from app.research.knowledge_api import (
    CoverageSummary,
    FactFigure,
    FactQuantity,
    FactReading,
    SubjectCoverage,
    coverage_summary,
)
from app.research.open_work import OpenTask
from app.research.open_work_tasks import subject_tasks

from . import knowledge_view
from .coverage import coverage_of, subject_coverage
from .open_work import subject_standings
from .open_work_components import registered_pieces
from .open_work_subjects import CATEGORY, WorkSubject, craft_subject, craft_subjects, subject_by_key

__all__ = [
    "FACT_TASK_KINDS",
    "FIELD_TASK_KINDS",
    "FactDetails",
    "craft_field_work",
    "fact_details",
    "found_coverage",
    "read_subject_coverage",
    "subject_field_work",
]

FACT_TASK_KINDS = frozenset({"MISSING_FIELD", "THIN_FIELD"})
FIELD_TASK_KINDS = frozenset({"MISSING_FIELD", "THIN_FIELD", "SECTION"})
CRAFT = "craft"


@dataclass(frozen=True)
class FactDetails:
    quantities: dict[uuid.UUID, FactQuantity] = field(default_factory=dict)
    readings: dict[uuid.UUID, list[FactReading]] = field(default_factory=dict)
    figures: dict[uuid.UUID, list[FactFigure]] = field(default_factory=dict)


async def subject_field_work(
    session: AsyncSession,
    subject: WorkSubject,
    *,
    site: str,
    kinds: Collection[str],
    field: str | None = None,
) -> list[OpenTask]:
    (standing,) = await subject_standings(session, [subject], site=site)
    return [
        task
        for task in subject_tasks(standing)
        if task.kind in kinds and (field is None or task.field == field)
    ]


async def craft_field_work(
    session: AsyncSession, craft: Craft, *, site: str, kinds: Collection[str], field: str | None = None
) -> list[OpenTask]:
    try:
        subject = await craft_subject(session, craft.slug)
    except InvalidInput:
        return []
    return await subject_field_work(session, subject, site=site, kinds=kinds, field=field)


async def read_subject_coverage(session: AsyncSession, kind: str, slug: str, *, site: str) -> SubjectCoverage:
    subject = await _subject(session, kind, slug)
    return SubjectCoverage(
        coverage=await coverage_of(session, subject),
        open_work=await subject_field_work(session, subject, site=site, kinds=FIELD_TASK_KINDS),
        page_url=subject.task_subject(site).page_url,
    )


async def found_coverage(session: AsyncSession, slugs: Sequence[str]) -> dict[str, CoverageSummary]:
    if not slugs:
        return {}
    subjects = await craft_subjects(session, slugs)
    held = await subject_coverage(session, subjects)
    return {subject.slug: coverage_summary(held[subject.id]) for subject in subjects}


async def fact_details(session: AsyncSession, claim_ids: Sequence[uuid.UUID]) -> FactDetails:
    if not claim_ids:
        return FactDetails()
    wanted = list(dict.fromkeys(claim_ids))
    return FactDetails(
        quantities=await _quantities(session, wanted),
        readings=await _readings(session, wanted),
        figures=await _figures(session, wanted),
    )


async def _subject(session: AsyncSession, kind: str, slug: str) -> WorkSubject:
    if kind == CATEGORY:
        return await subject_by_key(session, CATEGORY, slug)
    craft = await knowledge_view.resolve_craft(session, slug)
    return await craft_subject(session, craft.slug if craft is not None else slug)


async def _quantities(session: AsyncSession, claim_ids: list[uuid.UUID]) -> dict[uuid.UUID, FactQuantity]:
    rows = await session.execute(
        select(Claim.id, Claim.valueNum, Claim.valueUnit).where(
            Claim.id.in_(claim_ids), Claim.valueNum.is_not(None), Claim.valueUnit.is_not(None)
        )
    )
    return {
        claim_id: FactQuantity(value=float(value), unit=str(unit)) for claim_id, value, unit in rows.all()
    }


async def _readings(session: AsyncSession, claim_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[FactReading]]:
    rows = await session.execute(
        select(
            ClaimSource.claimId,
            ProcessCondition.label,
            ConditionReading.stated,
            ConditionReading.statedMin,
            ConditionReading.statedMax,
            ConditionReading.statedUnit,
        )
        .join(ConditionReading, ConditionReading.claimSourceId == ClaimSource.id)
        .join(ProcessCondition, ProcessCondition.id == ConditionReading.conditionId)
        .where(ClaimSource.claimId.in_(claim_ids), shown_reading())
        .order_by(ClaimSource.claimId, ProcessCondition.label, ConditionReading.stated)
    )
    found: dict[uuid.UUID, list[FactReading]] = defaultdict(list)
    for claim_id, label, stated, low, high, unit in rows.all():
        found[claim_id].append(
            FactReading(
                label=label,
                stated=stated,
                low=None if low is None else float(low),
                high=None if high is None else float(high),
                unit=unit,
            )
        )
    return dict(found)


async def _figures(session: AsyncSession, claim_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[FactFigure]]:
    rows = await session.execute(
        select(KnowledgePiece.claimIds, KnowledgePiece.label, KnowledgePiece.kind, KnowledgePiece.title)
        .where(KnowledgePiece.claimIds.overlap(claim_ids), *registered_pieces())
        .order_by(KnowledgePiece.label)
    )
    wanted = set(claim_ids)
    found: dict[uuid.UUID, list[FactFigure]] = defaultdict(list)
    for rests_on, label, kind, title in rows.all():
        figure = FactFigure(label=str(label), kind=kind, title=title or str(label))
        for claim_id in wanted.intersection(rests_on or ()):
            found[claim_id].append(figure)
    return dict(found)
