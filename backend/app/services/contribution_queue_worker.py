from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import aliased

from app.core.errors import InvalidInput, Refused
from app.core.logging import request_id_scope
from app.models import QueuedProposal, User
from app.models.contributions import QUEUE_FAILURE_CHARS
from app.research.contribution_queue import (
    ATTEMPTS_MAX,
    CHECKING,
    DONE,
    FAILED,
    LEASE_TIME,
    QUEUED,
    retry_delay,
    stream_request_id,
)
from app.research.knowledge_writes import FactProposal, ProposalReply

from .claim_pages import published_claims, refresh_claim_pages
from .cost_ledger import stream_spend
from .fact_proposals import ProposalAdapters, ProposalRun, embed_sources, propose_fact_run

__all__ = ["AdaptersFor", "ContributionWorker", "WorkerSettings", "claim_next", "drain", "work_on"]

logger = logging.getLogger(__name__)

NO_PROPOSER = "the account behind this proposal no longer exists"

AdaptersFor = Callable[[User], ProposalAdapters]
Clock = Callable[[], datetime]
Sessions = async_sessionmaker[AsyncSession]


@dataclass(frozen=True)
class WorkerSettings:
    concurrency: int = 4
    idle_seconds: float = 2.0


def utc_now() -> datetime:
    return datetime.now(UTC)


async def claim_next(session: AsyncSession, *, now: datetime) -> uuid.UUID | None:
    other = aliased(QueuedProposal, name="other")
    busy = (
        select(other.id)
        .where(other.subjectKey == QueuedProposal.subjectKey, other.state == CHECKING, other.leaseUntil > now)
        .exists()
    )
    ready = or_(
        and_(QueuedProposal.state == QUEUED, QueuedProposal.availableAt <= now),
        and_(QueuedProposal.state == CHECKING, QueuedProposal.leaseUntil <= now),
    )
    picked = await session.scalar(
        select(QueuedProposal.id)
        .where(ready, ~busy)
        .order_by(QueuedProposal.availableAt, QueuedProposal.createdAt, QueuedProposal.id)
        .limit(1)
        .with_for_update(skip_locked=True, of=QueuedProposal)
    )
    if picked is not None:
        await session.execute(
            update(QueuedProposal)
            .where(QueuedProposal.id == picked)
            .values(
                state=CHECKING,
                attempts=QueuedProposal.attempts + 1,
                leaseUntil=now + LEASE_TIME,
                startedAt=func.coalesce(QueuedProposal.startedAt, now),
            )
        )
    await session.commit()
    return picked


async def work_on(
    session: AsyncSession, proposal_id: uuid.UUID, adapters_for: AdaptersFor, *, clock: Clock = utc_now
) -> str | None:
    row = await session.get(QueuedProposal, proposal_id, populate_existing=True)
    if row is None or row.state != CHECKING:
        return None
    proposer = await session.get(User, row.proposerId)
    if proposer is None:
        _ended(row, FAILED, NO_PROPOSER, now=clock())
        await session.commit()
        return row.state
    adapters = adapters_for(proposer)
    try:
        async with session.begin_nested():
            with request_id_scope(stream_request_id(proposal_id)):
                ran = await propose_fact_run(
                    session,
                    FactProposal.model_validate(row.proposal),
                    proposer,
                    row.origin,
                    adapters=adapters,
                    now=clock(),
                    ticket=proposal_id,
                )
    except Refused as refused:
        _ended(await _fresh(session, row), FAILED, refused.message, now=clock())
    except InvalidInput as invalid:
        _ended(await _fresh(session, row), FAILED, str(invalid), now=clock())
    except Exception as failure:
        logger.warning("queued proposal %s could not be checked: %s", proposal_id, failure)
        _retried(await _fresh(session, row), str(failure) or type(failure).__name__, now=clock())
    else:
        await _done(session, row, ran.reply, now=clock())
        await session.commit()
        await refresh_claim_pages(session, published_claims(ran.reply))
        await _embedded(session, adapters, ran, row)
    await session.commit()
    return row.state


async def drain(
    sessions: Callable[[], AbstractAsyncContextManager[AsyncSession]],
    adapters_for: AdaptersFor,
    *,
    clock: Clock = utc_now,
    limit: int = 100,
) -> int:
    worked = 0
    while worked < limit:
        async with sessions() as session:
            claimed = await claim_next(session, now=clock())
            if claimed is None:
                return worked
            await work_on(session, claimed, adapters_for, clock=clock)
        worked += 1
    return worked


class ContributionWorker:
    def __init__(
        self, sessions: Sessions, adapters_for: AdaptersFor, settings: WorkerSettings = WorkerSettings()
    ) -> None:
        self._sessions = sessions
        self._adapters_for = adapters_for
        self._settings = settings

    async def run(self, stop: asyncio.Event) -> None:
        slots = asyncio.Semaphore(max(1, self._settings.concurrency))
        running: set[asyncio.Task[None]] = set()
        while not stop.is_set():
            await slots.acquire()
            claimed = await self._claim()
            if claimed is None:
                slots.release()
                await _pause(stop, self._settings.idle_seconds)
                continue
            task = asyncio.create_task(self._work(claimed, slots))
            running.add(task)
            task.add_done_callback(running.discard)
        if running:
            await asyncio.gather(*running, return_exceptions=True)

    async def _claim(self) -> uuid.UUID | None:
        try:
            async with self._sessions() as session:
                return await claim_next(session, now=utc_now())
        except Exception:
            logger.exception("the contribution queue could not be read")
            return None

    async def _work(self, proposal_id: uuid.UUID, slots: asyncio.Semaphore) -> None:
        try:
            async with self._sessions() as session:
                await work_on(session, proposal_id, self._adapters_for)
        except Exception:
            logger.exception("queued proposal %s stopped; its lease returns it to the queue", proposal_id)
        finally:
            slots.release()


async def _done(session: AsyncSession, row: QueuedProposal, reply: ProposalReply, *, now: datetime) -> None:
    calls, cost = await stream_spend(session, row.id)
    row.state, row.outcome, row.claimId = DONE, reply.outcome, reply.claim_id
    row.reply = reply.model_dump(mode="json", by_alias=True)
    row.finishedAt, row.leaseUntil, row.failure = now, None, None
    row.modelCalls, row.costUsd = calls, cost


async def _embedded(
    session: AsyncSession, adapters: ProposalAdapters, ran: ProposalRun, row: QueuedProposal
) -> None:
    with request_id_scope(stream_request_id(row.id)):
        await embed_sources(session, adapters.embed, ran.kept_sources)
    row.modelCalls, row.costUsd = await stream_spend(session, row.id)


async def _fresh(session: AsyncSession, row: QueuedProposal) -> QueuedProposal:
    await session.refresh(row)
    return row


def _ended(row: QueuedProposal, state: str, failure: str, *, now: datetime) -> None:
    row.state, row.failure = state, failure[:QUEUE_FAILURE_CHARS]
    row.finishedAt, row.leaseUntil = now, None


def _retried(row: QueuedProposal, failure: str, *, now: datetime) -> None:
    if row.attempts >= ATTEMPTS_MAX:
        _ended(row, FAILED, failure, now=now)
        return
    row.state, row.failure, row.leaseUntil = QUEUED, failure[:QUEUE_FAILURE_CHARS], None
    row.availableAt = now + retry_delay(row.attempts)


async def _pause(stop: asyncio.Event, seconds: float) -> None:
    try:
        await asyncio.wait_for(stop.wait(), timeout=seconds)
    except TimeoutError:
        return
