from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from sqlalchemy import Float, Integer, cast, delete, func, literal, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import aliased

from app.core.config import get_settings
from app.core.db import build_runtime_database_url
from app.models import AllowanceBucket

__all__ = [
    "ALLOWANCE_UNREAD",
    "COUNTING_POOL_OVERFLOW",
    "COUNTING_POOL_SIZE",
    "COUNT_SECONDS",
    "HOUR_SECONDS",
    "KEPT_HOURS",
    "UNREAD_WAIT_SECONDS",
    "AllowanceCounter",
    "AllowanceUnread",
    "Ask",
    "Bucket",
    "Counted",
    "SharedCounter",
    "Taken",
    "bucket_of",
    "counting_engine",
    "delete_old_buckets",
    "earlier_share",
    "give_back",
    "sliding_wait",
    "take",
    "take_sliding",
    "taken_from",
]

logger = logging.getLogger(__name__)

HOUR_SECONDS = 3600
WINDOWS_FROM = datetime(1970, 1, 1, tzinfo=UTC)
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
    start: datetime
    seconds: int

    @property
    def end(self) -> datetime:
        return self.start + timedelta(seconds=self.seconds)

    @property
    def before(self) -> Bucket:
        return Bucket(self.holder, self.kind, self.start - timedelta(seconds=self.seconds), self.seconds)


@dataclass(frozen=True)
class Ask:
    wanted: int
    limit: int
    earlier_share: float = 0.0


@dataclass(frozen=True)
class Counted:
    granted: int
    used: int
    earlier: int


@dataclass(frozen=True)
class Taken:
    granted: int
    wait_seconds: float = 0.0
    unread: bool = False


_UNREAD = Taken(granted=0, wait_seconds=UNREAD_WAIT_SECONDS, unread=True)


class AllowanceCounter(Protocol):
    async def take(self, bucket: Bucket, ask: Ask) -> Counted: ...

    async def give_back(self, bucket: Bucket) -> None: ...


class SharedCounter:
    def __init__(self, sessions: Sessions | None = None, *, seconds: float = COUNT_SECONDS) -> None:
        self._given = sessions
        self._own: AsyncEngine | None = None
        self._made: Sessions | None = None
        self._seconds = seconds

    async def take(self, bucket: Bucket, ask: Ask) -> Counted:
        async with self._counting(bucket, "counted") as session:
            row = (await session.execute(_taking(bucket, ask))).one()
        return Counted(granted=int(row.lastTaken), used=int(row.used), earlier=int(row.earlier))

    async def give_back(self, bucket: Bucket) -> None:
        async with self._counting(bucket, "given back") as session:
            await session.execute(_giving_back(bucket))

    async def dispose(self) -> None:
        if self._own is not None:
            await self._own.dispose()
        self._own, self._made = None, None

    @asynccontextmanager
    async def _counting(self, bucket: Bucket, done: str) -> AsyncIterator[AsyncSession]:
        try:
            async with asyncio.timeout(self._seconds), self._sessions()() as session:
                yield session
                await session.commit()
        except (SQLAlchemyError, OSError, TimeoutError) as error:
            raise AllowanceUnread(f"the {bucket.kind} allowance of {bucket.holder} was not {done}") from error

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


def bucket_of(holder: str, kind: str, now: datetime, *, seconds: int = HOUR_SECONDS) -> Bucket:
    if now.tzinfo is None:
        raise ValueError("an allowance is counted at an aware moment, not a naive one")
    if seconds < 1:
        raise ValueError(f"a window lasts at least one second, not {seconds}")
    length = timedelta(seconds=seconds)
    start = WINDOWS_FROM + (now - WINDOWS_FROM) // length * length
    return Bucket(holder=holder, kind=kind, start=start, seconds=seconds)


def earlier_share(bucket: Bucket, now: datetime) -> float:
    left = (bucket.end - now).total_seconds()
    return min(1.0, max(0.0, left / bucket.seconds))


def taken_from(granted: int, wanted: int, *, bucket: Bucket, now: datetime) -> Taken:
    if granted >= wanted:
        return Taken(granted=wanted)
    return Taken(granted=granted, wait_seconds=max(0.0, (bucket.end - now).total_seconds()))


def sliding_wait(counted: Counted, limit: int, *, bucket: Bucket, now: datetime) -> float:
    left = (bucket.end - now).total_seconds()
    room = limit - 1 - counted.used
    if room >= 0:
        return max(0.0, left - bucket.seconds * room / max(1, counted.earlier))
    return left + bucket.seconds * (counted.used - (limit - 1)) / counted.used


async def take(holder: str, kind: str, wanted: int, limit: int, *, now: datetime | None = None) -> Taken:
    if wanted < 1:
        return Taken(granted=0)
    moment = _moment(now)
    bucket = bucket_of(holder, kind, moment)
    counted = await _counted(bucket, Ask(wanted=wanted, limit=limit))
    if counted is None:
        return _UNREAD
    return taken_from(counted.granted, wanted, bucket=bucket, now=moment)


async def take_sliding(
    holder: str, kind: str, limit: int, *, seconds: int, now: datetime | None = None
) -> Taken:
    moment = _moment(now)
    bucket = bucket_of(holder, kind, moment, seconds=seconds)
    ask = Ask(wanted=1, limit=limit, earlier_share=earlier_share(bucket, moment))
    counted = await _counted(bucket, ask)
    if counted is None:
        return _UNREAD
    if counted.granted:
        return Taken(granted=counted.granted)
    return Taken(granted=0, wait_seconds=sliding_wait(counted, limit, bucket=bucket, now=moment))


async def give_back(holder: str, kind: str, *, seconds: int, now: datetime | None = None) -> None:
    bucket = bucket_of(holder, kind, _moment(now), seconds=seconds)
    try:
        await counter.give_back(bucket)
    except AllowanceUnread as unread:
        logger.error("%s; the count stays as it was: %s", unread, unread.__cause__)


async def delete_old_buckets(session: AsyncSession, *, now: datetime) -> int:
    cutoff = bucket_of("", "", now).start - timedelta(hours=KEPT_HOURS)
    result: Any = await session.execute(delete(AllowanceBucket).where(AllowanceBucket.hourStart < cutoff))
    return int(result.rowcount or 0)


def _moment(now: datetime | None) -> datetime:
    return now if now is not None else datetime.now(UTC)


async def _counted(bucket: Bucket, ask: Ask) -> Counted | None:
    try:
        return await counter.take(bucket, ask)
    except AllowanceUnread as unread:
        logger.error("%s; the call is refused: %s", unread, unread.__cause__)
        return None


def _taking(bucket: Bucket, ask: Ask) -> Any:
    earlier = _earlier_used(bucket)
    carried = cast(func.ceil(earlier * literal(ask.earlier_share, Float)), Integer)
    first = func.least(ask.wanted, func.greatest(0, ask.limit - carried))
    granted = func.least(ask.wanted, func.greatest(0, ask.limit - AllowanceBucket.used - carried))
    statement = insert(AllowanceBucket).values(
        holder=bucket.holder, kind=bucket.kind, hourStart=bucket.start, used=first, lastTaken=first
    )
    return statement.on_conflict_do_update(
        index_elements=[AllowanceBucket.holder, AllowanceBucket.kind, AllowanceBucket.hourStart],
        set_={"used": AllowanceBucket.used + granted, "lastTaken": granted},
    ).returning(AllowanceBucket.lastTaken, AllowanceBucket.used, earlier.label("earlier"))


def _earlier_used(bucket: Bucket) -> Any:
    earlier = aliased(AllowanceBucket, name="earlier")
    used = select(earlier.used).where(
        earlier.holder == bucket.holder,
        earlier.kind == bucket.kind,
        earlier.hourStart == bucket.before.start,
    )
    return func.coalesce(used.scalar_subquery(), 0)


def _giving_back(bucket: Bucket) -> Any:
    left = func.greatest(AllowanceBucket.used - 1, 0)
    return (
        update(AllowanceBucket)
        .where(
            AllowanceBucket.holder == bucket.holder,
            AllowanceBucket.kind == bucket.kind,
            AllowanceBucket.hourStart == bucket.start,
        )
        .values(used=left, lastTaken=func.least(AllowanceBucket.lastTaken, left))
        .execution_options(synchronize_session=False)
    )
