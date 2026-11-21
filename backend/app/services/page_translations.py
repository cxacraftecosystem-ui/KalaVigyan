from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput, Refused
from app.core.roles import PROFESSOR, has_rank
from app.models import PageTranslation, User
from app.research.monograph_page import MonographContent
from app.research.page_proposals import ACCEPTED, REFUSED, TRANSLATION, PartReport
from app.research.page_translation_gates import (
    GateInput,
    TranslationCheck,
    checks_passed,
    refusal,
    translation_checks,
)
from app.research.page_translation_texts import NO_PAGE, NO_PASSAGE, placed_message
from app.research.page_translations import PageTranslationPart, PassageTranslation, task_problem
from app.research.review_switch import PUBLISHED, ReviewSwitch, refused_placement
from app.research.translation_passages import is_translatable, passage_leaves, passage_text, unit_hash
from app.research.trust_tiers import SWITCH, TierPlacement, drawn_for_review, tier_placement

from . import app_settings, trust_tiers
from .fact_proposals import role_now
from .open_work_subjects import WorkSubject
from .page_english import english_page
from .page_text_index import PageKey, refresh_page_texts
from .page_translation_store import remaining_passages, supersede_others
from .task_reservations import complete_task
from .translation_readers import reads_language

__all__ = ["checked_translation", "translation_reports"]


@dataclass(frozen=True)
class _Proposer:
    user: User
    origin: str
    tier: str
    reviews: bool
    switch: ReviewSwitch


@dataclass(frozen=True)
class _Batch:
    page: PageKey
    part: PageTranslationPart
    content: MonographContent
    proposer: _Proposer
    batch_id: uuid.UUID
    now: datetime


async def checked_translation(
    session: AsyncSession,
    user: User,
    subject: WorkSubject,
    part: PageTranslationPart,
    *,
    origin: str,
    now: datetime,
) -> list[PartReport]:
    try:
        async with session.begin_nested():
            return await translation_reports(session, user, subject, part, origin=origin, now=now)
    except (InvalidInput, Refused) as problem:
        message = problem.message if isinstance(problem, Refused) else str(problem)
        return [_refused(index, message) for index in range(len(part.passages))]


async def translation_reports(
    session: AsyncSession,
    user: User,
    subject: WorkSubject,
    part: PageTranslationPart,
    *,
    origin: str,
    now: datetime,
) -> list[PartReport]:
    page = (subject.kind, subject.slug)
    problem = task_problem(part.task_key, page, part.language)
    english = None if problem is not None else await english_page(session, page)
    if english is None:
        return [_refused(index, problem or NO_PAGE) for index in range(len(part.passages))]
    await refresh_page_texts(session, page, english.tag, english.document.content, now=now)
    batch = _Batch(
        page, part, english.document.content, await _proposer(session, user, part, origin), uuid.uuid4(), now
    )
    reports = [
        await _passage_report(session, batch, index, passage) for index, passage in enumerate(part.passages)
    ]
    taken = any(report.outcome == ACCEPTED for report in reports)
    if part.task_key is not None and taken:
        left = await remaining_passages(session, page, part.language, english.document.content)
        if left == 0:
            await complete_task(session, user.id, part.task_key, now=now)
    return reports


async def _proposer(session: AsyncSession, user: User, part: PageTranslationPart, origin: str) -> _Proposer:
    role = await role_now(session, user.id)
    standing = await trust_tiers.account_standing(session, user.id)
    reviews = has_rank(role, PROFESSOR) and await reads_language(session, user.id, part.language)
    switch = await app_settings.review_switch(session)
    return _Proposer(user=user, origin=origin, tier=standing.tier, reviews=reviews, switch=switch)


async def _passage_report(
    session: AsyncSession, batch: _Batch, index: int, passage: PassageTranslation
) -> PartReport:
    unit = batch.content.units.get(passage.key)
    if unit is None or not is_translatable(passage.key, unit.nodes):
        return _refused(index, NO_PASSAGE.format(key=passage.key))
    leaves = passage_leaves(unit.nodes)
    given = GateInput(
        leaves=leaves,
        current_hash=unit_hash(unit.nodes, unit.claim_ids),
        given_hash=passage.source_hash,
        texts=passage.texts,
        language=batch.part.language,
    )
    checks = translation_checks(given)
    row_id = uuid.uuid4()
    placed = _placed(batch.proposer, checks_passed(checks), row_id)
    row = _row(batch, passage, (row_id, passage_text(leaves)), checks, placed)
    session.add(row)
    await session.flush()
    if placed.placed.outcome == PUBLISHED:
        await supersede_others(session, row)
    failed = refusal(checks)
    message = placed_message(placed, batch.part.language, failed)
    outcome = REFUSED if failed is not None else ACCEPTED
    return PartReport(
        part=TRANSLATION, index=index, outcome=outcome, status=row.status, id=str(row.id), message=message
    )


def _placed(proposer: _Proposer, passed: bool, row_id: uuid.UUID) -> TierPlacement:
    if not passed:
        return TierPlacement(refused_placement(), SWITCH)
    return tier_placement(
        proposer.switch.mode(proposer.origin),
        proposer_reviews=proposer.reviews,
        tier=proposer.tier,
        drawn=drawn_for_review(row_id),
    )


def _row(
    batch: _Batch,
    passage: PassageTranslation,
    made: tuple[uuid.UUID, str],
    checks: list[TranslationCheck],
    placed: TierPlacement,
) -> PageTranslation:
    row_id, english = made
    kind, slug = batch.page
    approved = placed.placed.approved_at_once
    proposer = batch.proposer
    return PageTranslation(
        id=row_id,
        batchId=batch.batch_id,
        subjectKind=kind,
        subjectSlug=slug,
        language=batch.part.language,
        unitKey=passage.key,
        sourceHash=passage.source_hash,
        english=english,
        texts=list(passage.texts),
        checks=[check.model_dump(mode="json") for check in checks],
        status=placed.placed.status,
        placedBy=placed.why,
        origin=proposer.origin,
        proposerId=proposer.user.id,
        taskKey=batch.part.task_key,
        note=batch.part.note,
        reviewedById=proposer.user.id if approved else None,
        reviewedAt=batch.now if approved else None,
        createdAt=batch.now,
    )


def _refused(index: int, message: str) -> PartReport:
    return PartReport(part=TRANSLATION, index=index, outcome=REFUSED, message=message)
