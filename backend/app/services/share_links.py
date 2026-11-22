from __future__ import annotations

import secrets
import uuid
from datetime import datetime
from typing import Any

from pydantic import ValidationError
from sqlalchemy import Row, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models import Answer, LessonPack as LessonRow
from app.research.explainer_versions import ExplainerVersionDocument
from app.research.lesson_builder import LessonNotBuildable, UnknownLessonSection, lesson_pack
from app.research.lessons import LessonPack, LessonRequest
from app.research.share_links import (
    SHARE_SCHEMA_VERSION,
    SHARED_ANSWER_PAGE,
    SHARED_LESSON_PAGE,
    ShareLink,
    shared_page,
)

from .access_roster import account_in_good_standing
from .explainer_history import UnknownExplainer, owned_explainer, shown_version
from .explainer_payload import stored_version
from .lesson_packs import stored_pack
from .public_explainer import PUBLIC_READING_ACLS, public_version
from .shared_files import FileDeleter, drop_stopped_share_files
from .visible_claims import visible_claim_ids

__all__ = [
    "NOTHING_PUBLIC_DETAIL",
    "NothingPublic",
    "answer_share",
    "lesson_share",
    "public_lesson",
    "share_answer",
    "share_lesson",
    "shared_answer",
    "shared_lesson",
    "unshare_answer",
    "unshare_lesson",
]

SHARE_TOKEN_BYTES = 24
READY = "READY"
SECTION_SLIDE = "SECTION"
NOTHING_PUBLIC_DETAIL = (
    "Nothing here can be shown publicly: every sentence quotes text that only signed-in researchers may read."
)


class NothingPublic(AppError):
    def __init__(self, what: str) -> None:
        super().__init__(f"{what} has nothing a public reader may see")


async def answer_share(
    session: AsyncSession, user_id: uuid.UUID, explainer_id: uuid.UUID, version: int
) -> ShareLink:
    row = await _owned_answer(session, user_id, explainer_id, version)
    return _link(SHARED_ANSWER_PAGE, row.shareToken, row.sharedAt)


async def share_answer(
    session: AsyncSession, user_id: uuid.UUID, explainer_id: uuid.UUID, version: int, *, now: datetime
) -> ShareLink:
    row = await _owned_answer(session, user_id, explainer_id, version)
    if row.shareToken is None:
        if await _public_answer(session, row.id, version, row.payload) is None:
            raise NothingPublic(f"explainer {explainer_id} version {version}")
        await _mark_shared(session, Answer, row.id, now)
        row = await _owned_answer(session, user_id, explainer_id, version)
    return _link(SHARED_ANSWER_PAGE, row.shareToken, row.sharedAt)


async def unshare_answer(
    session: AsyncSession,
    user_id: uuid.UUID,
    explainer_id: uuid.UUID,
    version: int,
    *,
    objects: FileDeleter | None,
) -> bool:
    owned = (*owned_explainer(explainer_id, user_id), Answer.explainerVersion == version)
    return await _unmark(session, objects, Answer, *owned)


async def shared_answer(session: AsyncSession, token: str) -> ExplainerVersionDocument | None:
    row = (
        await session.execute(
            select(Answer.id, Answer.explainerVersion, Answer.payload).where(
                Answer.shareToken == token, account_in_good_standing(Answer.userId)
            )
        )
    ).first()
    if row is None or row.explainerVersion is None:
        return None
    return await _public_answer(session, row.id, row.explainerVersion, row.payload)


async def lesson_share(session: AsyncSession, user_id: uuid.UUID, lesson_id: uuid.UUID) -> ShareLink | None:
    row = await _owned_lesson(session, user_id, lesson_id)
    return None if row is None else _link(SHARED_LESSON_PAGE, row.shareToken, row.sharedAt)


async def share_lesson(
    session: AsyncSession, user_id: uuid.UUID, lesson_id: uuid.UUID, *, now: datetime
) -> ShareLink | None:
    row = await _owned_lesson(session, user_id, lesson_id)
    if row is None:
        return None
    if row.shareToken is None:
        if await public_lesson(session, stored_pack(lesson_id, row.payload)) is None:
            raise NothingPublic(f"lesson {lesson_id}")
        await _mark_shared(session, LessonRow, lesson_id, now)
        row = await _owned_lesson(session, user_id, lesson_id)
    return None if row is None else _link(SHARED_LESSON_PAGE, row.shareToken, row.sharedAt)


async def unshare_lesson(
    session: AsyncSession, user_id: uuid.UUID, lesson_id: uuid.UUID, *, objects: FileDeleter | None
) -> bool:
    return await _unmark(session, objects, LessonRow, LessonRow.id == lesson_id, LessonRow.userId == user_id)


async def shared_lesson(session: AsyncSession, token: str) -> LessonPack | None:
    row = (
        await session.execute(
            select(LessonRow.id, LessonRow.payload).where(
                LessonRow.shareToken == token, account_in_good_standing(LessonRow.userId)
            )
        )
    ).first()
    return None if row is None else await public_lesson(session, stored_pack(row.id, row.payload))


async def public_lesson(session: AsyncSession, pack: LessonPack) -> LessonPack | None:
    row = (
        await session.execute(
            select(Answer.id, Answer.payload).where(
                Answer.explainerId == pack.explainer_id, Answer.explainerVersion == pack.version
            )
        )
    ).first()
    if row is None:
        return None
    public = await _public_answer(session, row.id, pack.version, row.payload)
    return None if public is None else await _rebuilt(session, pack, public)


async def _rebuilt(
    session: AsyncSession, pack: LessonPack, public: ExplainerVersionDocument
) -> LessonPack | None:
    ready = {section.id for section in public.explainer.sections if section.state == READY}
    taught = [
        section_id
        for section_id in dict.fromkeys(
            slide.section_id for slide in pack.slides if slide.kind == SECTION_SLIDE
        )
        if section_id in ready
    ]
    if not taught:
        return None
    request = LessonRequest(
        explainer_id=pack.explainer_id,
        version=pack.version,
        title=pack.title,
        section_ids=taught,
        quiz=pack.quiz is not None,
    )
    visible = await visible_claim_ids(session, public.explainer, acls=PUBLIC_READING_ACLS)
    try:
        return lesson_pack(
            public, request, visible_claim_ids=visible, pack_id=pack.id, created_at=pack.created_at
        )
    except LessonNotBuildable, UnknownLessonSection, ValidationError:
        return None


async def _public_answer(
    session: AsyncSession, answer_id: uuid.UUID, version: int, payload: dict[str, Any] | None
) -> ExplainerVersionDocument | None:
    try:
        document = await shown_version(session, stored_version(answer_id, version, payload))
    except UnknownExplainer:
        return None
    return await public_version(session, document)


async def _owned_answer(
    session: AsyncSession, user_id: uuid.UUID, explainer_id: uuid.UUID, version: int
) -> Row[Any]:
    row = (
        await session.execute(
            select(Answer.id, Answer.payload, Answer.shareToken, Answer.sharedAt).where(
                *owned_explainer(explainer_id, user_id), Answer.explainerVersion == version
            )
        )
    ).first()
    if row is None:
        raise UnknownExplainer(explainer_id)
    return row


async def _owned_lesson(session: AsyncSession, user_id: uuid.UUID, lesson_id: uuid.UUID) -> Row[Any] | None:
    return (
        await session.execute(
            select(LessonRow.payload, LessonRow.shareToken, LessonRow.sharedAt).where(
                LessonRow.id == lesson_id, LessonRow.userId == user_id
            )
        )
    ).first()


async def _mark_shared(session: AsyncSession, table: Any, row_id: uuid.UUID, now: datetime) -> None:
    await session.execute(
        update(table)
        .where(table.id == row_id, table.shareToken.is_(None))
        .values(shareToken=secrets.token_urlsafe(SHARE_TOKEN_BYTES), sharedAt=now)
    )
    await session.commit()


async def _unmark(session: AsyncSession, objects: FileDeleter | None, table: Any, *owned: Any) -> bool:
    found = await session.execute(
        update(table).where(*owned).values(shareToken=None, sharedAt=None).returning(table.id)
    )
    hit = found.first() is not None
    if hit:
        await drop_stopped_share_files(session, objects)
    await session.commit()
    return hit


def _link(page: str, token: str | None, shared_at: datetime | None) -> ShareLink:
    return ShareLink(
        schema_version=SHARE_SCHEMA_VERSION,
        shared=token is not None,
        path=shared_page(page, token),
        shared_at=shared_at,
    )
