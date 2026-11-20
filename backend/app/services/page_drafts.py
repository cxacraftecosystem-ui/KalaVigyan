from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from datetime import datetime

from pydantic import ValidationError
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput
from app.models import PageDraft, SuppliedSource, User
from app.research.page_drafts import (
    DRAFT_BYTES_MAX,
    DRAFT_LIFETIME,
    DRAFTS_OPEN_MAX,
    OPEN,
    SUBMITTED,
    DraftAddition,
    DraftParts,
    DraftPreviewLink,
    DraftView,
    draft_bundle,
    part_summaries,
    parts_counts,
    with_added,
    without,
)
from app.research.page_proposals import PageBundle, PagePreviewResult, PageProposalResult, PageSubject
from app.research.page_report import PageReport

from .open_work_subjects import subject_by_key

__all__ = [
    "UNKNOWN_DRAFT",
    "add_to_draft",
    "attach_supplied",
    "bundle_of",
    "create_draft",
    "draft_view",
    "held_parts",
    "own_draft",
    "record_preview",
    "record_submission",
    "remove_from_draft",
    "subject_of",
]

UNKNOWN_DRAFT = (
    "No open draft of yours has the id {draft_id}; create_draft makes one, or gives back the one you hold."
)
SUBMITTED_DRAFT = "The draft {draft_id} was submitted; create_draft starts a new one for the page."
TOO_MANY = (
    "This account holds {held} open drafts, the most one account may; submit one, or let one expire, first."
)
TOO_LARGE = (
    "The draft would hold {size} bytes, more than the {limit} a draft may; submit it, or split the page."
)
EMPTY = "The draft holds no part yet; add_to_draft adds facts, structure, components, a layout or pictures."
NOT_YOURS = "These supplied sources are not this account's: {ids}; supply_source gives each one its id."


async def create_draft(
    session: AsyncSession, user: User, subject: PageSubject, *, now: datetime
) -> PageDraft:
    found = await subject_by_key(session, subject.kind, subject.slug)
    await _prune(session, user.id, now)
    held = await _open(session, user.id, found.kind, found.slug)
    if held is not None:
        return held
    count = await session.scalar(
        select(func.count())
        .select_from(PageDraft)
        .where(PageDraft.userId == user.id, PageDraft.state == OPEN)
    )
    if (count or 0) >= DRAFTS_OPEN_MAX:
        raise InvalidInput(TOO_MANY.format(held=count))
    row = PageDraft(
        id=uuid.uuid4(),
        userId=user.id,
        subjectKind=found.kind,
        subjectSlug=found.slug,
        state=OPEN,
        parts={},
        bytes=0,
        version=1,
        expiresAt=now + DRAFT_LIFETIME,
        createdAt=now,
        updatedAt=now,
    )
    session.add(row)
    await session.flush()
    return row


async def own_draft(
    session: AsyncSession,
    user: User,
    draft_id: uuid.UUID,
    *,
    now: datetime,
    lock: bool = False,
    open_only: bool = True,
) -> PageDraft:
    query = select(PageDraft).where(PageDraft.id == draft_id, PageDraft.userId == user.id)
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    row = await session.scalar(query)
    if row is None or row.expiresAt <= now:
        raise InvalidInput(UNKNOWN_DRAFT.format(draft_id=draft_id))
    if open_only and row.state != OPEN:
        raise InvalidInput(SUBMITTED_DRAFT.format(draft_id=draft_id))
    return row


async def add_to_draft(
    session: AsyncSession, user: User, draft_id: uuid.UUID, added: DraftAddition, *, now: datetime
) -> PageDraft:
    row = await own_draft(session, user, draft_id, now=now, lock=True)
    await _refuse_foreign_sources(session, user.id, added.supplied_sources)
    _write(row, _parts_or_refusal(lambda: with_added(held_parts(row), added)), now)
    await session.flush()
    return row


async def remove_from_draft(
    session: AsyncSession, user: User, draft_id: uuid.UUID, removed: tuple[str, int], *, now: datetime
) -> PageDraft:
    row = await own_draft(session, user, draft_id, now=now, lock=True)
    part, index = removed
    _write(row, _parts_or_refusal(lambda: without(held_parts(row), part, index)), now)
    await session.flush()
    return row


async def attach_supplied(
    session: AsyncSession, user: User, draft_id: uuid.UUID, supplied_id: uuid.UUID, *, now: datetime
) -> PageDraft:
    return await add_to_draft(session, user, draft_id, DraftAddition(supplied_sources=[supplied_id]), now=now)


async def record_preview(
    session: AsyncSession, row: PageDraft, previewed: PagePreviewResult, report: PageReport | None
) -> None:
    row.previewUrl = previewed.preview_url
    row.previewExpiresAt = previewed.expires_at
    row.report = None if report is None else report.model_dump(mode="json", by_alias=True)
    await session.flush()


async def record_submission(
    session: AsyncSession, row: PageDraft, result: PageProposalResult, *, now: datetime
) -> None:
    row.state = SUBMITTED
    row.submittedAt = now
    row.result = result.model_dump(mode="json", by_alias=True)
    row.version += 1
    await session.flush()


def held_parts(row: PageDraft) -> DraftParts:
    return DraftParts.model_validate(row.parts or {})


def subject_of(row: PageDraft) -> PageSubject:
    return PageSubject(kind=row.subjectKind, slug=row.subjectSlug)


def draft_view(row: PageDraft, *, message: str, next_step: str, full: bool = False) -> DraftView:
    parts = held_parts(row)
    return DraftView(
        draft_id=row.id,
        subject=subject_of(row),
        state=row.state,
        version=row.version,
        updated_at=row.updatedAt,
        expires_at=row.expiresAt,
        bytes=row.bytes,
        counts=parts_counts(parts),
        parts=part_summaries(parts),
        lists=parts.lists,
        preview=_preview(row),
        result=PageProposalResult.model_validate(row.result) if row.result else None,
        draft=parts if full else None,
        message=message,
        next_step=next_step,
    )


def bundle_of(row: PageDraft) -> PageBundle:
    try:
        return draft_bundle(subject_of(row), held_parts(row))
    except ValidationError as refused:
        raise InvalidInput(EMPTY if not row.parts else _problems(refused)) from None


def _preview(row: PageDraft) -> DraftPreviewLink | None:
    if row.previewUrl is None or row.previewExpiresAt is None:
        return None
    report = row.report or {}
    return DraftPreviewLink(
        url=row.previewUrl,
        expires_at=row.previewExpiresAt,
        passed=int(report.get("passed", 0)),
        failed=int(report.get("failed", 0)),
        judged=int(report.get("judged", 0)),
    )


def _write(row: PageDraft, parts: DraftParts, now: datetime) -> None:
    dumped = parts.model_dump(mode="json", by_alias=True)
    size = len(json.dumps(dumped, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    if size > DRAFT_BYTES_MAX:
        raise InvalidInput(TOO_LARGE.format(size=size, limit=DRAFT_BYTES_MAX))
    row.parts = dumped
    row.bytes = size
    row.version += 1
    row.updatedAt = now
    row.expiresAt = now + DRAFT_LIFETIME
    row.previewUrl = None
    row.previewExpiresAt = None
    row.report = None


def _parts_or_refusal(build: Callable[[], DraftParts]) -> DraftParts:
    try:
        return build()
    except ValidationError as refused:
        raise InvalidInput(_problems(refused)) from None
    except ValueError as refused:
        raise InvalidInput(str(refused)) from None


def _problems(refused: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(str(part) for part in problem['loc']) or 'draft'}: {problem['msg']}"
        for problem in refused.errors()
    )


async def _refuse_foreign_sources(session: AsyncSession, user_id: uuid.UUID, wanted: list[uuid.UUID]) -> None:
    if not wanted:
        return
    mine = set(
        await session.scalars(
            select(SuppliedSource.id).where(SuppliedSource.id.in_(wanted), SuppliedSource.userId == user_id)
        )
    )
    foreign = [str(ident) for ident in wanted if ident not in mine]
    if foreign:
        raise InvalidInput(NOT_YOURS.format(ids=", ".join(foreign)))


async def _open(session: AsyncSession, user_id: uuid.UUID, kind: str, slug: str) -> PageDraft | None:
    return await session.scalar(
        select(PageDraft).where(
            PageDraft.userId == user_id,
            PageDraft.subjectKind == kind,
            PageDraft.subjectSlug == slug,
            PageDraft.state == OPEN,
        )
    )


async def _prune(session: AsyncSession, user_id: uuid.UUID, now: datetime) -> None:
    await session.execute(delete(PageDraft).where(PageDraft.userId == user_id, PageDraft.expiresAt <= now))
