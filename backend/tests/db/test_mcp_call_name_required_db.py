from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from .test_mcp_activity_db import connection
from .testimony_seed import rolled_back_session

pytestmark = pytest.mark.db

LAST_USED = datetime(2026, 11, 22, 18, 0, tzinfo=UTC)
WITHOUT_ITS_CLIENT = text(
    'INSERT INTO "McpToolCall" ("grantId", "tool", "outcome", "calledAt") '
    "VALUES (:grant, :tool, 'OK', now()) RETURNING \"clientName\""
)
WITH_ITS_CLIENT = text(
    'INSERT INTO "McpToolCall" ("grantId", "clientName", "tool", "outcome", "calledAt") '
    "VALUES (:grant, :name, :tool, 'OK', now()) RETURNING \"clientName\""
)
FILL_TRIGGERS = text("SELECT count(*) FROM pg_trigger WHERE tgname = 'McpToolCall_clientName_fill'")
FILL_FUNCTIONS = text("SELECT count(*) FROM pg_proc WHERE proname = 'kv_fill_mcp_client_name'")


async def test_a_call_recorded_without_its_client_name_is_refused() -> None:
    async for session in rolled_back_session():
        grant = await connection(session, "Claude", LAST_USED)
        with pytest.raises(IntegrityError, match="clientName"):
            await session.scalar(WITHOUT_ITS_CLIENT, {"grant": grant.id, "tool": "search_sources"})


async def test_a_call_that_names_its_client_keeps_the_name_it_gives() -> None:
    async for session in rolled_back_session():
        grant = await connection(session, "Claude", LAST_USED)
        params = {"grant": grant.id, "name": "Claude Code", "tool": "lookup"}
        assert await session.scalar(WITH_ITS_CLIENT, params) == "Claude Code"


async def test_the_fill_trigger_and_its_function_are_gone() -> None:
    async for session in rolled_back_session():
        assert await session.scalar(FILL_TRIGGERS) == 0
        assert await session.scalar(FILL_FUNCTIONS) == 0
