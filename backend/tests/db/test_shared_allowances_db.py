import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core import allowances
from app.core.allowances import AllowanceUnread, Ask, SharedCounter, Taken, bucket_of, take
from app.core.db import sessionmaker
from app.core.errors import InvalidInput
from app.core.rate_limit import SOURCE_READS, SOURCE_SEARCHES
from app.models import AllowanceBucket
from app.services.source_lookup_allowance import LookupCaller, spend
from app.services.upkeep_allowances import sweep_allowances

pytestmark = pytest.mark.db

NOW = datetime(2026, 11, 21, 10, 30, tzinfo=UTC)
HOUR_END = datetime(2026, 11, 21, 10, 59, 59, 500000, tzinfo=UTC)
NEXT_HOUR = datetime(2026, 11, 21, 11, 0, tzinfo=UTC)
UNREACHABLE = "postgresql+psycopg://nobody:nothing@127.0.0.1:1/nowhere"


def holder() -> str:
    return f"test-{uuid.uuid4()}"


@pytest.fixture
async def shared(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[SharedCounter]:
    counter = SharedCounter()
    monkeypatch.setattr(allowances, "counter", counter)
    yield counter
    await counter.dispose()


@pytest.fixture
async def two_processes() -> AsyncIterator[tuple[SharedCounter, SharedCounter]]:
    first, second = SharedCounter(), SharedCounter()
    yield first, second
    for counter in (first, second):
        await counter.dispose()


async def stored(bucket: allowances.Bucket) -> AllowanceBucket | None:
    async with sessionmaker()() as session:
        return await session.get(AllowanceBucket, (bucket.holder, bucket.kind, bucket.hour))


async def test_two_processes_counting_at_once_never_grant_more_than_the_limit(
    two_processes: tuple[SharedCounter, SharedCounter],
) -> None:
    bucket = bucket_of(holder(), SOURCE_SEARCHES, NOW)
    calls = [two_processes[n % 2].take(bucket, Ask(wanted=1, limit=30)) for n in range(40)]
    granted = await asyncio.gather(*calls)
    assert sorted(granted) == [0] * 10 + [1] * 30
    row = await stored(bucket)
    assert row is not None and (row.used, row.lastTaken) == (30, 0)


async def test_a_batch_is_granted_what_is_left_of_the_hour(shared: SharedCounter) -> None:
    who = holder()
    assert await take(who, SOURCE_READS, 25, 30, now=NOW) == Taken(granted=25)
    assert await take(who, SOURCE_READS, 10, 30, now=NOW) == Taken(granted=5, wait_seconds=1800.0)
    assert await take(who, SOURCE_READS, 40, 60, now=NOW) == Taken(granted=30, wait_seconds=1800.0)
    row = await stored(bucket_of(who, SOURCE_READS, NOW))
    assert row is not None and row.used == 60


async def test_the_hour_s_end_opens_a_fresh_bucket(shared: SharedCounter) -> None:
    who = holder()
    assert await take(who, SOURCE_READS, 3, 3, now=HOUR_END) == Taken(granted=3)
    assert await take(who, SOURCE_READS, 1, 3, now=HOUR_END) == Taken(granted=0, wait_seconds=0.5)
    assert await take(who, SOURCE_READS, 1, 3, now=NEXT_HOUR) == Taken(granted=1)
    assert (await stored(bucket_of(who, SOURCE_READS, NEXT_HOUR))) is not None


@pytest.mark.parametrize(("tier", "searches"), [("NEW", 30), ("ESTABLISHED", 60), ("PROVEN", 120)])
async def test_each_trust_tier_searches_as_often_as_its_tier_allows_in_an_hour(
    shared: SharedCounter, tier: str, searches: int
) -> None:
    caller = LookupCaller(holder=holder(), tier=tier)
    for _ in range(searches):
        await spend(SOURCE_SEARCHES, caller, now=NOW)
    with pytest.raises(InvalidInput, match=f"made {searches} source searches this hour"):
        await spend(SOURCE_SEARCHES, caller, now=NOW)
    other = LookupCaller(holder=holder(), tier=tier)
    await spend(SOURCE_SEARCHES, other, now=NOW)


async def test_a_count_that_cannot_reach_the_database_refuses_the_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_async_engine(UNREACHABLE, connect_args={"connect_timeout": 2})
    monkeypatch.setattr(allowances, "counter", SharedCounter(async_sessionmaker(engine)))
    try:
        assert await take(holder(), SOURCE_READS, 1, 120, now=NOW) == Taken(
            granted=0, wait_seconds=60.0, unread=True
        )
        with pytest.raises(InvalidInput, match="could not count this call"):
            await spend(SOURCE_READS, LookupCaller(holder=holder(), tier="PROVEN"), now=NOW)
    finally:
        await engine.dispose()


async def test_a_count_held_up_past_its_time_by_a_locked_bucket_refuses_the_call(
    two_processes: tuple[SharedCounter, SharedCounter],
) -> None:
    bucket = bucket_of(holder(), SOURCE_READS, NOW)
    first, _ = two_processes
    assert await first.take(bucket, Ask(wanted=1, limit=120)) == 1
    slow = SharedCounter(seconds=0.5)
    try:
        async with sessionmaker()() as holding:
            await _lock(holding, bucket)
            with pytest.raises(AllowanceUnread):
                await slow.take(bucket, Ask(wanted=1, limit=120))
            await holding.rollback()
    finally:
        await slow.dispose()
    row = await stored(bucket)
    assert row is not None and row.used == 1


async def test_the_nightly_upkeep_deletes_the_buckets_of_hours_over_a_day_old(shared: SharedCounter) -> None:
    old, recent = holder(), holder()
    await take(old, SOURCE_READS, 1, 5, now=NOW - timedelta(hours=25))
    await take(recent, SOURCE_READS, 1, 5, now=NOW - timedelta(hours=23))
    async with sessionmaker()() as session:
        report = await sweep_allowances(session, now=NOW)
    assert report.deleted >= 1
    assert await stored(bucket_of(old, SOURCE_READS, NOW - timedelta(hours=25))) is None
    assert await stored(bucket_of(recent, SOURCE_READS, NOW - timedelta(hours=23))) is not None


async def _lock(session: AsyncSession, bucket: allowances.Bucket) -> None:
    await session.execute(
        select(AllowanceBucket)
        .where(
            AllowanceBucket.holder == bucket.holder,
            AllowanceBucket.kind == bucket.kind,
            AllowanceBucket.hourStart == bucket.hour,
        )
        .with_for_update()
    )
