from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import ColumnElement, Select, and_, any_, case, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, FieldImage, FieldPhotoReview, FieldPhotoScreen, User
from app.research.field_photo_reviews import (
    DECIDED_ACTION,
    FIELD_PHOTO_QUEUE_SCHEMA_VERSION,
    HIDDEN,
    HIDE,
    HISTORY_SHOWN,
    PHOTO_DECISIONS,
    PHOTO_TARGET,
    SHOWING_DECISIONS,
    SHOWN,
    WAITING,
    FieldPhotoItem,
    FieldPhotoQueue,
    PhotoHistoryEntry,
    PhotoQueueCounts,
)
from app.research.field_voices import FIELD_LIST_PAGE_SIZE
from app.research.image_screens import FACE, ID_DOCUMENT
from app.retrieval.field_scope import held_images

from .field_photo_crops import PhotoObjects
from .field_photo_items import PhotoRow, Shown, photo_item
from .field_voices_held import artisan_image_visibility
from .field_voices_reading import list_offset

__all__ = ["photo_history", "photo_item_of", "photo_queue"]


async def photo_queue(
    session: AsyncSession, *, state: str, cursor: str | None, objects: PhotoObjects | None, now: datetime
) -> FieldPhotoQueue:
    offset = list_offset(cursor)
    rows = await _rows(session, _listed(state).offset(offset).limit(FIELD_LIST_PAGE_SIZE))
    counts = await _counts(session)
    total = {WAITING: counts.waiting, SHOWN: counts.shown, HIDDEN: counts.hidden}[state]
    following = offset + FIELD_LIST_PAGE_SIZE
    shown = Shown(objects=objects, now=now, history=await photo_history(session, [r.image.id for r in rows]))
    return FieldPhotoQueue(
        schema_version=FIELD_PHOTO_QUEUE_SCHEMA_VERSION,
        state=state,
        visibility=await artisan_image_visibility(session),
        counts=counts,
        cursor=cursor,
        next_cursor=str(following) if following < total else None,
        items=[photo_item(row, shown) for row in rows],
    )


async def photo_item_of(
    session: AsyncSession, image_id: uuid.UUID, *, objects: PhotoObjects | None, now: datetime
) -> FieldPhotoItem | None:
    rows = await _rows(session, _joined().where(FieldImage.id == image_id))
    if not rows:
        return None
    shown = Shown(objects=objects, now=now, history=await photo_history(session, [image_id]))
    return photo_item(rows[0], shown)


async def photo_history(
    session: AsyncSession, image_ids: Sequence[uuid.UUID]
) -> dict[str, list[PhotoHistoryEntry]]:
    if not image_ids:
        return {}
    rows = await session.execute(
        select(AuditLog.targetId, AuditLog.detail, AuditLog.createdAt, User.name)
        .outerjoin(User, User.id == AuditLog.actorId)
        .where(
            AuditLog.action == DECIDED_ACTION,
            AuditLog.targetType == PHOTO_TARGET,
            AuditLog.targetId.in_([str(each) for each in image_ids]),
        )
    )
    found: dict[str, list[PhotoHistoryEntry]] = defaultdict(list)
    for target, detail, at, name in rows:
        entry = _entry(detail or {}, at, name)
        if entry is not None and target is not None:
            found[target].append(entry)
    return {
        key: sorted(each, key=lambda entry: entry.decided_at, reverse=True)[:HISTORY_SHOWN]
        for key, each in found.items()
    }


def _entry(detail: dict[str, Any], at: datetime, name: str | None) -> PhotoHistoryEntry | None:
    decision = detail.get("decision")
    if decision not in PHOTO_DECISIONS:
        return None
    decided = detail.get("decidedAt")
    return PhotoHistoryEntry(
        decision=decision,
        reason=detail.get("reason"),
        note=detail.get("note"),
        decided_at=datetime.fromisoformat(decided) if isinstance(decided, str) else at,
        decided_by=name,
    )


def _joined() -> Select[Any]:
    current_screen = and_(
        FieldPhotoScreen.imageId == FieldImage.id, FieldPhotoScreen.imageSha256 == FieldImage.sha256
    )
    return (
        select(FieldImage, FieldPhotoReview, FieldPhotoScreen, User.name)
        .outerjoin(FieldPhotoReview, FieldPhotoReview.imageId == FieldImage.id)
        .outerjoin(FieldPhotoScreen, current_screen)
        .outerjoin(User, User.id == FieldPhotoReview.deciderId)
    )


def _listed(state: str) -> Select[Any]:
    query = _joined().where(*held_images(), _in_state(state))
    if state == WAITING:
        return query.order_by(_risk_rank(), FieldImage.takenAt.desc().nulls_last(), FieldImage.id)
    return query.order_by(FieldPhotoReview.decidedAt.desc(), FieldImage.id)


def _in_state(state: str) -> ColumnElement[bool]:
    current = FieldPhotoReview.imageSha256 == FieldImage.sha256
    if state == WAITING:
        return or_(FieldPhotoReview.id.is_(None), FieldPhotoReview.imageSha256 != FieldImage.sha256)
    if state == SHOWN:
        return and_(current, FieldPhotoReview.decision.in_(SHOWING_DECISIONS))
    return and_(current, FieldPhotoReview.decision == HIDE)


def _risk_rank() -> ColumnElement[int]:
    return case(
        (literal(ID_DOCUMENT) == any_(FieldPhotoScreen.flags), 0),
        (literal(FACE) == any_(FieldPhotoScreen.flags), 1),
        (FieldPhotoScreen.imageId.is_(None), 2),
        (func.cardinality(FieldPhotoScreen.flags) > 0, 2),
        else_=3,
    )


async def _counts(session: AsyncSession) -> PhotoQueueCounts:
    found = (
        await session.execute(
            select(*(func.count().filter(_in_state(state)) for state in (WAITING, SHOWN, HIDDEN)))
            .select_from(FieldImage)
            .outerjoin(FieldPhotoReview, FieldPhotoReview.imageId == FieldImage.id)
            .where(*held_images())
        )
    ).one()
    return PhotoQueueCounts(waiting=int(found[0]), shown=int(found[1]), hidden=int(found[2]))


async def _rows(session: AsyncSession, query: Select[Any]) -> list[PhotoRow]:
    found = await session.execute(query.execution_options(populate_existing=True))
    return [
        PhotoRow(image=image, review=review, screen=screen, decider=name)
        for image, review, screen, name in found
    ]
