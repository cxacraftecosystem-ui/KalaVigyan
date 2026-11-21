from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput
from app.models import AnswerGap, Craft
from app.research.knowledge_writes import gap_fields_problem
from app.research.open_work import parse_task_key
from app.research.open_work_gap_keys import GAP_TASK, gap_id

__all__ = ["asked_fields", "check_question_task"]


async def check_question_task(session: AsyncSession, key: str | None, fields: Sequence[str]) -> None:
    if key is None:
        return
    task = parse_task_key(key)
    if task.kind != GAP_TASK or task.slug is None:
        return
    gap = gap_id(task.detail) if task.detail is not None else None
    asked = None if gap is None else await asked_fields(session, gap, task.slug)
    problem = gap_fields_problem(key, asked, fields)
    if problem is not None:
        raise InvalidInput(problem)


async def asked_fields(session: AsyncSession, gap: uuid.UUID, craft_slug: str) -> tuple[str, ...] | None:
    fields = await session.scalar(
        select(AnswerGap.fields)
        .join(Craft, Craft.id == AnswerGap.craftId)
        .where(AnswerGap.id == gap, Craft.slug == craft_slug)
    )
    return None if fields is None else tuple(fields)
