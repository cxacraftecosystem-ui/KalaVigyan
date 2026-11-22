from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from pydantic import AwareDatetime, Field, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.research.base import ContractModel
from app.services.app_settings import get_value, set_value

__all__ = [
    "HEARTBEAT_SECONDS",
    "WORKER_HEARTBEAT_KEY",
    "WORKER_SILENT_AFTER",
    "WorkerHeartbeat",
    "beat",
    "worker_listening",
    "worker_listening_at",
]

WORKER_HEARTBEAT_KEY = "worker.heartbeat"
HEARTBEAT_SECONDS = 60.0
WORKER_SILENT_AFTER = timedelta(minutes=5)


class WorkerHeartbeat(ContractModel):
    at: AwareDatetime
    worker: str = Field(min_length=1, max_length=200)


async def beat(sessions: async_sessionmaker[AsyncSession], *, worker_id: str, now: datetime) -> None:
    heartbeat = WorkerHeartbeat(at=now, worker=worker_id)
    async with sessions() as session:
        await set_value(session, WORKER_HEARTBEAT_KEY, heartbeat.model_dump(mode="json", by_alias=True))
        await session.commit()


async def worker_listening_at(session: AsyncSession, now: datetime) -> bool:
    return worker_listening(await get_value(session, WORKER_HEARTBEAT_KEY), now=now)


def worker_listening(value: Any, *, now: datetime) -> bool:
    if value is None:
        return False
    try:
        heartbeat = WorkerHeartbeat.model_validate(value)
    except ValidationError:
        return False
    return now - heartbeat.at <= WORKER_SILENT_AFTER
