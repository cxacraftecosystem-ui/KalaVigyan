from __future__ import annotations

import asyncio
import logging
from collections.abc import Coroutine
from typing import Any

__all__ = ["DRAIN_SECONDS", "ShieldedWork"]

logger = logging.getLogger(__name__)

DRAIN_SECONDS = 8.0


class ShieldedWork:
    def __init__(self) -> None:
        self._running: set[asyncio.Task[Any]] = set()

    @property
    def running(self) -> int:
        return len(self._running)

    async def run[T](self, work: Coroutine[Any, Any, T], *, name: str) -> T:
        task = self._started(work, name)
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            task.add_done_callback(_report_unattended)
            raise

    async def run_within[T](self, work: Coroutine[Any, Any, T], *, name: str, seconds: float) -> T:
        task = self._started(work, name)
        try:
            return await asyncio.wait_for(asyncio.shield(task), timeout=seconds)
        except TimeoutError, asyncio.CancelledError:
            task.add_done_callback(_report_unattended)
            raise

    def start(self, work: Coroutine[Any, Any, Any], *, name: str) -> None:
        self._started(work, name).add_done_callback(_report_unattended)

    def _started[T](self, work: Coroutine[Any, Any, T], name: str) -> asyncio.Task[T]:
        task = asyncio.create_task(work, name=name)
        self._running.add(task)
        task.add_done_callback(self._running.discard)
        return task

    async def drain(self, timeout: float = DRAIN_SECONDS) -> int:
        if not self._running:
            return 0
        _, pending = await asyncio.wait(set(self._running), timeout=timeout)
        for task in pending:
            logger.warning("%s was still running when the process stopped", task.get_name())
        return len(pending)


def _report_unattended(task: asyncio.Task[Any]) -> None:
    if task.cancelled():
        logger.warning("%s was cancelled after its caller left", task.get_name())
        return
    error = task.exception()
    if error is not None:
        logger.error("%s failed after its caller left", task.get_name(), exc_info=error)
        return
    logger.info("%s finished after its caller left", task.get_name())
