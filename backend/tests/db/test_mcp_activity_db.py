import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import McpToolCall, McpToolCallDay, OAuthClient, OAuthGrant, OAuthToken, User
from app.research.mcp_activity import ActivityPoint, ToolActivity
from app.services import mcp_activity_upkeep
from app.services.mcp_activity import ActivityAsk, read_activity
from app.services.mcp_activity_upkeep import keep_mcp_activity
from app.services.oauth_bearer import McpCaller, record_tool_call

from .testimony_seed import rolled_back_session

pytestmark = pytest.mark.db

NOW = datetime(2026, 11, 22, 23, 45, tzinfo=UTC)
DAY = timedelta(days=1)
REDIRECT = "https://claude.ai/api/mcp/auth_callback"
RESOURCE = "https://api.kalavigyan.example/api/mcp"
QUOTE_MISSING = "The quote is not in the source's text."
A_AT = datetime(2026, 11, 22, 10, 0, tzinfo=UTC)
C_AT = datetime(2026, 11, 22, 18, 20, tzinfo=UTC)
B_AT = datetime(2026, 11, 22, 18, 40, tzinfo=UTC)
D_AT = datetime(2026, 11, 21, 9, 0, tzinfo=UTC)
E_AT = datetime(2026, 5, 1, 6, 0, tzinfo=UTC)


@dataclass(frozen=True)
class Seeded:
    claude: OAuthGrant
    chatgpt: OAuthGrant
    claude_name: str
    chatgpt_name: str


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in rolled_back_session():
        await opened.execute(delete(McpToolCall))
        await opened.execute(delete(McpToolCallDay))
        yield opened


async def connection(session: AsyncSession, client_name: str, last_used: datetime) -> OAuthGrant:
    person = User(
        id=uuid.uuid4(), name="Ravi Shah", email=f"{uuid.uuid4().hex[:10]}@example.org", role="RESEARCHER"
    )
    client = OAuthClient(id=uuid.uuid4(), name=client_name, redirectUris=[REDIRECT], createdAt=NOW - 30 * DAY)
    session.add_all([person, client])
    await session.flush()
    grant = OAuthGrant(
        id=uuid.uuid4(),
        clientId=client.id,
        userId=person.id,
        scopes=["read", "contribute"],
        resource=RESOURCE,
        userTokenVersion=0,
        lastUsedAt=last_used,
        expiresAt=NOW + 30 * DAY,
    )
    session.add(grant)
    await session.flush()
    return grant


def made(
    grant: OAuthGrant, client_name: str, tool: str, at: datetime, reason: str | None = None
) -> McpToolCall:
    outcome = "OK" if reason is None else "TOOL_ERROR"
    return McpToolCall(
        grantId=grant.id, clientName=client_name, tool=tool, outcome=outcome, reason=reason, calledAt=at
    )


async def seeded(session: AsyncSession) -> Seeded:
    tag = uuid.uuid4().hex[:8]
    claude_name, chatgpt_name = f"Claude {tag}", f"ChatGPT {tag}"
    claude = await connection(session, claude_name, B_AT)
    chatgpt = await connection(session, chatgpt_name, D_AT)
    session.add_all(
        [
            made(claude, claude_name, "find_crafts", A_AT),
            made(claude, claude_name, "find_crafts", C_AT),
            made(claude, claude_name, "find_crafts", B_AT),
            made(chatgpt, chatgpt_name, "propose_facts", D_AT, QUOTE_MISSING),
            made(claude, claude_name, "get_facts", E_AT),
        ]
    )
    await session.flush()
    return Seeded(claude, chatgpt, claude_name, chatgpt_name)


async def counted_rows(session: AsyncSession) -> set[tuple[date, str, str, str, int]]:
    found = await session.scalars(select(McpToolCallDay))
    return {(row.day, row.clientName, row.tool, row.outcome, row.calls) for row in found}


async def test_a_failed_call_keeps_its_reason_and_an_ok_call_keeps_none(session: AsyncSession) -> None:
    grant = await connection(session, "Claude", D_AT)
    token = OAuthToken(
        id=uuid.uuid4(),
        grantId=grant.id,
        kind="ACCESS",
        tokenHash=uuid.uuid4().hex * 2,
        scopes=["read"],
        expiresAt=NOW + DAY,
    )
    session.add(token)
    await session.flush()
    caller = McpCaller(
        user=User(id=uuid.uuid4(), name="Ravi Shah", email="ravi@example.org", role="RESEARCHER"),
        scopes=frozenset({"read"}),
        grant_id=grant.id,
        token_id=token.id,
        client_name="Claude",
    )
    await record_tool_call(
        session, caller, tool="propose_facts", outcome="TOOL_ERROR", reason=QUOTE_MISSING, now=D_AT
    )
    await session.flush()
    stored = await session.scalar(select(McpToolCall).where(McpToolCall.grantId == grant.id))
    assert stored is not None
    assert (stored.clientName, stored.outcome, stored.reason) == ("Claude", "TOOL_ERROR", QUOTE_MISSING)
    with pytest.raises(ValueError, match="keeps a reason exactly when it failed"):
        await record_tool_call(session, caller, tool="find_crafts", outcome="OK", reason="fine", now=D_AT)
    with pytest.raises(ValueError, match="keeps a reason exactly when it failed"):
        await record_tool_call(
            session, caller, tool="find_crafts", outcome="PROTOCOL_ERROR", reason=None, now=D_AT
        )
    with pytest.raises(ValueError, match="1 to 300 characters"):
        await record_tool_call(
            session, caller, tool="find_crafts", outcome="TOOL_ERROR", reason="a" * 301, now=D_AT
        )


async def test_the_database_refuses_a_reason_on_a_call_that_succeeded(session: AsyncSession) -> None:
    grant = await connection(session, "Claude", D_AT)
    session.add(
        McpToolCall(
            grantId=grant.id, clientName="Claude", tool="find_crafts", outcome="OK", reason="x", calledAt=D_AT
        )
    )
    with pytest.raises(IntegrityError, match="McpToolCall_reason_check"):
        await session.flush()


async def test_the_night_counts_each_finished_india_day_once_and_prunes_counted_calls_past_180_days(
    session: AsyncSession,
) -> None:
    mine = await seeded(session)
    report = await keep_mcp_activity(session, now=NOW)
    assert report.as_dict() == {"daysCounted": 3, "callsCounted": 4, "callsPruned": 1}
    assert await counted_rows(session) == {
        (date(2026, 5, 1), mine.claude_name, "get_facts", "OK", 1),
        (date(2026, 11, 21), mine.chatgpt_name, "propose_facts", "TOOL_ERROR", 1),
        (date(2026, 11, 22), mine.claude_name, "find_crafts", "OK", 2),
    }
    kept = set(await session.scalars(select(McpToolCall.calledAt)))
    assert kept == {A_AT, B_AT, C_AT, D_AT}
    again = await keep_mcp_activity(session, now=NOW)
    assert again.as_dict() == {"daysCounted": 0, "callsCounted": 0, "callsPruned": 0}


async def test_each_night_is_bounded_and_the_next_night_carries_on(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    mine = await seeded(session)
    session.add(made(mine.claude, mine.claude_name, "get_facts", E_AT + timedelta(hours=1)))
    await session.flush()
    monkeypatch.setattr(mcp_activity_upkeep, "DAYS_COUNTED_PER_NIGHT", 2)
    monkeypatch.setattr(mcp_activity_upkeep, "CALLS_PRUNED_PER_NIGHT", 1)
    first = await keep_mcp_activity(session, now=NOW)
    assert first.as_dict() == {"daysCounted": 2, "callsCounted": 3, "callsPruned": 1}
    second = await keep_mcp_activity(session, now=NOW)
    assert second.as_dict() == {"daysCounted": 1, "callsCounted": 2, "callsPruned": 1}
    assert (date(2026, 5, 1), mine.claude_name, "get_facts", "OK", 2) in await counted_rows(session)


async def test_the_screen_reads_counted_days_and_today_s_calls_by_client_and_connection(
    session: AsyncSession,
) -> None:
    mine = await seeded(session)
    await keep_mcp_activity(session, now=NOW)
    week = await read_activity(session, ActivityAsk(days=7), now=NOW)
    assert (week.first_day, week.last_day, week.unit) == (date(2026, 11, 17), date(2026, 11, 23), "day")
    assert [(point.start.day, point.ok, point.tool_errors) for point in week.series] == [
        (17, 0, 0),
        (18, 0, 0),
        (19, 0, 0),
        (20, 0, 0),
        (21, 0, 1),
        (22, 2, 0),
        (23, 1, 0),
    ]
    assert week.tools == [
        ToolActivity(tool="find_crafts", ok=3, tool_errors=0, protocol_errors=0),
        ToolActivity(tool="propose_facts", ok=0, tool_errors=1, protocol_errors=0),
    ]
    clients = {client.client_name: client for client in week.clients}
    assert (clients[mine.claude_name].ok, clients[mine.claude_name].connections) == (3, 1)
    assert (clients[mine.chatgpt_name].tool_errors, clients[mine.chatgpt_name].last_used_at) == (1, D_AT)
    connections = {item.id: item for item in week.connections}
    assert (connections[mine.claude.id].ok, connections[mine.claude.id].ended) == (3, False)
    assert connections[mine.chatgpt.id].tool_errors == 1
    assert [(failed.connection_id, failed.reason) for failed in week.failures] == [
        (mine.chatgpt.id, QUOTE_MISSING)
    ]


async def test_a_client_or_a_connection_narrows_the_series_the_tools_and_the_failures(
    session: AsyncSession,
) -> None:
    mine = await seeded(session)
    await keep_mcp_activity(session, now=NOW)
    chatgpt = await read_activity(session, ActivityAsk(days=7, client=mine.chatgpt_name), now=NOW)
    assert [tool.tool for tool in chatgpt.tools] == ["propose_facts"]
    assert sum(point.tool_errors for point in chatgpt.series) == 1
    claude = await read_activity(session, ActivityAsk(days=7, connection=mine.claude.id), now=NOW)
    assert claude.tools == [ToolActivity(tool="find_crafts", ok=3, tool_errors=0, protocol_errors=0)]
    assert claude.failures == []
    half_year = await read_activity(session, ActivityAsk(days=180), now=NOW)
    assert (half_year.first_day, half_year.unit, len(half_year.series)) == (date(2026, 5, 28), "week", 26)
    assert half_year.series[-1] == ActivityPoint(
        start=date(2026, 11, 19), ok=3, tool_errors=1, protocol_errors=0
    )
