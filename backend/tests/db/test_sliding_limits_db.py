import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest

from app.core import allowances
from app.core.allowances import Ask, SharedCounter, Taken, bucket_of, give_back, take_sliding
from app.core.db import sessionmaker
from app.models import AllowanceBucket

pytestmark = pytest.mark.db

KIND = "ask"
TEN_MINUTES = 600
EARLIER = datetime(2026, 11, 22, 10, 5, tzinfo=UTC)
NOW = datetime(2026, 11, 22, 10, 12, 30, tzinfo=UTC)
LATER = datetime(2026, 11, 22, 10, 13, 45, tzinfo=UTC)


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


async def stored(who: str, moment: datetime) -> tuple[int, int] | None:
    bucket = bucket_of(who, KIND, moment, seconds=TEN_MINUTES)
    async with sessionmaker()() as session:
        row = await session.get(AllowanceBucket, (bucket.holder, bucket.kind, bucket.start))
    return None if row is None else (row.used, row.lastTaken)


async def slide(who: str, moment: datetime) -> Taken:
    return await take_sliding(who, KIND, 10, seconds=TEN_MINUTES, now=moment)


@pytest.mark.usefixtures("shared")
async def test_eight_used_in_the_previous_window_count_as_six_a_quarter_into_this_one() -> None:
    who = holder()
    assert [await slide(who, EARLIER) for _ in range(8)] == [Taken(granted=1)] * 8
    assert [await slide(who, NOW) for _ in range(4)] == [Taken(granted=1)] * 4
    assert await slide(who, NOW) == Taken(granted=0, wait_seconds=75.0)
    assert await slide(who, LATER) == Taken(granted=1)
    assert (await stored(who, EARLIER), await stored(who, NOW)) == ((8, 1), (5, 1))


async def test_two_processes_counting_a_sliding_window_at_once_share_one_limit(
    two_processes: tuple[SharedCounter, SharedCounter],
) -> None:
    who = holder()
    first, second = two_processes
    earlier = bucket_of(who, KIND, EARLIER, seconds=TEN_MINUTES)
    assert (await first.take(earlier, Ask(wanted=8, limit=8))).granted == 8
    bucket = bucket_of(who, KIND, NOW, seconds=TEN_MINUTES)
    ask = Ask(wanted=1, limit=30, earlier_share=0.75)
    counted = await asyncio.gather(*[(first, second)[n % 2].take(bucket, ask) for n in range(40)])
    assert sorted(each.granted for each in counted) == [0] * 16 + [1] * 24
    assert {each.earlier for each in counted} == {8}
    assert await stored(who, NOW) == (24, 0)


@pytest.mark.usefixtures("shared")
async def test_a_refund_gives_back_one_unit_of_the_current_window_never_below_nothing() -> None:
    who = holder()
    for _ in range(3):
        await slide(who, NOW)
    await give_back(who, KIND, seconds=TEN_MINUTES, now=NOW)
    assert await stored(who, NOW) == (2, 1)
    for _ in range(3):
        await give_back(who, KIND, seconds=TEN_MINUTES, now=NOW)
    assert await stored(who, NOW) == (0, 0)
    stranger = holder()
    await give_back(stranger, KIND, seconds=TEN_MINUTES, now=NOW)
    assert await stored(stranger, NOW) is None
