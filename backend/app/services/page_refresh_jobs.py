from __future__ import annotations

import uuid
from collections.abc import Coroutine
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Protocol

from sqlalchemy import and_, func, or_, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import INDIA_TZ
from app.core.config import get_settings
from app.core.errors import Refused
from app.core.roles import is_master_admin
from app.models import PageRefreshJob, User
from app.research.page_refresh import (
    CHANGED,
    CHANGED_COOLDOWN,
    DEAD_AFTER,
    EVERY,
    EVERY_COOLDOWN,
    FAILED,
    FINISHED_PHASE,
    MCP_ORIGIN,
    NAMED,
    NIGHT_DEAD_AFTER,
    NIGHT_ORIGIN,
    RUNNING,
    WEB_ORIGIN,
    PageRefreshState,
    RefreshJobView,
    RefreshProgress,
    cooldown_end,
)
from app.research.page_revalidation import PageOwners

from . import audit

__all__ = [
    "BUSY",
    "EVERY_FOR_MASTER",
    "REFRESH_STARTED",
    "TOO_SOON",
    "Background",
    "RefreshAsk",
    "RefreshRefused",
    "claim_night",
    "end_stopped_jobs",
    "finish_job",
    "job_view",
    "record_progress",
    "refresh_state",
    "start_refresh",
]

REFRESH_STARTED = "site.pages_refresh_started"
BUSY, TOO_SOON, EVERY_FOR_MASTER = "busy", "too_soon", "master_admin_only"
BUSY_MESSAGE = "A refresh of the pages is already running; wait for it to finish."
NIGHT_BUSY_MESSAGE = "The night's refresh is running; wait for it to finish."
TOO_SOON_MESSAGE = "A refresh started in the last {minutes} minutes; the next can start at {at} India time."
EVERY_MESSAGE = "Refreshing every page is for the Master Admin, once a day."
STOPPED = "The refresh stopped without finishing; the next one starts afresh."
MANUAL_ORIGINS = (WEB_ORIGIN, MCP_ORIGIN)
RUNNING_ONLY = text(f"\"status\" = '{RUNNING}'")


class Background(Protocol):
    def start(self, work: Coroutine[Any, Any, Any], *, name: str) -> None: ...


class RefreshRefused(Refused):
    def __init__(self, reason: str, message: str, *, retry_after: float | None = None) -> None:
        super().__init__(reason, message)
        self.retry_after = retry_after


@dataclass(frozen=True)
class RefreshAsk:
    scope: str
    origin: str
    actor: User | None
    client_name: str | None = None
    owners: PageOwners | None = None


async def start_refresh(session: AsyncSession, ask: RefreshAsk, *, now: datetime) -> uuid.UUID:
    if ask.scope == EVERY and not is_master_admin(ask.actor):
        raise RefreshRefused(EVERY_FOR_MASTER, EVERY_MESSAGE)
    await end_stopped_jobs(session, now=now)
    await _refuse_early(session, ask, now=now)
    job_id = await _claimed(session, ask, now=now)
    if job_id is None:
        raise RefreshRefused(BUSY, await _busy_message(session))
    await audit.record(
        session,
        action=REFRESH_STARTED,
        actor=ask.actor,
        target_type="PageRefreshJob",
        target_id=job_id,
        detail={"scope": ask.scope, "origin": ask.origin, "client": ask.client_name},
    )
    await session.commit()
    return job_id


async def claim_night(session: AsyncSession, *, now: datetime) -> uuid.UUID | None:
    await end_stopped_jobs(session, now=now)
    job_id = await _claimed(session, RefreshAsk(CHANGED, NIGHT_ORIGIN, None), now=now)
    await session.commit()
    return job_id


async def end_stopped_jobs(session: AsyncSession, *, now: datetime) -> None:
    night = PageRefreshJob.origin == NIGHT_ORIGIN
    stopped = or_(
        and_(night, PageRefreshJob.startedAt < now - NIGHT_DEAD_AFTER),
        and_(~night, PageRefreshJob.startedAt < now - DEAD_AFTER),
    )
    await session.execute(
        update(PageRefreshJob)
        .where(PageRefreshJob.status == RUNNING, stopped)
        .values(status=FAILED, phase=FINISHED_PHASE, finishedAt=now, note=STOPPED)
    )


async def record_progress(
    session: AsyncSession, job_id: uuid.UUID, *, phase: str, progress: RefreshProgress
) -> None:
    await session.execute(
        update(PageRefreshJob)
        .where(PageRefreshJob.id == job_id)
        .values(phase=phase, progress=progress.model_dump(mode="json"))
    )
    await session.commit()


async def finish_job(
    session: AsyncSession, job_id: uuid.UUID, *, status: str, progress: RefreshProgress, note: str | None
) -> None:
    await session.execute(
        update(PageRefreshJob)
        .where(PageRefreshJob.id == job_id, PageRefreshJob.status == RUNNING)
        .values(
            status=status,
            phase=FINISHED_PHASE,
            progress=progress.model_dump(mode="json"),
            note=note,
            finishedAt=func.now(),
        )
    )
    await session.commit()


async def refresh_state(session: AsyncSession, viewer: User, *, now: datetime) -> PageRefreshState:
    await end_stopped_jobs(session, now=now)
    running = await _latest(session, PageRefreshJob.status == RUNNING)
    last = await _latest(session, PageRefreshJob.status != RUNNING)
    changed_at = await _last_start(session, PageRefreshJob.origin.in_(MANUAL_ORIGINS))
    every_at = await _last_start(session, PageRefreshJob.scope == EVERY)
    return PageRefreshState(
        configured=bool((get_settings().web_revalidate_secret or "").strip()),
        running=running,
        last=last,
        next_allowed_at=cooldown_end(changed_at, CHANGED_COOLDOWN, now=now),
        every_allowed_at=cooldown_end(every_at, EVERY_COOLDOWN, now=now),
        may_refresh_every=is_master_admin(viewer),
    )


async def job_view(session: AsyncSession, job_id: uuid.UUID) -> RefreshJobView | None:
    return await _latest(session, PageRefreshJob.id == job_id)


async def _refuse_early(session: AsyncSession, ask: RefreshAsk, *, now: datetime) -> None:
    if ask.scope == NAMED or ask.origin not in MANUAL_ORIGINS:
        return
    await _refuse_within(session, PageRefreshJob.origin.in_(MANUAL_ORIGINS), CHANGED_COOLDOWN, now=now)
    if ask.scope == EVERY:
        await _refuse_within(session, PageRefreshJob.scope == EVERY, EVERY_COOLDOWN, now=now)


async def _refuse_within(
    session: AsyncSession, condition: Any, cooldown: timedelta, *, now: datetime
) -> None:
    ends = cooldown_end(await _last_start(session, condition), cooldown, now=now)
    if ends is None:
        return
    minutes = int(cooldown.total_seconds() // 60)
    at = ends.astimezone(INDIA_TZ).strftime("%H:%M")
    message = TOO_SOON_MESSAGE.format(minutes=minutes, at=at)
    raise RefreshRefused(TOO_SOON, message, retry_after=(ends - now).total_seconds())


async def _claimed(session: AsyncSession, ask: RefreshAsk, *, now: datetime) -> uuid.UUID | None:
    owners = (
        None
        if ask.owners is None
        else {"crafts": [*ask.owners.crafts], "categories": [*ask.owners.categories]}
    )
    statement = (
        insert(PageRefreshJob)
        .values(
            scope=ask.scope,
            origin=ask.origin,
            startedById=None if ask.actor is None else ask.actor.id,
            clientName=ask.client_name,
            owners=owners,
            status=RUNNING,
            startedAt=now,
        )
        .on_conflict_do_nothing(index_elements=["status"], index_where=RUNNING_ONLY)
        .returning(PageRefreshJob.id)
    )
    found: uuid.UUID | None = (await session.execute(statement)).scalar_one_or_none()
    return found


async def _busy_message(session: AsyncSession) -> str:
    origin = await session.scalar(select(PageRefreshJob.origin).where(PageRefreshJob.status == RUNNING))
    return NIGHT_BUSY_MESSAGE if origin == NIGHT_ORIGIN else BUSY_MESSAGE


async def _last_start(session: AsyncSession, condition: Any) -> datetime | None:
    found: datetime | None = await session.scalar(select(func.max(PageRefreshJob.startedAt)).where(condition))
    return found


async def _latest(session: AsyncSession, condition: Any) -> RefreshJobView | None:
    row = (
        await session.execute(
            select(PageRefreshJob, User.name)
            .outerjoin(User, User.id == PageRefreshJob.startedById)
            .where(condition)
            .order_by(PageRefreshJob.startedAt.desc())
            .limit(1)
        )
    ).first()
    if row is None:
        return None
    job, name = row
    return RefreshJobView(
        id=job.id,
        scope=job.scope,
        origin=job.origin,
        status=job.status,
        phase=job.phase,
        started_by=name,
        client_name=job.clientName,
        started_at=job.startedAt,
        finished_at=job.finishedAt,
        progress=RefreshProgress.model_validate(job.progress or {}),
        note=job.note,
    )
