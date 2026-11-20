from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput, Refused
from app.models import Craft, CraftSteward, User
from app.research.open_work import TASKS_LIMIT_MAX, Viewer, WorkFilters
from app.research.stewardship import STEWARD_CRAFTS_MAX, MyCrafts, StewardPackage, Stewardship

from .open_work import list_open_work
from .open_work_subjects import WorkSubject, craft_subject, craft_subjects

__all__ = ["CRAFTS_ADOPTED", "adopt_craft", "drop_craft", "my_crafts"]

CRAFTS_ADOPTED = "crafts_adopted"
FAMILY = "family"
TOO_MANY = "This account stewards {count} crafts, the most one account may; drop one with steward_craft before adopting another."
NOT_ADOPTED = "This account does not steward {slug}; my_work lists the crafts it stewards."
DROPPED = "This account no longer stewards {slug}; its open work stays open to everyone."
LISTED = (
    "This account stewards {count} of at most {most} crafts; each craft's tasks not open at your last look "
    "come first, as new gaps. Stewardship never reserves a task: reserve_tasks does."
)


async def adopt_craft(
    session: AsyncSession, user: User, slug: str, *, site: str, now: datetime
) -> StewardPackage:
    subject = await craft_subject(session, slug)
    row = await _live(session, user.id, subject.id)
    if row is None:
        held = await _adopted(session, user.id)
        if held >= STEWARD_CRAFTS_MAX:
            raise Refused(CRAFTS_ADOPTED, TOO_MANY.format(count=held))
        row = await _stored(session, user.id, subject.id, now=now)
    return await _package(session, user.id, row, subject, site=site, now=now)


async def drop_craft(session: AsyncSession, user: User, slug: str, *, now: datetime) -> Stewardship:
    subject = await craft_subject(session, slug)
    row = await _live(session, user.id, subject.id)
    if row is None:
        raise InvalidInput(NOT_ADOPTED.format(slug=subject.slug))
    row.droppedAt = now
    await session.flush()
    return Stewardship(craft_slug=subject.slug, adopted=False, message=DROPPED.format(slug=subject.slug))


async def my_crafts(session: AsyncSession, user: User, *, site: str, now: datetime) -> MyCrafts:
    rows = list(
        await session.scalars(
            select(CraftSteward)
            .where(CraftSteward.userId == user.id, CraftSteward.droppedAt.is_(None))
            .order_by(CraftSteward.adoptedAt, CraftSteward.id)
        )
    )
    slugs = dict(
        (
            await session.execute(
                select(Craft.id, Craft.slug).where(Craft.id.in_([row.craftId for row in rows]))
            )
        ).all()
    )
    subjects = {subject.id: subject for subject in await craft_subjects(session, list(slugs.values()))}
    packages = [
        await _package(session, user.id, row, subjects[row.craftId], site=site, now=now)
        for row in rows
        if row.craftId in subjects
    ]
    return MyCrafts(
        crafts=packages,
        adopted=len(packages),
        adopted_max=STEWARD_CRAFTS_MAX,
        message=LISTED.format(count=len(packages), most=STEWARD_CRAFTS_MAX),
    )


async def _package(
    session: AsyncSession,
    user_id: uuid.UUID,
    row: CraftSteward,
    subject: WorkSubject,
    *,
    site: str,
    now: datetime,
) -> StewardPackage:
    named = {"family_slug" if subject.kind == FAMILY else "craft_slug": subject.slug}
    work = await list_open_work(
        session, WorkFilters(limit=TASKS_LIMIT_MAX, **named), Viewer(user_id=user_id), site=site, now=now
    )
    seen = set(row.seenTaskKeys)
    fresh = [task for task in work.tasks if task.key not in seen]
    known = [task for task in work.tasks if task.key in seen]
    looked = row.seenAt
    row.seenTaskKeys, row.seenAt = [task.key for task in work.tasks], now
    await session.flush()
    return StewardPackage(
        craft=subject.task_subject(site),
        adopted_at=row.adoptedAt,
        seen_at=looked,
        stewards=await _stewards(session, subject.id),
        new_tasks=fresh,
        tasks=known,
        total=work.total,
    )


async def _live(session: AsyncSession, user_id: uuid.UUID, craft_id: uuid.UUID) -> CraftSteward | None:
    return await session.scalar(
        select(CraftSteward).where(
            CraftSteward.userId == user_id, CraftSteward.craftId == craft_id, CraftSteward.droppedAt.is_(None)
        )
    )


async def _stored(
    session: AsyncSession, user_id: uuid.UUID, craft_id: uuid.UUID, *, now: datetime
) -> CraftSteward:
    row = CraftSteward(
        id=uuid.uuid4(),
        userId=user_id,
        craftId=craft_id,
        adoptedAt=now,
        droppedAt=None,
        seenTaskKeys=[],
        seenAt=None,
    )
    try:
        async with session.begin_nested():
            session.add(row)
    except IntegrityError:
        found = await _live(session, user_id, craft_id)
        if found is None:
            raise
        return found
    return row


async def _adopted(session: AsyncSession, user_id: uuid.UUID) -> int:
    count = await session.scalar(
        select(func.count(CraftSteward.id)).where(
            CraftSteward.userId == user_id, CraftSteward.droppedAt.is_(None)
        )
    )
    return int(count or 0)


async def _stewards(session: AsyncSession, craft_id: uuid.UUID) -> int:
    count = await session.scalar(
        select(func.count(CraftSteward.id)).where(
            CraftSteward.craftId == craft_id, CraftSteward.droppedAt.is_(None)
        )
    )
    return max(1, int(count or 0))
