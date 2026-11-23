from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import ValidationError
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput
from app.models import LessonPack as LessonRow
from app.research.lesson_builder import lesson_pack
from app.research.lessons import LESSON_SCHEMA_VERSION, LessonList, LessonPack, LessonRequest, LessonSummary

from .explainer_history import explainer_version
from .shared_files import FileDeleter, drop_stopped_share_files
from .visible_claims import visible_claim_ids

__all__ = ["build_lesson", "delete_lesson", "lesson_list", "lesson_of", "stored_pack"]

CRAFT_KEY = "craft"
SLIDES_KEY = "slides"


async def build_lesson(
    session: AsyncSession, user_id: uuid.UUID, request: LessonRequest, *, now: datetime
) -> LessonPack:
    document = await explainer_version(session, request.explainer_id, user_id, request.version)
    pack = lesson_pack(
        document,
        request,
        visible_claim_ids=await visible_claim_ids(session, document.explainer),
        pack_id=uuid.uuid4(),
        created_at=now,
    )
    session.add(
        LessonRow(
            id=pack.id,
            userId=user_id,
            explainerId=pack.explainer_id,
            version=pack.version,
            title=pack.title,
            payload=pack.model_dump(mode="json", by_alias=True),
            createdAt=pack.created_at,
        )
    )
    await session.commit()
    return pack


async def lesson_list(session: AsyncSession, user_id: uuid.UUID) -> LessonList:
    rows = await session.execute(
        select(
            LessonRow.id,
            LessonRow.title,
            LessonRow.explainerId,
            LessonRow.version,
            LessonRow.payload[CRAFT_KEY],
            LessonRow.createdAt,
            func.jsonb_array_length(LessonRow.payload[SLIDES_KEY]),
        )
        .where(LessonRow.userId == user_id)
        .order_by(LessonRow.createdAt.desc(), LessonRow.id)
    )
    items = [
        LessonSummary(
            id=pack_id,
            title=title,
            explainer_id=explainer_id,
            version=version,
            craft=craft,
            created_at=created_at,
            slide_count=slides,
        )
        for pack_id, title, explainer_id, version, craft, created_at, slides in rows.tuples().all()
    ]
    return LessonList(schema_version=LESSON_SCHEMA_VERSION, items=items)


async def lesson_of(session: AsyncSession, user_id: uuid.UUID, pack_id: uuid.UUID) -> LessonPack | None:
    payload = await session.scalar(
        select(LessonRow.payload).where(LessonRow.id == pack_id, LessonRow.userId == user_id)
    )
    return None if payload is None else stored_pack(pack_id, payload)


def stored_pack(pack_id: uuid.UUID, payload: dict[str, Any]) -> LessonPack:
    try:
        return LessonPack.model_validate(payload)
    except ValidationError as error:
        raise InvalidInput(f"lesson pack {pack_id} is stored off its contract") from error


async def delete_lesson(
    session: AsyncSession, user_id: uuid.UUID, pack_id: uuid.UUID, *, objects: FileDeleter | None
) -> bool:
    deleted = await session.execute(
        delete(LessonRow).where(LessonRow.id == pack_id, LessonRow.userId == user_id).returning(LessonRow.id)
    )
    found = deleted.scalar_one_or_none() is not None
    if found:
        await drop_stopped_share_files(session, objects)
    await session.commit()
    return found
