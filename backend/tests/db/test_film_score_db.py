import uuid
from collections.abc import AsyncIterator
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.db import get_engine
from app.models import UsageEvent, User
from app.providers.budget import MEDIA_CAP
from app.providers.catalogue import AiTask
from app.providers.media_router import MediaAsk, MediaRouter
from app.providers.router import Principal, RouterError, load_routes
from app.services import app_settings

from ..media.audio_routes import SoundStudio

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


async def person(session: AsyncSession, role: str) -> Principal:
    user = User(
        id=uuid.uuid4(), name="Film Score", email=f"score-{uuid.uuid4().hex[:8]}@example.com", role=role
    )
    session.add(user)
    await session.commit()
    return Principal(user_id=user.id, role=role)


def music(principal: Principal) -> MediaAsk:
    return MediaAsk(AiTask.MUSIC, "A calm underscore.", {"seconds": "30"}, 30.0, principal)


async def test_the_migration_seeds_elevenlabs_as_the_one_score_route(sessions: Any) -> None:
    _, session = sessions
    music_routes = await load_routes(session, AiTask.MUSIC)
    cue_routes = await load_routes(session, AiTask.SOUND_EFFECT)
    assert [(r.provider, r.model, r.preset, r.kind, r.key_name) for r in music_routes] == [
        ("ELEVENLABS", "music_v2_5", "elevenlabs", "elevenlabs", "ELEVENLABS_API_KEY")
    ]
    assert [(r.provider, r.model) for r in cue_routes] == [("ELEVENLABS", "eleven_text_to_sound_v3")]
    assert [r.provider for r in await load_routes(session, AiTask.IMAGE)] == ["GEMINI", "GEMINI"]


async def test_music_spends_from_the_media_cap_and_a_master_admin_is_not_refused(sessions: Any) -> None:
    factory, session = sessions
    await app_settings.set_value(session, app_settings.MEDIA_CAP_USD, 0.01)
    await session.commit()
    calls: list[Any] = []
    media = MediaRouter(session_factory=factory, adapter_factory=lambda choice, key: SoundStudio(calls))
    student = await person(session, "STUDENT")
    with pytest.raises(RouterError) as refused:
        await media.generate(music(student))
    assert (refused.value.reason, calls) == (MEDIA_CAP, [])
    master = await person(session, "MASTER_ADMIN")
    made = await media.generate(music(master))
    row = await session.get(UsageEvent, made.usage_event_id)
    assert row is not None
    assert (row.task, row.provider, row.isMedia, row.outcome, row.units) == (
        "MUSIC",
        "ELEVENLABS",
        True,
        "OK",
        30.0,
    )
    assert row.costUsd == Decimal("0.137500") == made.cost_usd
