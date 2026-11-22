from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.core import allowances
from app.core.allowances import (
    ALLOWANCE_UNREAD,
    AllowanceUnread,
    Ask,
    Bucket,
    Counted,
    SharedCounter,
    Taken,
    bucket_of,
    earlier_share,
    give_back,
    take,
    take_sliding,
    taken_from,
)
from app.core.errors import InvalidInput
from app.core.rate_limit import ANONYMOUS_HOLDER, SOURCE_SEARCHES, lookup_attempt
from app.services.source_lookup_allowance import LookupCaller, spend

from .allowance_counter import MemoryCounter

QUARTER_PAST = datetime(2026, 11, 21, 10, 15, tzinfo=UTC)
TEN = datetime(2026, 11, 21, 10, 0, tzinfo=UTC)
TEN_MINUTES = 600
ASKS = "ask"


def at(minute: int, second: int = 0) -> datetime:
    return datetime(2026, 11, 21, 10, minute, second, tzinfo=UTC)


class UnreadCounter:
    async def take(self, bucket: Bucket, ask: Ask) -> Counted:
        raise AllowanceUnread("not counted")

    async def give_back(self, bucket: Bucket) -> None:
        raise AllowanceUnread("not given back")


class NeverCounter:
    async def take(self, bucket: Bucket, ask: Ask) -> Counted:
        raise AssertionError("nothing should be counted")

    async def give_back(self, bucket: Bucket) -> None:
        raise AssertionError("nothing should be given back")


async def slide(moment: datetime, *, limit: int = 10) -> Taken:
    return await take_sliding("a", ASKS, limit, seconds=TEN_MINUTES, now=moment)


def test_a_bucket_is_the_utc_hour_of_the_moment() -> None:
    india = timezone(timedelta(hours=5, minutes=30))
    moment = datetime(2026, 11, 21, 16, 10, 42, tzinfo=india)
    assert bucket_of("a", SOURCE_SEARCHES, moment) == Bucket("a", SOURCE_SEARCHES, TEN, 3600)
    with pytest.raises(ValueError, match="aware"):
        bucket_of("a", SOURCE_SEARCHES, QUARTER_PAST.replace(tzinfo=None))


def test_a_bucket_of_any_length_starts_at_its_window_s_start() -> None:
    ten_minutes = bucket_of("a", ASKS, at(17, 30), seconds=TEN_MINUTES)
    assert (ten_minutes.start, ten_minutes.end, ten_minutes.before.start) == (at(10), at(20), at(0))
    assert bucket_of("a", ASKS, at(17, 30), seconds=900).start == at(15)


def test_the_share_of_the_previous_window_still_inside_the_sliding_window() -> None:
    bucket = bucket_of("a", ASKS, at(12, 30), seconds=TEN_MINUTES)
    assert earlier_share(bucket, at(12, 30)) == 0.75
    assert earlier_share(bucket, at(10)) == 1.0


def test_a_partial_grant_waits_for_the_end_of_its_hour() -> None:
    bucket = bucket_of("a", SOURCE_SEARCHES, QUARTER_PAST)
    assert taken_from(4, 4, bucket=bucket, now=QUARTER_PAST) == Taken(granted=4)
    assert taken_from(2, 4, bucket=bucket, now=QUARTER_PAST) == Taken(granted=2, wait_seconds=2700.0)
    assert taken_from(0, 1, bucket=bucket, now=QUARTER_PAST) == Taken(granted=0, wait_seconds=2700.0)


async def test_eight_used_in_the_previous_window_count_as_six_a_quarter_into_this_one() -> None:
    assert [await slide(at(5)) for _ in range(8)] == [Taken(granted=1)] * 8
    assert [await slide(at(12, 30)) for _ in range(4)] == [Taken(granted=1)] * 4
    assert await slide(at(12, 30)) == Taken(granted=0, wait_seconds=75.0)
    assert await slide(at(13, 44)) == Taken(granted=0, wait_seconds=1.0)
    assert await slide(at(13, 45)) == Taken(granted=1)


async def test_a_window_spent_in_full_waits_into_the_next() -> None:
    assert [await slide(at(17, 30)) for _ in range(10)] == [Taken(granted=1)] * 10
    assert await slide(at(17, 30)) == Taken(granted=0, wait_seconds=210.0)
    assert (await slide(at(20, 59))).granted == 0
    assert await slide(at(21)) == Taken(granted=1)


async def test_a_refund_gives_back_one_unit_of_the_current_window_never_below_nothing(
    allowance_counter: MemoryCounter,
) -> None:
    bucket = bucket_of("a", ASKS, at(12), seconds=TEN_MINUTES)
    for _ in range(3):
        await slide(at(12))
    await give_back("a", ASKS, seconds=TEN_MINUTES, now=at(12))
    assert allowance_counter.used[bucket] == 2
    for _ in range(3):
        await give_back("a", ASKS, seconds=TEN_MINUTES, now=at(12))
    assert allowance_counter.used[bucket] == 0
    await give_back("b", ASKS, seconds=TEN_MINUTES, now=at(12))
    assert not allowance_counter.asked("b", ASKS)


async def test_nothing_wanted_counts_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(allowances, "counter", NeverCounter())
    assert await take("a", SOURCE_SEARCHES, 0, 30, now=QUARTER_PAST) == Taken(granted=0)


async def test_an_allowance_that_cannot_be_counted_refuses_for_a_minute(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(allowances, "counter", UnreadCounter())
    assert await lookup_attempt(SOURCE_SEARCHES, "a", 30, now=QUARTER_PAST) == Taken(
        granted=0, wait_seconds=60.0, unread=True
    )
    assert await slide(at(12)) == Taken(granted=0, wait_seconds=60.0, unread=True)
    with pytest.raises(InvalidInput, match="could not count this call") as refused:
        await spend(SOURCE_SEARCHES, LookupCaller(holder="a", tier="NEW"), now=QUARTER_PAST)
    assert str(refused.value) == ALLOWANCE_UNREAD


async def test_a_refund_that_cannot_be_counted_leaves_the_count_as_it_was(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(allowances, "counter", UnreadCounter())
    assert await give_back("a", ASKS, seconds=TEN_MINUTES, now=at(12)) is None


async def test_signed_out_callers_count_against_one_holder(allowance_counter: MemoryCounter) -> None:
    for _ in range(3):
        await spend(SOURCE_SEARCHES, LookupCaller(holder=ANONYMOUS_HOLDER), now=QUARTER_PAST)
    assert allowance_counter.used == {bucket_of(ANONYMOUS_HOLDER, SOURCE_SEARCHES, QUARTER_PAST): 3}


def test_the_app_counts_in_postgres(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.undo()
    assert isinstance(allowances.counter, SharedCounter)
