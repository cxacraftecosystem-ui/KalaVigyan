import uuid
from collections.abc import AsyncIterator
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.db import get_engine
from app.models import UsageEvent, User
from app.providers.base import Adapter, MediaRequest, MediaResult
from app.providers.catalogue import AiTask
from app.providers.media_router import MediaAsk, MediaRouter
from app.providers.router import Principal

from ..media.fakes import media_result, png_bytes

pytestmark = pytest.mark.db


@pytest.fixture
async def sessions() -> AsyncIterator[tuple[async_sessionmaker[AsyncSession], AsyncSession]]:
    async with get_engine().connect() as connection:
        transaction = await connection.begin()
        try:
            factory = async_sessionmaker(
                bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
            )
            async with factory() as session:
                yield factory, session
        finally:
            await transaction.rollback()


class OneImage(Adapter):
    def __init__(self) -> None:
        super().__init__(api_key="k", base_url=None, preset="gemini", extra={}, learned={})

    async def chat(self, req: Any) -> Any:
        raise AssertionError("media never chats")

    async def list_models(self) -> list[dict]:
        return []

    async def generate_image(self, req: MediaRequest) -> MediaResult:
        return media_result(png_bytes())


async def asker(session: AsyncSession) -> MediaAsk:
    user = User(id=uuid.uuid4(), name="Media Router", email=f"router-{uuid.uuid4().hex[:8]}@example.com")
    session.add(user)
    await session.commit()
    return MediaAsk(AiTask.IMAGE, "Draw one stage.", {"image_size": "1K"}, 1.0, Principal(user.id, "STUDENT"))


async def test_a_hold_is_a_media_reservation_and_release_cancels_it(sessions: Any) -> None:
    factory, session = sessions
    ask = await asker(session)
    media = MediaRouter(session_factory=factory)
    held = await media.hold(ask)
    row = await session.get(UsageEvent, held)
    assert row is not None and (row.outcome, row.isMedia, row.task) == ("RESERVED", True, "IMAGE")
    assert row.estimatedCostUsd == Decimal("0.067000")
    await media.release(held)
    await session.refresh(row)
    assert row.outcome == "CANCELLED"


async def test_a_generated_image_settles_its_call_at_the_billed_cost(sessions: Any) -> None:
    factory, session = sessions
    ask = await asker(session)
    media = MediaRouter(session_factory=factory, adapter_factory=lambda choice, key: OneImage())
    made = await media.generate(ask)
    row = await session.get(UsageEvent, made.usage_event_id)
    assert row is not None and (row.outcome, row.model, row.isMedia) == ("OK", "gemini-3.1-flash-image", True)
    assert row.costUsd == Decimal("0.067350") == made.cost_usd
    assert (row.inputTokens, row.outputTokens) == (300, 1120)
