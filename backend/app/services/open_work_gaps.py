from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Sequence

from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AnswerGap
from app.research.open_work import PRIORITIES, OpenTask, TaskSubject
from app.research.open_work_gap_tasks import OpenGap, gap_task

__all__ = ["OPEN_GAP", "asked_tasks", "open_gaps"]

OPEN_GAP = "OPEN"
PRIORITY_ORDER = case({priority: rank for rank, priority in enumerate(PRIORITIES)}, value=AnswerGap.priority)


async def open_gaps(session: AsyncSession, craft_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, list[OpenGap]]:
    if not craft_ids:
        return {}
    rows = await session.scalars(
        select(AnswerGap)
        .where(AnswerGap.craftId.in_(list(craft_ids)), AnswerGap.state == OPEN_GAP, AnswerGap.askers > 0)
        .order_by(PRIORITY_ORDER, AnswerGap.askers.desc(), AnswerGap.lastAskedAt.desc(), AnswerGap.id)
    )
    found: dict[uuid.UUID, list[OpenGap]] = defaultdict(list)
    for row in rows.all():
        found[row.craftId].append(
            OpenGap(
                id=row.id,
                question=row.question,
                askers=row.askers,
                last_asked=row.lastAskedAt,
                fields=tuple(row.fields),
                lacks=tuple(row.lacks),
                priority=row.priority,
            )
        )
    return dict(found)


def asked_tasks(subject: TaskSubject, gaps: Sequence[OpenGap]) -> tuple[OpenTask, ...]:
    return tuple(gap_task(subject, gap) for gap in gaps if gap.fields)
