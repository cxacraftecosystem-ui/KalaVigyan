from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import signal
import socket
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy.exc import SQLAlchemyError

from app.core.clock import INDIA_TZ
from app.core.config import get_settings
from app.core.db import dispose_engine, sessionmaker
from app.core.errors import AppError, NotConfigured
from app.core.logging import configure_logging
from app.core.service_notify import READY, WATCHDOG, notify_service
from app.media.heartbeat import HEARTBEAT_SECONDS, beat
from app.media.wiring import media_queue
from app.voice.daily_upkeep import daily_voice_upkeep
from app.voice.score_sweep import daily_score_sweep

logger = logging.getLogger("kalavigyan.worker")

DAY_SECONDS = 86_400.0
DailyJob = Callable[[], Awaitable[dict[str, Any]]]
Beat = Callable[[], Awaitable[None]]


async def serve() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for stop_signal in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(stop_signal, stop.set)
    worker_id = f"{socket.gethostname()}:{os.getpid()}"
    notify_service(READY)
    try:
        await asyncio.gather(
            _media(stop, worker_id),
            every_day(stop, _voice_upkeep, name="daily voice upkeep"),
            every_day(stop, _score_sweep, name="daily score sweep"),
            beating(stop, lambda: beat(sessionmaker(), worker_id=worker_id, now=datetime.now(UTC))),
        )
    finally:
        await dispose_engine()


async def every_day(
    stop: asyncio.Event, job: DailyJob, *, name: str, every_seconds: float = DAY_SECONDS
) -> int:
    runs = 0
    while not stop.is_set():
        await _logged(name, job)
        runs += 1
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=every_seconds)
    return runs


async def beating(stop: asyncio.Event, heartbeat: Beat, *, every_seconds: float = HEARTBEAT_SECONDS) -> int:
    beats = 0
    while not stop.is_set():
        try:
            await heartbeat()
            beats += 1
        except SQLAlchemyError, OSError:
            logger.exception("the worker heartbeat was not written")
        notify_service(WATCHDOG)
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=every_seconds)
    return beats


async def _media(stop: asyncio.Event, worker_id: str) -> None:
    try:
        queue = media_queue(get_settings(), worker_id=worker_id)
    except NotConfigured as missing:
        logger.error("media worker idle until %s is set", missing.name)
        await stop.wait()
        return
    await queue.run(stop)


async def _voice_upkeep() -> dict[str, Any]:
    return await daily_voice_upkeep(now=datetime.now(UTC))


async def _score_sweep() -> dict[str, Any]:
    return await daily_score_sweep(today=datetime.now(INDIA_TZ).date())


async def _logged(name: str, job: DailyJob) -> None:
    try:
        report = await job()
    except AppError, SQLAlchemyError, OSError, httpx.HTTPError:
        logger.exception("%s failed", name)
        return
    if report.get("ok"):
        logger.info("%s: %s", name, json.dumps(report))
    else:
        logger.error("%s left failures: %s", name, json.dumps(report))


if __name__ == "__main__":
    asyncio.run(serve())
