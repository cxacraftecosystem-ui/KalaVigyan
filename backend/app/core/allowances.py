from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from sqlalchemy import delete, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.db import build_runtime_database_url
from app.models import AllowanceBucket

__all__ = [
    "ALLOWANCE_UNREAD",
    "BUCKET_HOUR",
    "COUNTING_POOL_OVERFLOW",
    "COUNTING_POOL_SIZE",
    "COUNT_SECONDS",
    "KEPT_HOURS",
    "UNREAD_WAIT_SECONDS",
    "AllowanceCounter",
    "AllowanceUnread",
    "Ask",
    "Bucket",
    "SharedCounter",
    "Taken",
    "bucket_of",
    "counting_engine",
    "delete_old_buckets",
    "take",
    "taken_from",
]

logger = logging.getLogger(__name__)

BUCKET_HOUR = timedelta(hours=1)
COUNT_SECONDS = 5.0
UNREAD_WAIT_SECONDS = 60.0
KEPT_HOURS = 24
COUNTING_POOL_SIZE = 2
COUNTING_POOL_OVERFLOW = 6
COUNTING_POOL_RECYCLE_SECONDS = 1800
ALLOWANCE_UNREAD = (
    "KalaVigyan could not count this call against the account's hourly allowance just now, "
    "so nothing was done. Try again in a minute."
)

Sessions = async_sessionmaker[AsyncSession]


class AllowanceUnread(Exception):
    pass


@dataclass(frozen=True)
class Bucket:
    holder: str
    kind: str
    hour: datetime


@dataclass(frozen=True)
class Ask:
    wanted: int
    limit: int


@dataclass(frozen=True)
class Taken:
    granted: int
    wait_seconds: float = 0.0
    unread: bool = False


class AllowanceCounter(Protocol):
    async def take(self, bucket: Bucket, ask: Ask) -> int: ...


class SharedCounter:
    def __init__(self, sessions: Sessions | None = None, *, seconds: float = COUNT_SECONDS) -> None:
        self._given = sessions
        self._own: AsyncEngine | None = None
        self._made: Sessions | None = None
        self._seconds = seconds

    async def take(self, bucket: Bucket, ask: Ask) -> int:
        try:
            async with asyncio.timeout(self._seconds), self._sessions()() as session:
                granted = (await session.execute(_taking(bucket, ask))).scalar_one()
                await session.commit()
        except (SQLAlchemyError, OSError, TimeoutError) as error:
            raise AllowanceUnread(
                f"the {bucket.kind} allowance of {bucket.holder} was not counted"
            ) from error
        return int(granted)

    async def dispose(self) -> None:
        if self._own is not None:
            await self._own.dispose()
        self._own, self._made = None, None

    def _sessions(self) -> Sessions:
        if self._given is not None:
            return self._given
        if self._made is None:
            self._own = counting_engine(self._seconds)
            self._made = async_sessionmaker(self._own, expire_on_commit=False, autoflush=False)
        return self._made


def counting_engine(seconds: float) -> AsyncEngine:
    runtime = build_runtime_database_url(get_settings().database_url)
    return create_async_engine(
        runtime.url,
        connect_args=runtime.connect_args,
        pool_size=COUNTING_POOL_SIZE,
        max_overflow=COUNTING_POOL_OVERFLOW,
        pool_timeout=seconds,
        pool_pre_ping=True,
        pool_recycle=COUNTING_POOL_RECYCLE_SECONDS,
    )


counter: AllowanceCounter = SharedCounter()


def bucket_of(holder: str, kind: str, now: datetime) -> Bucket:
    if now.tzinfo is None:
        raise ValueError("an allowance is counted at an aware moment, not a naive one")
    hour = now.astimezone(UTC).replace(minute=0, second=0, microsecond=0)
    return Bucket(holder=holder, kind=kind, hour=hour)


def taken_from(granted: int, wanted: int, *, bucket: Bucket, now: datetime) -> Taken:
    if granted >= wanted:
        return Taken(granted=wanted)
    return Taken(granted=granted, wait_seconds=max(0.0, (bucket.hour + BUCKET_HOUR - now).total_seconds()))


async def take(holder: str, kind: str, wanted: int, limit: int, *, now: datetime | None = None) -> Taken:
    if wanted < 1:
        return Taken(granted=0)
    moment = now if now is not None else datetime.now(UTC)
    bucket = bucket_of(holder, kind, moment)
    try:
        granted = await counter.take(bucket, Ask(wanted=wanted, limit=limit))
    except AllowanceUnread as unread:
        logger.error("%s; the call is refused: %s", unread, unread.__cause__)
        return Taken(granted=0, wait_seconds=UNREAD_WAIT_SECONDS, unread=True)
    return taken_from(granted, wanted, bucket=bucket, now=moment)


async def delete_old_buckets(session: AsyncSession, *, now: datetime) -> int:
    cutoff = bucket_of("", "", now).hour - timedelta(hours=KEPT_HOURS)
    result: Any = await session.execute(delete(AllowanceBucket).where(AllowanceBucket.hourStart < cutoff))
    return int(result.rowcount or 0)


def _taking(bucket: Bucket, ask: Ask) -> Any:
    first = min(ask.wanted, max(0, ask.limit))
    statement = insert(AllowanceBucket).values(
        holder=bucket.holder, kind=bucket.kind, hourStart=bucket.hour, used=first, lastTaken=first
    )
    left = func.greatest(0, ask.limit - AllowanceBucket.used)
    granted = func.least(ask.wanted, left)
    return statement.on_conflict_do_update(
        index_elements=[AllowanceBucket.holder, AllowanceBucket.kind, AllowanceBucket.hourStart],
        set_={"used": AllowanceBucket.used + granted, "lastTaken": granted},
    ).returning(AllowanceBucket.lastTaken)
