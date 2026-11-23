from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import AsyncIterator, Callable, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Protocol

from sqlalchemy import DateTime, Float, String, and_, cast, delete, extract, func, literal, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.db import counting_sessionmaker, dispose_counting_engine
from app.core.pooler import POOLER_RETRY_WAITS, connected_session
from app.models import SourceLease, SourcePace

__all__ = [
    "LEASE_LOCK_PREFIX",
    "PACE_SECONDS",
    "LeaseAsk",
    "MemoryPaces",
    "PaceAsk",
    "PaceLane",
    "PaceLease",
    "PaceSlot",
    "PaceStore",
    "PaceUnread",
    "SharedPaces",
]

PACE_SECONDS = 5.0
STORED_DIGITS = 6
LEASE_LOCK_PREFIX = "source-lease:"

Sessions = async_sessionmaker[AsyncSession]
Clock = Callable[[], float]
MOMENT = DateTime(timezone=True)


class PaceUnread(Exception):
    pass


@dataclass(frozen=True)
class PaceLane:
    service: str
    lane: str


@dataclass(frozen=True)
class PaceAsk:
    interval: float
    queue_max: float
    hold_max: float

    def __post_init__(self) -> None:
        if min(self.interval, self.queue_max, self.hold_max) < 0:
            raise ValueError("a pace's interval, queue and hold are never negative")


@dataclass(frozen=True)
class PaceSlot:
    wait: float | None
    held_for: float = 0.0

    @property
    def granted(self) -> bool:
        return self.wait is not None


@dataclass(frozen=True)
class LeaseAsk:
    concurrency: int
    seconds: float

    def __post_init__(self) -> None:
        if self.concurrency < 1 or self.seconds < 0:
            raise ValueError("a lease lets one request or more run, for a time that is never negative")


@dataclass(frozen=True)
class PaceLease:
    service: str
    lease_id: uuid.UUID


class PaceStore(Protocol):
    async def reserve(self, lane: PaceLane, ask: PaceAsk) -> PaceSlot: ...

    async def hold(self, lanes: Sequence[PaceLane], seconds: float) -> None: ...

    async def lease(self, service: str, ask: LeaseAsk) -> PaceLease | None: ...

    async def release(self, lease: PaceLease) -> None: ...


class MemoryPaces:
    def __init__(self, *, clock: Clock = time.monotonic) -> None:
        self._clock = clock
        self._free: dict[PaceLane, float] = {}
        self._held: dict[PaceLane, float] = {}
        self._leases: dict[PaceLease, float] = {}

    async def reserve(self, lane: PaceLane, ask: PaceAsk) -> PaceSlot:
        now = self._clock()
        held = self._held.get(lane, now)
        start = max(now, self._free.get(lane, now), held)
        if held - now > ask.hold_max or start - now > ask.queue_max:
            return PaceSlot(wait=None, held_for=max(held - now, 0.0))
        self._free[lane] = start + ask.interval
        return PaceSlot(wait=start - now)

    async def hold(self, lanes: Sequence[PaceLane], seconds: float) -> None:
        until = self._clock() + seconds
        for lane in lanes:
            self._held[lane] = max(self._held.get(lane, until), until)

    async def lease(self, service: str, ask: LeaseAsk) -> PaceLease | None:
        now = self._clock()
        self._leases = {found: until for found, until in self._leases.items() if until > now}
        if sum(1 for found in self._leases if found.service == service) >= ask.concurrency:
            return None
        lease = PaceLease(service, uuid.uuid4())
        self._leases[lease] = now + ask.seconds
        return lease

    async def release(self, lease: PaceLease) -> None:
        self._leases.pop(lease, None)


class SharedPaces:
    def __init__(
        self,
        sessions: Sessions | None = None,
        *,
        seconds: float = PACE_SECONDS,
        waits: Sequence[float] = POOLER_RETRY_WAITS,
    ) -> None:
        self._given = sessions
        self._seconds = seconds
        self._waits = waits

    async def reserve(self, lane: PaceLane, ask: PaceAsk) -> PaceSlot:
        async with self._transaction(f"the {lane.lane} pace of {lane.service}") as session:
            until_free = (await session.execute(_reserving(lane, ask))).scalar_one_or_none()
            held = None if until_free is not None else (await session.execute(_held_for(lane))).scalar_one()
        if until_free is not None:
            return PaceSlot(wait=max(round(float(until_free) - ask.interval, STORED_DIGITS), 0.0))
        return PaceSlot(wait=None, held_for=max(float(held or 0), 0.0))

    async def hold(self, lanes: Sequence[PaceLane], seconds: float) -> None:
        if not lanes:
            return
        async with self._transaction(f"the hold of {lanes[0].service}") as session:
            await session.execute(_holding(lanes, seconds))

    async def lease(self, service: str, ask: LeaseAsk) -> PaceLease | None:
        async with self._transaction(f"the leases of {service}") as session:
            await session.execute(_locking(service))
            lease_id = (await session.execute(_leasing(service, ask))).scalar_one_or_none()
        return None if lease_id is None else PaceLease(service, lease_id)

    async def release(self, lease: PaceLease) -> None:
        async with self._transaction(f"the lease of {lease.service}") as session:
            await session.execute(_releasing(lease))

    async def dispose(self) -> None:
        if self._given is None:
            await dispose_counting_engine()

    @asynccontextmanager
    async def _transaction(self, what: str) -> AsyncIterator[AsyncSession]:
        try:
            async with asyncio.timeout(self._seconds):
                session = await connected_session(self._sessions(), waits=self._waits)
                async with session:
                    yield session
                    await session.commit()
        except (SQLAlchemyError, OSError, TimeoutError) as error:
            raise PaceUnread(f"{what} could not be read or written") from error

    def _sessions(self) -> Sessions:
        return self._given if self._given is not None else counting_sessionmaker()


def _reserving(lane: PaceLane, ask: PaceAsk) -> Any:
    now = func.now()
    gap = timedelta(seconds=ask.interval)
    start = func.greatest(now, SourcePace.freeAt, SourcePace.heldUntil, type_=MOMENT)
    statement = insert(SourcePace).values(
        service=lane.service, lane=lane.lane, freeAt=func.now() + gap, heldUntil=func.now()
    )
    return statement.on_conflict_do_update(
        index_elements=[SourcePace.service, SourcePace.lane],
        set_={"freeAt": start + gap},
        where=(start <= func.now() + timedelta(seconds=ask.queue_max))
        & (SourcePace.heldUntil <= func.now() + timedelta(seconds=ask.hold_max)),
    ).returning(_seconds_until(SourcePace.freeAt))


def _held_for(lane: PaceLane) -> Any:
    return select(_seconds_until(SourcePace.heldUntil)).where(
        SourcePace.service == lane.service, SourcePace.lane == lane.lane
    )


def _holding(lanes: Sequence[PaceLane], seconds: float) -> Any:
    rows = [
        {
            "service": lane.service,
            "lane": lane.lane,
            "freeAt": func.now(),
            "heldUntil": func.now() + timedelta(seconds=seconds),
        }
        for lane in lanes
    ]
    statement = insert(SourcePace).values(rows)
    return statement.on_conflict_do_update(
        index_elements=[SourcePace.service, SourcePace.lane],
        set_={"heldUntil": func.greatest(SourcePace.heldUntil, statement.excluded.heldUntil, type_=MOMENT)},
    )


def _locking(service: str) -> Any:
    return select(func.pg_advisory_xact_lock(func.hashtextextended(f"{LEASE_LOCK_PREFIX}{service}", 0)))


def _leasing(service: str, ask: LeaseAsk) -> Any:
    live = (
        select(func.count())
        .select_from(SourceLease)
        .where(SourceLease.service == service, SourceLease.expiresAt > func.now())
        .scalar_subquery()
    )
    row = select(literal(service, String), func.now() + timedelta(seconds=ask.seconds)).where(
        live < ask.concurrency
    )
    return insert(SourceLease).from_select(["service", "expiresAt"], row).returning(SourceLease.id)


def _releasing(lease: PaceLease) -> Any:
    expired = and_(SourceLease.service == lease.service, SourceLease.expiresAt <= func.now())
    return delete(SourceLease).where(or_(SourceLease.id == lease.lease_id, expired))


def _seconds_until(moment: Any) -> Any:
    return cast(extract("epoch", moment - func.now()), Float)
