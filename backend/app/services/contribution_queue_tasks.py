from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput
from app.models import TaskReservation, User
from app.research.my_tasks import (
    COMPLETED_SHOWN_MAX,
    COMPLETED_WINDOW,
    OUTCOMES_SHOWN_MAX,
    EndedTask,
    HeldTask,
    MyTasks,
)
from app.research.open_work import OpenTask, parse_task_key
from app.research.open_work_tasks import subject_tasks

from . import trust_tiers
from .contribution_queue_tickets import recent_tickets
from .open_work import RESERVATION_MINUTES, subject_standings
from .open_work_subjects import subject_by_key

__all__ = ["COMPLETED", "my_tasks"]

COMPLETED = "COMPLETED"


async def my_tasks(session: AsyncSession, user: User, *, site: str, now: datetime) -> MyTasks:
    standing = await trust_tiers.account_standing(session, user.id)
    live = await _live(session, user.id, now=now)
    tasks = await _open_tasks(session, [row.taskKey for row in live], site=site)
    outcomes = await recent_tickets(session, user.id, limit=OUTCOMES_SHOWN_MAX)
    return MyTasks(
        tier=standing.tier,
        holding=len(live),
        holding_max=standing.tasks_held_max,
        reservation_minutes=RESERVATION_MINUTES,
        claimed=[
            HeldTask(task_key=row.taskKey, reserved_until=row.expiresAt, task=tasks.get(row.taskKey))
            for row in live
        ],
        completed=await _completed(session, user.id, now=now),
        outcomes=outcomes.proposals,
    )


async def _live(session: AsyncSession, user_id: uuid.UUID, *, now: datetime) -> list[TaskReservation]:
    rows = await session.scalars(
        select(TaskReservation)
        .where(
            TaskReservation.userId == user_id,
            TaskReservation.endedAt.is_(None),
            TaskReservation.expiresAt > now,
        )
        .order_by(TaskReservation.expiresAt, TaskReservation.taskKey)
    )
    return list(rows.all())


async def _completed(session: AsyncSession, user_id: uuid.UUID, *, now: datetime) -> list[EndedTask]:
    rows = await session.scalars(
        select(TaskReservation)
        .where(
            TaskReservation.userId == user_id,
            TaskReservation.ending == COMPLETED,
            TaskReservation.endedAt >= now - COMPLETED_WINDOW,
        )
        .order_by(TaskReservation.endedAt.desc(), TaskReservation.taskKey)
        .limit(COMPLETED_SHOWN_MAX)
    )
    return [
        EndedTask(task_key=row.taskKey, ending=COMPLETED, ended_at=row.endedAt)
        for row in rows.all()
        if row.endedAt is not None
    ]


async def _open_tasks(session: AsyncSession, keys: Sequence[str], *, site: str) -> dict[str, OpenTask]:
    subjects: dict[tuple[str, str], set[str]] = {}
    for key in keys:
        parsed = parse_task_key(key)
        if parsed.subject_kind is not None and parsed.slug is not None:
            subjects.setdefault((parsed.subject_kind, parsed.slug), set()).add(key)
    found: dict[str, OpenTask] = {}
    for (kind, slug), wanted in subjects.items():
        try:
            subject = await subject_by_key(session, kind, slug)
        except InvalidInput:
            continue
        (standing,) = await subject_standings(session, [subject], site=site)
        found |= {task.key: task for task in subject_tasks(standing) if task.key in wanted}
    return found
