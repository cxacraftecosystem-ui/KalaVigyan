from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput, Refused
from app.models import TaskReservation
from app.research.my_tasks import RefusedClaim, TaskClaims
from app.research.open_work import (
    RESERVATION_TIME,
    UNRESERVABLE_KINDS,
    OpenTask,
    TaskHold,
    parse_task_key,
)

from . import trust_tiers
from .open_work import open_task, proposed_tasks

__all__ = [
    "TASKS_HELD",
    "TASK_TAKEN",
    "claim_task",
    "claim_tasks",
    "complete_task",
    "give_back_task",
    "holding",
    "release_task",
]

TASK_TAKEN = "task_taken"
TASKS_HELD = "tasks_held"
EXPIRED = "EXPIRED"
RELEASED = "RELEASED"
COMPLETED = "COMPLETED"
NOT_OPEN = "No open task has the key {key}; list_open_work gives the open tasks."
QUEUE_NOT_RESERVED = "A review queue is worked item by item in admin settings; it is never reserved."
TOO_MANY = (
    "This account holds {held} tasks, the most an account of its trust tier ({tier}) may hold at once; "
    "release_task one, or finish one, before claiming another."
)
CLAIMED = "Reserved {held} tasks and refused {refused}; this account now holds {count} of its {most}."


async def claim_task(
    session: AsyncSession, user_id: uuid.UUID, key: str, *, site: str, now: datetime
) -> TaskHold:
    task = await _open(session, key, site=site)
    await _expire(session, key, now=now)
    current = await _live(session, key)
    if current is not None and current.userId != user_id:
        raise Refused(
            TASK_TAKEN,
            f"{key} is reserved by another account until {current.expiresAt.astimezone(UTC):%Y-%m-%d %H:%M} UTC; "
            "list_open_work gives the tasks still open.",
        )
    if current is not None:
        current.expiresAt = now + RESERVATION_TIME
        await session.flush()
        return _held(key, task, current.expiresAt)
    await _refuse_too_many(session, user_id, now=now)
    reservation = TaskReservation(
        taskKey=key, userId=user_id, reservedAt=now, expiresAt=now + RESERVATION_TIME
    )
    try:
        async with session.begin_nested():
            session.add(reservation)
    except IntegrityError as taken:
        raise Refused(TASK_TAKEN, f"{key} was reserved by another account a moment ago.") from taken
    return _held(key, task, reservation.expiresAt)


async def claim_tasks(
    session: AsyncSession, user_id: uuid.UUID, keys: list[str], *, site: str, now: datetime
) -> TaskClaims:
    held: list[TaskHold] = []
    refused: list[RefusedClaim] = []
    for key in dict.fromkeys(keys):
        try:
            async with session.begin_nested():
                held.append(await claim_task(session, user_id, key, site=site, now=now))
        except Refused as problem:
            refused.append(RefusedClaim(task_key=key, problem=problem.message))
        except InvalidInput as problem:
            refused.append(RefusedClaim(task_key=key, problem=str(problem)))
    standing = await trust_tiers.account_standing(session, user_id)
    count = await holding(session, user_id, now=now)
    return TaskClaims(
        held=held,
        refused=refused,
        tier=standing.tier,
        holding=count,
        holding_max=standing.tasks_held_max,
        message=CLAIMED.format(
            held=len(held), refused=len(refused), count=count, most=standing.tasks_held_max
        ),
    )


async def holding(session: AsyncSession, user_id: uuid.UUID, *, now: datetime) -> int:
    held = await session.scalar(
        select(func.count(TaskReservation.id)).where(
            TaskReservation.userId == user_id,
            TaskReservation.endedAt.is_(None),
            TaskReservation.expiresAt > now,
        )
    )
    return int(held or 0)


async def release_task(session: AsyncSession, user_id: uuid.UUID, key: str, *, now: datetime) -> TaskHold:
    parse_task_key(key)
    current = await _live(session, key)
    if current is None or current.userId != user_id:
        raise InvalidInput(f"You hold no reservation of {key}.")
    _end(current, _given_back(current, now), now=now)
    await session.flush()
    return TaskHold(task_key=key, held=False, reserved_until=None)


async def complete_task(session: AsyncSession, user_id: uuid.UUID, key: str, *, now: datetime) -> None:
    current = await _live(session, key)
    if current is not None and current.userId == user_id:
        _end(current, COMPLETED, now=now)
        await session.flush()


async def give_back_task(session: AsyncSession, user_id: uuid.UUID, key: str, *, now: datetime) -> None:
    current = await _live(session, key)
    if current is not None and current.userId == user_id:
        _end(current, _given_back(current, now), now=now)
        await session.flush()


async def _open(session: AsyncSession, key: str, *, site: str) -> OpenTask:
    parsed = parse_task_key(key)
    if parsed.kind in UNRESERVABLE_KINDS:
        raise InvalidInput(QUEUE_NOT_RESERVED)
    task = await open_task(session, parsed, site=site)
    if task is None or key in await proposed_tasks(session):
        raise InvalidInput(NOT_OPEN.format(key=key))
    return task


async def _expire(session: AsyncSession, key: str, *, now: datetime) -> None:
    await session.execute(
        update(TaskReservation)
        .where(
            TaskReservation.taskKey == key,
            TaskReservation.endedAt.is_(None),
            TaskReservation.expiresAt <= now,
        )
        .values(endedAt=TaskReservation.expiresAt, ending=EXPIRED)
        .execution_options(synchronize_session="fetch")
    )


async def _live(session: AsyncSession, key: str) -> TaskReservation | None:
    return await session.scalar(
        select(TaskReservation).where(TaskReservation.taskKey == key, TaskReservation.endedAt.is_(None))
    )


async def _refuse_too_many(session: AsyncSession, user_id: uuid.UUID, *, now: datetime) -> None:
    held = await holding(session, user_id, now=now)
    standing = await trust_tiers.account_standing(session, user_id)
    if held >= standing.tasks_held_max:
        raise Refused(TASKS_HELD, TOO_MANY.format(held=held, tier=standing.tier.lower()))


def _given_back(reservation: TaskReservation, now: datetime) -> str:
    return RELEASED if reservation.expiresAt > now else EXPIRED


def _end(reservation: TaskReservation, ending: str, *, now: datetime) -> None:
    reservation.endedAt = now if ending != EXPIRED else reservation.expiresAt
    reservation.ending = ending


def _held(key: str, task: OpenTask, until: datetime) -> TaskHold:
    return TaskHold(
        task_key=key, held=True, reserved_until=until, task=task.model_copy(update={"reserved_until": until})
    )
