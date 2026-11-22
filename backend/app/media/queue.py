from __future__ import annotations

import asyncio
import contextlib
import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta

from sqlalchemy.exc import SQLAlchemyError

from app.providers.budget import RESERVATION_TTL
from app.schemas.media import JOB_TIMEOUT_SECONDS, QUEUE_CONCURRENCY

from .records import MEDIA_QUEUES, QueueStore

__all__ = [
    "DRAIN_SECONDS",
    "HOLD_RENEW_AFTER",
    "HOLD_RENEW_EVERY",
    "IDLE_SECONDS",
    "STALE_AFTER",
    "MediaQueue",
]

logger = logging.getLogger(__name__)

IDLE_SECONDS = 2.0
DRAIN_SECONDS = 25.0
STALE_AFTER = timedelta(seconds=JOB_TIMEOUT_SECONDS + 120)
HOLD_RENEW_AFTER = RESERVATION_TTL / 2
HOLD_RENEW_EVERY = timedelta(minutes=1)

JobStep = Callable[[uuid.UUID], Awaitable[str]]


class MediaQueue:
    def __init__(
        self,
        *,
        store: QueueStore,
        run: JobStep,
        abandon: JobStep,
        worker_id: str,
        clock: Callable[[], datetime],
        idle_seconds: float = IDLE_SECONDS,
        drain_seconds: float = DRAIN_SECONDS,
    ) -> None:
        self._store = store
        self._run = run
        self._abandon = abandon
        self._worker_id = worker_id
        self._clock = clock
        self._idle = idle_seconds
        self._drain = drain_seconds
        self._running: dict[str, set[asyncio.Task[str]]] = {kind: set() for kind in MEDIA_QUEUES}
        self._renewed_at: datetime | None = None

    def running(self, kind: str) -> int:
        return len(self._running[kind])

    async def tick(self) -> int:
        for job_id in await self._store.stale(self._clock() - STALE_AFTER):
            await self._abandon(job_id)
        await self._renewed()
        started = 0
        for kind, tasks in self._running.items():
            free = QUEUE_CONCURRENCY[kind] - len(tasks)
            if free < 1:
                continue
            for job_id in await self._store.claim(kind, limit=free, worker_id=self._worker_id):
                self._spawn(kind, job_id)
                started += 1
        return started

    async def run(self, stop: asyncio.Event) -> None:
        while not stop.is_set():
            try:
                await self.tick()
            except SQLAlchemyError, OSError:
                logger.exception("media queue tick failed")
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=self._idle)
        await self.drain()

    async def drain(self) -> int:
        tasks = [task for running in self._running.values() for task in running]
        if not tasks:
            return 0
        _, pending = await asyncio.wait(tasks, timeout=self._drain)
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        return len(pending)

    async def _renewed(self) -> None:
        now = self._clock()
        if self._renewed_at is not None and now - self._renewed_at < HOLD_RENEW_EVERY:
            return
        self._renewed_at = now
        await self._store.renew_holds(now - HOLD_RENEW_AFTER)

    def _spawn(self, kind: str, job_id: uuid.UUID) -> None:
        task = asyncio.create_task(self._run(job_id), name=f"media-{job_id}")
        self._running[kind].add(task)
        task.add_done_callback(lambda done: self._settled(kind, job_id, done))

    def _settled(self, kind: str, job_id: uuid.UUID, task: asyncio.Task[str]) -> None:
        self._running[kind].discard(task)
        if task.cancelled():
            logger.warning("media job stopped with the worker", extra={"jobId": str(job_id)})
            return
        error = task.exception()
        if error is not None:
            logger.error("media job crashed", extra={"jobId": str(job_id)}, exc_info=error)
