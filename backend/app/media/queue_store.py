from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Text, cast, func, select, text, update
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Job, MediaAsset, MediaJob, UsageEvent
from app.providers.quota import LedgerEntry, record_units
from app.schemas.media import ASSET_LABEL, QUEUE_CONCURRENCY
from app.services.craft_ai_media import page_visibility

from .records import MEDIA_QUEUES, JobRecord, NewAsset, StageFacts
from .rows import job_record, stage_facts
from .store import queue_key

__all__ = ["SqlQueueStore"]

HOLD_PARAM = "holdId"
PRIVATE = "PRIVATE"
RESERVED = "RESERVED"


class SqlQueueStore:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def stale(self, older_than: datetime) -> list[uuid.UUID]:
        async with self._sessions() as session, session.begin():
            rows = (
                await session.scalars(
                    select(Job)
                    .where(
                        Job.queue.in_(list(MEDIA_QUEUES.values())),
                        Job.status == "RUNNING",
                        Job.lockedAt < older_than,
                    )
                    .with_for_update(skip_locked=True)
                )
            ).all()
            for row in rows:
                row.lockedAt = func.now()
            return [_media_job_id(row) for row in rows]

    async def claim(self, kind: str, *, limit: int, worker_id: str) -> list[uuid.UUID]:
        queue = MEDIA_QUEUES[kind]
        async with self._sessions() as session, session.begin():
            await session.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": queue})
            running = await session.scalar(
                select(func.count()).select_from(Job).where(Job.queue == queue, Job.status == "RUNNING")
            )
            free = min(limit, QUEUE_CONCURRENCY[kind] - int(running or 0))
            if free < 1:
                return []
            rows = (
                await session.scalars(
                    select(Job)
                    .where(Job.queue == queue, Job.status == "QUEUED", Job.runAfter <= func.now())
                    .order_by(Job.priority.desc(), Job.runAfter, Job.createdAt)
                    .limit(free)
                    .with_for_update(skip_locked=True)
                )
            ).all()
            return [await _start(session, row, worker_id) for row in rows]

    async def renew_holds(self, older_than: datetime) -> int:
        held = select(cast(MediaJob.params[HOLD_PARAM].astext, PG_UUID(as_uuid=True))).where(
            MediaJob.status == "QUEUED", MediaJob.params.has_key(HOLD_PARAM)
        )
        async with self._sessions() as session, session.begin():
            renewed = await session.execute(
                update(UsageEvent)
                .where(
                    UsageEvent.id.in_(held), UsageEvent.outcome == RESERVED, UsageEvent.createdAt < older_than
                )
                .values(createdAt=func.now())
            )
            return int(getattr(renewed, "rowcount", 0) or 0)

    async def job(self, job_id: uuid.UUID) -> JobRecord | None:
        async with self._sessions() as session:
            row = await session.get(MediaJob, job_id)
            return None if row is None else job_record(row)

    async def stage(self, stage_id: uuid.UUID) -> StageFacts | None:
        async with self._sessions() as session:
            return (await stage_facts(session, [stage_id])).get(stage_id)

    async def forget_hold(self, job_id: uuid.UUID) -> None:
        async with self._sessions() as session, session.begin():
            await session.execute(
                update(MediaJob)
                .where(MediaJob.id == job_id)
                .values(params=MediaJob.params.op("-")(cast(HOLD_PARAM, Text)))
            )

    async def succeed(
        self, job_id: uuid.UUID, asset: NewAsset, *, cost_usd: Decimal, billed_tokens: int | None
    ) -> None:
        async with self._sessions() as session, session.begin():
            session.add(_asset_row(job_id, asset))
            await session.flush()
            await _settle_rows(
                session,
                job_id,
                media={
                    "assetId": asset.id,
                    "costUsd": cost_usd,
                    "billedTokens": billed_tokens,
                    "error": None,
                },
                queue={"lastError": None},
                status="SUCCEEDED",
            )

    async def retry(self, job_id: uuid.UUID, *, error: str, run_after: datetime) -> None:
        async with self._sessions() as session, session.begin():
            await _settle_rows(
                session,
                job_id,
                media={"error": error},
                queue={"lastError": error, "runAfter": run_after},
                status="QUEUED",
            )

    async def fail(self, job_id: uuid.UUID, *, status: str, error: str, refund: LedgerEntry) -> None:
        async with self._sessions() as session, session.begin():
            await _settle_rows(
                session, job_id, media={"error": error}, queue={"lastError": error}, status=status
            )
            await record_units(session, refund)


async def _start(session: AsyncSession, row: Job, worker_id: str) -> uuid.UUID:
    row.status = "RUNNING"
    row.attempts = row.attempts + 1
    row.lockedAt = func.now()
    row.lockedBy = worker_id
    media_job_id = _media_job_id(row)
    await session.execute(
        update(MediaJob).where(MediaJob.id == media_job_id).values(status="RUNNING", attempts=row.attempts)
    )
    return media_job_id


async def _settle_rows(
    session: AsyncSession,
    job_id: uuid.UUID,
    *,
    media: dict[str, Any],
    queue: dict[str, Any],
    status: str,
) -> None:
    await session.execute(update(MediaJob).where(MediaJob.id == job_id).values(status=status, **media))
    await session.execute(
        update(Job)
        .where(Job.idempotencyKey == queue_key(job_id))
        .values(status=status, lockedAt=None, lockedBy=None, **queue)
    )


def _asset_row(job_id: uuid.UUID, asset: NewAsset) -> MediaAsset:
    return MediaAsset(
        id=asset.id,
        jobId=job_id,
        s3Key=asset.s3_key,
        mime=asset.mime,
        bytes=asset.size,
        width=asset.width,
        height=asset.height,
        durationS=None if asset.duration_seconds is None else Decimal(str(asset.duration_seconds)),
        label=ASSET_LABEL,
        model=asset.model,
        altText=asset.alt_text,
        visibility=PRIVATE
        if asset.page_key is None
        else page_visibility(depicts_named_cluster=asset.depicts_named_cluster),
        depictsNamedCluster=asset.depicts_named_cluster,
        pageKey=asset.page_key,
    )


def _media_job_id(row: Job) -> uuid.UUID:
    return uuid.UUID(str((row.payload or {})["mediaJobId"]))
