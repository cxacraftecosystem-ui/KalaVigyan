from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.db import get_engine
from app.media.heartbeat import WORKER_HEARTBEAT_KEY, beat
from app.media.store import SqlMediaStore
from app.models import AppSetting

pytestmark = pytest.mark.db

NOW = datetime(2026, 11, 23, 6, 0, tzinfo=UTC)


@pytest.fixture
async def sessions() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    async with get_engine().connect() as connection:
        transaction = await connection.begin()
        try:
            factory = async_sessionmaker(
                bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
            )
            async with factory() as session:
                await session.execute(delete(AppSetting).where(AppSetting.key == WORKER_HEARTBEAT_KEY))
                await session.commit()
            yield factory
        finally:
            await transaction.rollback()


async def test_the_options_hear_the_worker_for_five_minutes_after_its_last_beat(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    store = SqlMediaStore(sessions)
    assert not await store.worker_listening(NOW)
    await beat(sessions, worker_id="box:41", now=NOW)
    await beat(sessions, worker_id="box:41", now=NOW + timedelta(minutes=1))
    assert await store.worker_listening(NOW + timedelta(minutes=6))
    assert not await store.worker_listening(NOW + timedelta(minutes=6, seconds=1))
