import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.db import get_engine
from app.models import Answer, UsageEvent
from app.services.upkeep_costs import settle_late_costs

pytestmark = pytest.mark.db

NOW = datetime(2031, 1, 6, 21, 30, tzinfo=UTC)


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async with get_engine().connect() as connection:
        transaction = await connection.begin()
        try:
            factory = async_sessionmaker(
                bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
            )
            async with factory() as opened:
                yield opened
        finally:
            await transaction.rollback()


def answer(request_id: str | None, cost: str, *, age: timedelta) -> Answer:
    return Answer(
        id=uuid.uuid4(),
        question="Why does alum keep Ajrakh red?",
        mode="HYBRID",
        requestId=request_id,
        costUsd=Decimal(cost),
        createdAt=NOW - age,
    )


def spent(request_id: str, cost: str, *, age: timedelta) -> UsageEvent:
    return UsageEvent(
        task="COMPOSE", requestId=request_id, costUsd=Decimal(cost), outcome="OK", createdAt=NOW - age
    )


async def test_the_nightly_upkeep_adds_what_settled_after_an_answer_finished(session: AsyncSession) -> None:
    fresh = answer("late-cost-fresh-0001", "0.012500", age=timedelta(hours=5))
    old = answer("late-cost-old-00001", "0.010000", age=timedelta(days=8))
    loose = answer(None, "0.000000", age=timedelta(hours=5))
    session.add_all([fresh, old, loose])
    session.add_all(
        [
            spent("late-cost-fresh-0001", "0.012500", age=timedelta(hours=5)),
            spent("late-cost-fresh-0001", "0.031000", age=timedelta(hours=4)),
            spent("late-cost-old-00001", "0.010000", age=timedelta(days=8)),
            spent("late-cost-old-00001", "0.500000", age=timedelta(days=7, hours=23)),
        ]
    )
    await session.commit()
    report = await settle_late_costs(session, now=NOW)
    for row in (fresh, old, loose):
        await session.refresh(row)
    assert report.updated == 1
    assert (fresh.costUsd, old.costUsd, loose.costUsd) == (
        Decimal("0.043500"),
        Decimal("0.010000"),
        Decimal(0),
    )
    again = await settle_late_costs(session, now=NOW)
    assert again.updated == 0
