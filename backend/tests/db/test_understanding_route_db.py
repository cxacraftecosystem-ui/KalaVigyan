import pytest
from sqlalchemy import inspect, select

from app.core.db import get_engine, session_scope
from app.models import Provider, RoutePolicy

pytestmark = pytest.mark.db


async def routes(task: str) -> list[tuple[int, str, str, bool]]:
    async with session_scope() as session:
        rows = await session.execute(
            select(RoutePolicy.ordinal, Provider.name, RoutePolicy.model, RoutePolicy.enabled)
            .join(Provider, Provider.id == RoutePolicy.providerId)
            .where(RoutePolicy.task == task)
            .order_by(RoutePolicy.ordinal)
        )
        return [(row.ordinal, str(row.name), row.model, row.enabled) for row in rows]


async def test_the_understanding_starts_on_the_planning_routes() -> None:
    planned = await routes("PLAN")
    assert planned
    assert await routes("UNDERSTAND") == planned


async def test_an_answer_keeps_its_request_id_and_live_candidates_are_gone() -> None:
    async with get_engine().connect() as connection:
        tables, answer_columns, citation_columns = await connection.run_sync(
            lambda sync: (
                inspect(sync).get_table_names(),
                {column["name"] for column in inspect(sync).get_columns("Answer")},
                {column["name"] for column in inspect(sync).get_columns("AnswerCitation")},
            )
        )
    assert "LiveCandidate" not in tables
    assert "requestId" in answer_columns and "liveCandidateIds" not in answer_columns
    assert "liveCandidateId" not in citation_columns
