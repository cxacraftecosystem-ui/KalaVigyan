from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast

import pytest
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core import allowances
from app.core.allowances import Ask, SharedCounter, Taken, bucket_of
from app.core.pooler import connected_session, pooler_full

POOLER_FULL = (
    "(EMAXCONNSESSION) max clients reached in session mode - max clients are limited to pool_size: 30"
)
NOW = datetime(2026, 11, 23, 4, 36, tzinfo=UTC)


def refused(message: str) -> OperationalError:
    return OperationalError("SELECT 1", {}, Exception(message))


class Pooler:
    def __init__(self, refusals: list[str]) -> None:
        self.refusals = refusals
        self.opened = 0
        self.closed = 0
        self.waited: list[float] = []

    def session(self) -> AsyncSession:
        return cast(AsyncSession, FakeSession(self))

    async def sleep(self, seconds: float) -> None:
        self.waited.append(seconds)


class FakeSession:
    def __init__(self, pooler: Pooler) -> None:
        self.pooler = pooler

    async def connection(self) -> None:
        self.pooler.opened += 1
        if self.pooler.refusals:
            raise refused(self.pooler.refusals.pop(0))

    async def close(self) -> None:
        self.pooler.closed += 1

    async def __aenter__(self) -> FakeSession:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    async def execute(self, _statement: Any) -> Any:
        return SimpleNamespace(one=lambda: SimpleNamespace(lastTaken=1, used=1, earlier=0))

    async def commit(self) -> None:
        return None


def test_the_pooler_s_own_refusal_is_recognised_through_the_driver_s_error() -> None:
    assert pooler_full(refused(POOLER_FULL))
    assert not pooler_full(refused("connection to server at 127.0.0.1 port 1 failed: Connection refused"))


async def test_a_refused_connect_is_tried_again_after_each_wait_until_one_opens() -> None:
    pooler = Pooler([POOLER_FULL, POOLER_FULL])
    session = await connected_session(pooler.session, waits=(0.2, 0.5, 1.0), sleep=pooler.sleep)
    assert isinstance(session, FakeSession)
    assert (pooler.opened, pooler.closed, pooler.waited) == (3, 2, [0.2, 0.5])


async def test_a_pooler_that_stays_full_fails_after_the_last_wait() -> None:
    pooler = Pooler([POOLER_FULL] * 4)
    with pytest.raises(OperationalError, match="EMAXCONNSESSION"):
        await connected_session(pooler.session, waits=(0.2, 0.5, 1.0), sleep=pooler.sleep)
    assert (pooler.opened, pooler.closed, pooler.waited) == (4, 4, [0.2, 0.5, 1.0])


async def test_any_other_failure_is_not_tried_again() -> None:
    pooler = Pooler(["password authentication failed for user"])
    with pytest.raises(OperationalError, match="password"):
        await connected_session(pooler.session, waits=(0.2, 0.5, 1.0), sleep=pooler.sleep)
    assert (pooler.opened, pooler.waited) == (1, [])


def counter_over(pooler: Pooler) -> SharedCounter:
    return SharedCounter(cast(async_sessionmaker[AsyncSession], pooler.session), waits=(0.0, 0.0))


async def test_the_allowance_counts_once_the_pooler_frees_a_session(monkeypatch: pytest.MonkeyPatch) -> None:
    pooler = Pooler([POOLER_FULL, POOLER_FULL])
    monkeypatch.setattr(allowances, "counter", counter_over(pooler))
    assert await allowances.take("reader", "PUBLIC_ASSET", 1, 120, now=NOW) == Taken(granted=1)
    assert pooler.opened == 3


async def test_the_allowance_still_refuses_when_the_pooler_stays_full(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pooler = Pooler([POOLER_FULL] * 3)
    monkeypatch.setattr(allowances, "counter", counter_over(pooler))
    assert await allowances.take("reader", "PUBLIC_ASSET", 1, 120, now=NOW) == Taken(
        granted=0, wait_seconds=60.0, unread=True
    )
    assert pooler.opened == 3


async def test_a_direct_count_through_a_full_pooler_is_unread() -> None:
    counter = counter_over(Pooler([POOLER_FULL] * 3))
    with pytest.raises(allowances.AllowanceUnread):
        await counter.take(bucket_of("reader", "PUBLIC_ASSET", NOW), Ask(wanted=1, limit=120))
