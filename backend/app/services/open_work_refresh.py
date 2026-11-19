from __future__ import annotations

from collections import Counter
from collections.abc import Collection, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import TaskReservation
from app.research.open_work import OpenTask
from app.research.open_work_tasks import subject_tasks

from .open_work import subject_standings
from .open_work_subjects import work_subjects

__all__ = ["FIELD_TASK_KINDS", "FieldWorkReport", "closed_field_reservations", "refresh_field_work"]

FIELD_TASK_KINDS = ("MISSING_FIELD", "THIN_FIELD")
COMPLETED = "COMPLETED"
KEY_SEPARATOR = ":"


@dataclass
class FieldWorkReport:
    subjects: int = 0
    tasks: dict[str, int] = field(default_factory=dict)
    priorities: dict[str, int] = field(default_factory=dict)
    closed: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "subjects": self.subjects,
            "tasks": self.tasks,
            "priorities": self.priorities,
            "reservationsClosed": len(self.closed),
        }


async def refresh_field_work(session: AsyncSession, *, now: datetime) -> FieldWorkReport:
    subjects = await work_subjects(session, None)
    standings = await subject_standings(session, subjects, site=get_settings().public_web_url.rstrip("/"))
    tasks = [
        task for standing in standings for task in subject_tasks(standing) if task.kind in FIELD_TASK_KINDS
    ]
    report = FieldWorkReport(
        subjects=len(subjects),
        tasks=dict(Counter(task.kind for task in tasks)),
        priorities=dict(Counter(task.priority for task in tasks)),
    )
    report.closed = await _close_done(session, tasks, now=now)
    return report


def closed_field_reservations(held: Sequence[str], tasks: Sequence[OpenTask]) -> list[str]:
    still_open = {task.key for task in tasks}
    return [key for key in held if key not in still_open]


async def _close_done(session: AsyncSession, tasks: Collection[OpenTask], *, now: datetime) -> list[str]:
    rows = await session.scalars(
        select(TaskReservation).where(
            TaskReservation.endedAt.is_(None),
            or_(
                *(
                    TaskReservation.taskKey.startswith(f"{kind}{KEY_SEPARATOR}", autoescape=True)
                    for kind in FIELD_TASK_KINDS
                )
            ),
        )
    )
    held = {reservation.taskKey: reservation for reservation in rows.all()}
    closed = closed_field_reservations(sorted(held), list(tasks))
    for key in closed:
        held[key].endedAt = now
        held[key].ending = COMPLETED
    await session.flush()
    return closed
