from datetime import UTC, datetime

import pytest
from sqlalchemy import text

from .test_mcp_activity_db import connection
from .testimony_seed import rolled_back_session

pytestmark = pytest.mark.db

LAST_USED = datetime(2026, 11, 22, 18, 0, tzinfo=UTC)
AS_THE_RELEASE_BEFORE = text(
    'INSERT INTO "McpToolCall" ("grantId", "tool", "outcome", "calledAt") '
    "VALUES (:grant, :tool, 'OK', now()) RETURNING \"clientName\""
)
AS_THIS_RELEASE = text(
    'INSERT INTO "McpToolCall" ("grantId", "clientName", "tool", "outcome", "calledAt") '
    "VALUES (:grant, :name, :tool, 'OK', now()) RETURNING \"clientName\""
)


async def test_a_call_the_release_before_records_without_its_client_takes_the_grant_s_client_name() -> None:
    async for session in rolled_back_session():
        grant = await connection(session, "Claude", LAST_USED)
        named = await session.scalar(AS_THE_RELEASE_BEFORE, {"grant": grant.id, "tool": "search_sources"})
        assert named == "Claude"


async def test_a_call_that_names_its_client_keeps_the_name_it_gives() -> None:
    async for session in rolled_back_session():
        grant = await connection(session, "Claude", LAST_USED)
        params = {"grant": grant.id, "name": "Claude Code", "tool": "lookup"}
        assert await session.scalar(AS_THIS_RELEASE, params) == "Claude Code"
