from collections.abc import AsyncIterator

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import redact_secrets

from .testimony_seed import rolled_back_session

pytestmark = pytest.mark.db

HOLDER = "ravi@example.org kvmcp_at_A1b2C3d4E5f6G7h8I9j0"
FAILING = "SELECT 1 / 0 WHERE CAST(:holder AS text) IS NOT NULL"
REFUSED_ROW = (
    'INSERT INTO "AllowanceBucket" ("holder", "kind", "hourStart", "used", "lastTaken") '
    "VALUES (:holder, :kind, now(), -1, 0)"
)


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in rolled_back_session():
        yield opened


async def test_a_failed_statement_never_carries_the_values_it_was_given(session: AsyncSession) -> None:
    with pytest.raises(DBAPIError) as failed:
        await session.execute(text(FAILING), {"holder": HOLDER})
    said = str(failed.value)
    assert "division by zero" in said
    assert "[SQL parameters hidden due to hide_parameters=True]" in said
    assert "ravi@example.org" not in said


async def test_a_refused_row_s_values_never_reach_a_log_line(session: AsyncSession) -> None:
    with pytest.raises(IntegrityError) as refused:
        await session.execute(text(REFUSED_ROW), {"holder": HOLDER, "kind": "probe"})
    logged = redact_secrets(str(refused.value))
    assert "violates check constraint" in logged
    assert "ravi@example.org" not in logged
    assert "kvmcp_at_" not in logged
