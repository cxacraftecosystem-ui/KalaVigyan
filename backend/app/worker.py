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

from app.core.config import get_settings
from app.core.db import dispose_engine
from app.core.errors import AppError, NotConfigured
from app.core.logging import configure_logging
from app.media.wiring import media_queue
from app.voice.daily_upkeep import daily_voice_upkeep

logger = logging.getLogger("kalavigyan.worker")

DAY_SECONDS = 86_400.0
DailyJob = Callable[[], Awaitable[dict[str, Any]]]


async def serve() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for stop_signal in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(stop_signal, stop.set)
    try:
        await asyncio.gather(_media(stop), every_day(stop, _voice_upkeep))
    finally:
        await dispose_engine()


async def every_day(stop: asyncio.Event, job: DailyJob, *, every_seconds: float = DAY_SECONDS) -> int:
    runs = 0
    while not stop.is_set():
        await _logged(job)
        runs += 1
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=every_seconds)
    return runs


async def _media(stop: asyncio.Event) -> None:
    try:
        queue = media_queue(get_settings(), worker_id=f"{socket.gethostname()}:{os.getpid()}")
    except NotConfigured as missing:
        logger.error("media worker idle until %s is set", missing.name)
        await stop.wait()
        return
    await queue.run(stop)


async def _voice_upkeep() -> dict[str, Any]:
    return await daily_voice_upkeep(now=datetime.now(UTC))


async def _logged(job: DailyJob) -> None:
    try:
        report = await job()
    except AppError, SQLAlchemyError, OSError, httpx.HTTPError:
        logger.exception("daily voice upkeep failed")
        return
    if report.get("ok"):
        logger.info("daily voice upkeep: %s", json.dumps(report))
    else:
        logger.error("daily voice upkeep left failures: %s", json.dumps(report))


if __name__ == "__main__":
    asyncio.run(serve())
