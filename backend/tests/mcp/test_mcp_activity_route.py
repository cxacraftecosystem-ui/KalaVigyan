import uuid
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.routes import mcp_activity as route
from app.core.db import get_session
from app.main import create_app
from app.models import User
from app.research.mcp_activity import (
    ActivityPoint,
    ClientActivity,
    ConnectionActivity,
    FailedCall,
    McpActivity,
    ToolActivity,
    activity_series,
    series_unit,
    tally,
)
from app.services.mcp_activity import ActivityAsk

from ..contracts.golden import golden_json
from ..readers import sign_in_as

PATH = "/api/settings/mcp-activity"
FIRST = uuid.UUID("8f3e2c1a-0000-4000-8000-000000000001")
SECOND = uuid.UUID("8f3e2c1a-0000-4000-8000-000000000002")
THIRD = uuid.UUID("8f3e2c1a-0000-4000-8000-000000000003")


def at(month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, month, day, hour, minute, tzinfo=UTC)


def point(day: int, ok: int, tool_errors: int = 0, protocol_errors: int = 0) -> ActivityPoint:
    return ActivityPoint(
        start=date(2026, 11, day), ok=ok, tool_errors=tool_errors, protocol_errors=protocol_errors
    )


def connection(key: uuid.UUID, client: str, account: tuple[str, str], **rest: Any) -> ConnectionActivity:
    return ConnectionActivity(
        id=key, client_name=client, account_name=account[0], account_email=account[1], **rest
    )


RAVI = ("Ravi Shah", "ravi@example.org")
MEERA = ("Meera Iyer", "meera@example.org")
WEEK = McpActivity(
    days=7,
    first_day=date(2026, 11, 16),
    last_day=date(2026, 11, 22),
    unit="day",
    client=None,
    connection=None,
    series=[
        point(16, 4),
        point(17, 0),
        point(18, 12, 1),
        point(19, 0),
        point(20, 7, 0, 1),
        point(21, 0),
        point(22, 9, 2),
    ],
    tools=[
        ToolActivity(tool="propose_facts", ok=18, tool_errors=2, protocol_errors=0),
        ToolActivity(tool="get_facts", ok=14, tool_errors=1, protocol_errors=0),
        ToolActivity(tool="(unknown)", ok=0, tool_errors=0, protocol_errors=1),
    ],
    clients=[
        ClientActivity(
            client_name="Claude",
            connections=2,
            last_used_at=at(11, 22, 9, 15),
            ok=28,
            tool_errors=3,
            protocol_errors=0,
        ),
        ClientActivity(
            client_name="ChatGPT",
            connections=1,
            last_used_at=at(11, 20, 14, 2),
            ok=4,
            tool_errors=0,
            protocol_errors=1,
        ),
    ],
    connections=[
        connection(
            FIRST,
            "Claude",
            RAVI,
            scopes=["read", "contribute"],
            connected_at=at(11, 10, 6, 30),
            last_used_at=at(11, 22, 9, 15),
            ended=False,
            ok=28,
            tool_errors=3,
            protocol_errors=0,
        ),
        connection(
            SECOND,
            "ChatGPT",
            MEERA,
            scopes=["read"],
            connected_at=at(11, 19, 11),
            last_used_at=at(11, 20, 14, 2),
            ended=False,
            ok=4,
            tool_errors=0,
            protocol_errors=1,
        ),
        connection(
            THIRD,
            "Claude",
            RAVI,
            scopes=["read"],
            connected_at=at(10, 2, 8),
            last_used_at=None,
            ended=False,
            ok=0,
            tool_errors=0,
            protocol_errors=0,
        ),
    ],
    failures=[
        FailedCall(
            called_at=at(11, 22, 9, 10),
            client_name="Claude",
            connection_id=FIRST,
            tool="propose_facts",
            outcome="TOOL_ERROR",
            reason="The quote is not in the source's text; read_source shows the text the gates read.",
        ),
        FailedCall(
            called_at=at(11, 20, 14, 2),
            client_name="ChatGPT",
            connection_id=SECOND,
            tool="(unknown)",
            outcome="PROTOCOL_ERROR",
            reason="no tool is named …; tools/list gives them",
        ),
    ],
)


class QuietSession:
    pass


def master_client(monkeypatch: pytest.MonkeyPatch, asked: list[ActivityAsk]) -> TestClient:
    async def answered(session: Any, ask: ActivityAsk, *, now: datetime) -> McpActivity:
        asked.append(ask)
        return WEEK

    async def quiet() -> AsyncIterator[Any]:
        yield QuietSession()

    monkeypatch.setattr(route, "read_activity", answered)
    app = create_app()
    app.dependency_overrides[get_session] = quiet
    sign_in_as(
        app, lambda: User(id=uuid.uuid4(), name="Master", email="master@example.org", role="MASTER_ADMIN")
    )
    return TestClient(app)


def test_the_activity_a_master_admin_reads_matches_the_shared_golden(monkeypatch: pytest.MonkeyPatch) -> None:
    asked: list[ActivityAsk] = []
    answer = master_client(monkeypatch, asked).get(PATH, params={"days": 7})
    assert answer.status_code == 200
    assert answer.json() == golden_json("mcp.activity.golden.json")
    assert asked == [ActivityAsk(days=7)]


def test_one_client_or_one_connection_narrows_the_screen(monkeypatch: pytest.MonkeyPatch) -> None:
    asked: list[ActivityAsk] = []
    http = master_client(monkeypatch, asked)
    assert http.get(PATH, params={"client": "Claude"}).status_code == 200
    assert http.get(PATH, params={"days": 180, "connection": str(SECOND)}).status_code == 200
    assert asked == [ActivityAsk(days=30, client="Claude"), ActivityAsk(days=180, connection=SECOND)]


@pytest.mark.parametrize(
    ("params", "detail"),
    [
        ({"days": 14}, "Choose a period of 7, 30 or 180 days."),
        ({"client": "Claude", "connection": str(FIRST)}, "Show one client or one connection, not both."),
    ],
)
def test_a_period_off_the_list_or_two_scopes_are_refused(
    monkeypatch: pytest.MonkeyPatch, params: dict[str, Any], detail: str
) -> None:
    asked: list[ActivityAsk] = []
    answer = master_client(monkeypatch, asked).get(PATH, params=params)
    assert (answer.status_code, answer.json()["detail"]) == (422, detail)
    assert asked == []


def test_a_week_is_seven_daily_points_and_half_a_year_is_twenty_six_weekly_ones() -> None:
    assert [series_unit(days) for days in (7, 30, 180)] == ["day", "day", "week"]
    daily = tally(
        [(date(2026, 11, 16), "OK", 2), (date(2026, 11, 22), "TOOL_ERROR", 1), (date(2026, 11, 22), "OK", 3)]
    )
    week = activity_series(daily, first_day=date(2026, 11, 16), last_day=date(2026, 11, 22), unit="day")
    assert [(item.start.day, item.ok, item.tool_errors) for item in week] == [
        (16, 2, 0),
        (17, 0, 0),
        (18, 0, 0),
        (19, 0, 0),
        (20, 0, 0),
        (21, 0, 0),
        (22, 3, 1),
    ]
    weekly = tally(
        [(date(2026, 5, 27), "OK", 1), (date(2026, 6, 3), "OK", 2), (date(2026, 11, 22), "PROTOCOL_ERROR", 1)]
    )
    half = activity_series(weekly, first_day=date(2026, 5, 27), last_day=date(2026, 11, 22), unit="week")
    assert len(half) == 26
    assert (half[0].start, half[0].ok) == (date(2026, 5, 27), 1)
    assert (half[1].start, half[1].ok) == (date(2026, 6, 3), 2)
    assert (half[-1].start, half[-1].protocol_errors) == (date(2026, 11, 18), 1)
