from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.core import allowances
from app.core.allowances import (
    ALLOWANCE_UNREAD,
    AllowanceUnread,
    Ask,
    Bucket,
    SharedCounter,
    Taken,
    bucket_of,
    take,
    taken_from,
)
from app.core.errors import InvalidInput
from app.core.rate_limit import ANONYMOUS_HOLDER, SOURCE_SEARCHES, lookup_attempt
from app.services.source_lookup_allowance import LookupCaller, spend

from .allowance_counter import MemoryCounter

QUARTER_PAST = datetime(2026, 11, 21, 10, 15, tzinfo=UTC)
TEN = datetime(2026, 11, 21, 10, 0, tzinfo=UTC)


class UnreadCounter:
    async def take(self, bucket: Bucket, ask: Ask) -> int:
        raise AllowanceUnread("not counted")


class NeverCounter:
    async def take(self, bucket: Bucket, ask: Ask) -> int:
        raise AssertionError("nothing should be counted")


def test_a_bucket_is_the_utc_hour_of_the_moment() -> None:
    india = timezone(timedelta(hours=5, minutes=30))
    moment = datetime(2026, 11, 21, 16, 10, 42, tzinfo=india)
    assert bucket_of("a", SOURCE_SEARCHES, moment) == Bucket("a", SOURCE_SEARCHES, TEN)
    with pytest.raises(ValueError, match="aware"):
        bucket_of("a", SOURCE_SEARCHES, QUARTER_PAST.replace(tzinfo=None))


def test_a_partial_grant_waits_for_the_end_of_its_hour() -> None:
    bucket = bucket_of("a", SOURCE_SEARCHES, QUARTER_PAST)
    assert taken_from(4, 4, bucket=bucket, now=QUARTER_PAST) == Taken(granted=4)
    assert taken_from(2, 4, bucket=bucket, now=QUARTER_PAST) == Taken(granted=2, wait_seconds=2700.0)
    assert taken_from(0, 1, bucket=bucket, now=QUARTER_PAST) == Taken(granted=0, wait_seconds=2700.0)


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
    with pytest.raises(InvalidInput, match="could not count this call") as refused:
        await spend(SOURCE_SEARCHES, LookupCaller(holder="a", tier="NEW"), now=QUARTER_PAST)
    assert str(refused.value) == ALLOWANCE_UNREAD


async def test_signed_out_callers_count_against_one_holder(allowance_counter: MemoryCounter) -> None:
    for _ in range(3):
        await spend(SOURCE_SEARCHES, LookupCaller(holder=ANONYMOUS_HOLDER), now=QUARTER_PAST)
    assert allowance_counter.used == {(ANONYMOUS_HOLDER, SOURCE_SEARCHES): 3}


def test_the_app_counts_in_postgres(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.undo()
    assert isinstance(allowances.counter, SharedCounter)
