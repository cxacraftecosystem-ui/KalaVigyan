from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Job, MediaAsset, MediaJob, Process, ProcessStage
from app.models.science import live_process
from app.providers.quota import record_units, used_today
from app.schemas.media import JOB_RETRIES, MEDIA_PROMPT_VERSION
from app.services.knowledge_view import resolve_craft

from .heartbeat import worker_listening_at
from .records import (
    JOB_KIND,
    MEDIA_QUEUES,
    AssetRecord,
    ClaimFacts,
    CraftFacts,
    Created,
    CreateLimits,
    JobRecord,
    NewJob,
    StageFacts,
)
from .rows import asset_record, craft_facts, job_params, job_record, stage_claims, stage_facts

__all__ = ["OPEN_STATUSES", "SqlMediaStore", "queue_key"]

OPEN_STATUSES = ("QUEUED", "RUNNING")
SHARED = "CRAFT_SHARED"


def queue_key(job_id: uuid.UUID) -> str:
    return f"media-job:{job_id}"


class SqlMediaStore:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def craft_stages(self, slug: str) -> tuple[CraftFacts, list[StageFacts]] | None:
        async with self._sessions() as session:
            craft = await resolve_craft(session, slug)
            if craft is None:
                return None
            ids = (
                await session.scalars(
                    select(ProcessStage.id)
                    .join(Process, Process.id == ProcessStage.processId)
                    .where(Process.craftId == craft.id, live_process())
                    .order_by(Process.name, Process.variant, ProcessStage.ordinal, ProcessStage.id)
                )
            ).all()
            stages = await stage_facts(session, ids)
            facts = (await craft_facts(session, [craft]))[craft.id]
        return facts, [stages[stage_id] for stage_id in ids]

    async def stage(self, stage_id: uuid.UUID) -> StageFacts | None:
        async with self._sessions() as session:
            return (await stage_facts(session, [stage_id])).get(stage_id)

    async def stage_claims(self, stage_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, list[ClaimFacts]]:
        async with self._sessions() as session:
            return await stage_claims(session, stage_ids)

    async def units_used(self, user_id: uuid.UUID, kind: str, now: datetime) -> int:
        async with self._sessions() as session:
            return await used_today(session, user_id=user_id, resource=kind, now=now)

    async def worker_listening(self, now: datetime) -> bool:
        async with self._sessions() as session:
            return await worker_listening_at(session, now)

    async def active_jobs(self, user_id: uuid.UUID) -> int:
        async with self._sessions() as session:
            return await _active_jobs(session, user_id)

    async def job_by_key(self, key_hash: str) -> JobRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(select(MediaJob).where(MediaJob.idempotencyKey == key_hash))
            return None if row is None else job_record(row)

    async def job(self, job_id: uuid.UUID) -> JobRecord | None:
        async with self._sessions() as session:
            row = await session.get(MediaJob, job_id)
            return None if row is None else job_record(row)

    async def asset(self, asset_id: uuid.UUID) -> AssetRecord | None:
        async with self._sessions() as session:
            row = await session.get(MediaAsset, asset_id)
            return None if row is None else asset_record(row)

    async def shared_asset(self, prompt_hash: str) -> AssetRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(MediaAsset)
                .join(MediaJob, MediaJob.id == MediaAsset.jobId)
                .where(MediaJob.promptHash == prompt_hash, MediaAsset.visibility == SHARED)
                .order_by(MediaAsset.createdAt.desc(), MediaAsset.id)
                .limit(1)
            )
            return None if row is None else asset_record(row)

    async def create(self, job: NewJob, limits: CreateLimits) -> Created:
        record = job.record
        async with self._sessions() as session, session.begin():
            await _lock_user(session, record.requested_by)
            if await session.scalar(select(MediaJob.id).where(MediaJob.idempotencyKey == job.key_hash)):
                return Created.REPEATED
            if await _active_jobs(session, record.requested_by) >= limits.max_active:
                return Created.BUSY
            used = await used_today(
                session, user_id=record.requested_by, resource=record.kind, now=limits.now
            )
            if limits.allowance is not None and used + 1 > limits.allowance:
                return Created.NO_UNITS
            session.add(_media_job_row(job))
            await session.flush()
            if job.ledger is not None:
                await record_units(session, job.ledger)
            session.add(_queue_row(record))
        return Created.CREATED

    async def create_cached(self, job: NewJob) -> Created:
        async with self._sessions() as session, session.begin():
            await _lock_user(session, job.record.requested_by)
            if await session.scalar(select(MediaJob.id).where(MediaJob.idempotencyKey == job.key_hash)):
                return Created.REPEATED
            session.add(_media_job_row(job))
        return Created.CREATED


async def _lock_user(session: AsyncSession, user_id: uuid.UUID | None) -> None:
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": f"media-user:{user_id}"}
    )


async def _active_jobs(session: AsyncSession, user_id: uuid.UUID | None) -> int:
    count = await session.scalar(
        select(func.count())
        .select_from(MediaJob)
        .where(MediaJob.requestedById == user_id, MediaJob.status.in_(OPEN_STATUSES))
    )
    return int(count or 0)


def _media_job_row(job: NewJob) -> MediaJob:
    record = job.record
    return MediaJob(
        id=record.id,
        kind=record.kind,
        requestedById=record.requested_by,
        craftId=job.craft_id,
        stageId=record.stage_id,
        claimIds=list(record.claim_ids),
        prompt=record.prompt,
        promptVersion=MEDIA_PROMPT_VERSION,
        promptHash=record.prompt_hash,
        model=record.model,
        params=job_params(record),
        status=record.status,
        attempts=record.attempts,
        idempotencyKey=job.key_hash,
        bundle=dict(record.bundle) if record.bundle is not None else None,
        assetId=record.asset_id,
        createdAt=record.created_at,
        updatedAt=record.updated_at,
    )


def _queue_row(record: JobRecord) -> Job:
    return Job(
        queue=MEDIA_QUEUES[record.kind],
        kind=JOB_KIND,
        payload={"mediaJobId": str(record.id)},
        status="QUEUED",
        maxAttempts=JOB_RETRIES + 1,
        idempotencyKey=queue_key(record.id),
    )
