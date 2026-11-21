from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput, Refused
from app.core.roles import PROFESSOR, has_rank
from app.models import PageTextUnit, PageTranslation, User
from app.research.page_proposals import PageSubject
from app.research.page_translation_gates import TranslationCheck
from app.research.page_translation_views import ReviewItem, ReviewList
from app.research.page_translations import WAITING_TRANSLATION_STATUSES
from app.research.review_switch import APPROVED_STATUS, REFUSED_STATUS
from app.research.vocabulary import ANSWER_LANGUAGE_SPECS

from .page_translation_store import supersede_others
from .translation_readers import NOT_A_REVIEWER, reader_languages

__all__ = ["REVIEW_LIMIT_DEFAULT", "approve_translation", "reject_translation", "review_list"]

REVIEW_LIMIT_DEFAULT = 50
NOT_WAITING = "not_waiting"
OWN = "own_translation"
NO_TRANSLATION = "No translation waiting for review has the id {translation_id}."
REVIEWERS_ONLY = "Only a Professor or Admin who reads {label} reviews translations into it."
DECIDED = "That translation was decided already ({status}); it waits for no review."
YOUR_OWN = "A translation is reviewed by someone other than the person who proposed it."
NOTE_NEEDED = "Say why the translation is rejected, so its translator can mend it."


async def review_list(session: AsyncSession, reviewer: User, *, limit: int, site: str) -> ReviewList:
    languages = await reader_languages(session, reviewer.id)
    if not has_rank(reviewer, PROFESSOR) or not languages:
        return ReviewList(languages=list(languages), total=0, items=[])
    waiting = (
        PageTranslation.language.in_(languages),
        PageTranslation.status.in_(WAITING_TRANSLATION_STATUSES),
    )
    total = await session.scalar(select(func.count()).select_from(PageTranslation).where(*waiting))
    rows = await session.execute(
        select(PageTranslation, PageTextUnit.sourceHash)
        .outerjoin(
            PageTextUnit,
            (PageTextUnit.subjectKind == PageTranslation.subjectKind)
            & (PageTextUnit.subjectSlug == PageTranslation.subjectSlug)
            & (PageTextUnit.unitKey == PageTranslation.unitKey),
        )
        .where(*waiting)
        .order_by(PageTranslation.createdAt, PageTranslation.id)
        .limit(limit)
    )
    items = [_item(row, indexed, site) for row, indexed in rows.all()]
    return ReviewList(languages=list(languages), total=int(total or 0), items=items)


def _item(row: PageTranslation, indexed: str | None, site: str) -> ReviewItem:
    path = "categories" if row.subjectKind == "category" else "crafts"
    return ReviewItem(
        id=row.id,
        subject=PageSubject(kind=row.subjectKind, slug=row.subjectSlug),
        language=row.language,
        key=row.unitKey,
        status=row.status,
        english=row.english,
        texts=list(row.texts),
        current=indexed is None or indexed == row.sourceHash,
        checks=[TranslationCheck.model_validate(check) for check in row.checks],
        note=row.note,
        created_at=row.createdAt,
        page_url=f"{site}/{path}/{row.subjectSlug}/{row.language}",
    )


async def approve_translation(
    session: AsyncSession, reviewer: User, translation_id: uuid.UUID, *, note: str | None, now: datetime
) -> PageTranslation:
    row = await _reviewable(session, reviewer, translation_id)
    _decide(row, reviewer, (APPROVED_STATUS, note), now)
    await session.flush()
    await supersede_others(session, row)
    return row


async def reject_translation(
    session: AsyncSession, reviewer: User, translation_id: uuid.UUID, *, note: str | None, now: datetime
) -> PageTranslation:
    if note is None:
        raise InvalidInput(NOTE_NEEDED)
    row = await _reviewable(session, reviewer, translation_id)
    _decide(row, reviewer, (REFUSED_STATUS, note), now)
    await session.flush()
    return row


async def _reviewable(session: AsyncSession, reviewer: User, translation_id: uuid.UUID) -> PageTranslation:
    row = await session.get(PageTranslation, translation_id, with_for_update=True)
    if row is None:
        raise InvalidInput(NO_TRANSLATION.format(translation_id=translation_id))
    label = ANSWER_LANGUAGE_SPECS[row.language].label
    if not has_rank(reviewer, PROFESSOR) or row.language not in await reader_languages(session, reviewer.id):
        raise Refused(NOT_A_REVIEWER, REVIEWERS_ONLY.format(label=label))
    if row.status not in WAITING_TRANSLATION_STATUSES:
        raise Refused(NOT_WAITING, DECIDED.format(status=row.status))
    if row.proposerId == reviewer.id:
        raise Refused(OWN, YOUR_OWN)
    return row


def _decide(row: PageTranslation, reviewer: User, decision: tuple[str, str | None], now: datetime) -> None:
    status, note = decision
    row.status = status
    row.reviewedById = reviewer.id
    row.reviewedAt = now
    row.reviewNote = note
