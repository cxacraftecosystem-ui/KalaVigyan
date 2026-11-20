import asyncio
import json
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api import mcp_stream
from app.api.mcp_stream import (
    HEARTBEAT_FRAME,
    OPENING_FRAME,
    STREAM_HEARTBEAT_SECONDS,
    accepts_event_stream,
    progress_token,
    reply_stream,
    streams,
)
from app.api.routes import mcp as mcp_route
from app.core.db import get_session
from app.main import create_app

REPO = Path(__file__).resolve().parents[3]
EDGE_SECONDS = 20
CALL = {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "get_page", "arguments": {}}}
BOTH = "application/json, text/event-stream"


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1


async def frames(work: Any, token: str | int | None, seconds: float = 0.01) -> list[str]:
    return [frame async for frame in reply_stream(work, token, heartbeat_seconds=seconds)]


async def slow(reply: dict[str, Any] | None, seconds: float = 0.05) -> dict[str, Any] | None:
    await asyncio.sleep(seconds)
    return reply


def data_of(frame: str) -> dict[str, Any]:
    assert frame.startswith("event: message\ndata: ") and frame.endswith("\n\n"), frame
    return json.loads(frame.removeprefix("event: message\ndata: "))


@pytest.mark.parametrize(
    ("accept", "taken"),
    [
        (BOTH, True),
        ("text/event-stream", True),
        ("TEXT/Event-Stream; charset=utf-8", True),
        ("application/json, text/event-stream;q=0", False),
        ("application/json", False),
        ("*/*", False),
        (None, False),
    ],
)
def test_only_a_client_that_names_the_event_stream_gets_one(accept: str | None, taken: bool) -> None:
    assert accepts_event_stream(accept) is taken


def test_only_a_tool_call_request_streams() -> None:
    assert streams(BOTH, CALL) is True
    assert streams("application/json", CALL) is False
    assert streams(BOTH, {"jsonrpc": "2.0", "id": 1, "method": "initialize"}) is False
    assert streams(BOTH, {"jsonrpc": "2.0", "method": "tools/call", "params": {}}) is False
    assert streams(BOTH, [CALL]) is False


@pytest.mark.parametrize(
    ("meta", "token"),
    [
        ({"progressToken": "ask-7"}, "ask-7"),
        ({"progressToken": 7}, 7),
        ({"progressToken": True}, None),
        ({}, None),
    ],
)
def test_the_progress_token_is_the_request_s_own(meta: dict[str, Any], token: str | int | None) -> None:
    message = {**CALL, "params": {**CALL["params"], "_meta": meta}}
    assert progress_token(message) == token
    assert progress_token({"jsonrpc": "2.0", "id": 1}) is None


async def test_a_long_call_sends_progress_for_its_token_then_its_result() -> None:
    result = {"jsonrpc": "2.0", "id": 4, "result": {"isError": False}}
    sent = await frames(slow(result), "ask-7")
    assert sent[0] == OPENING_FRAME
    beats = [data_of(frame) for frame in sent[1:-1]]
    assert beats, sent
    assert {beat["method"] for beat in beats} == {"notifications/progress"}
    assert [beat["params"]["progress"] for beat in beats] == list(range(1, len(beats) + 1))
    assert {beat["params"]["progressToken"] for beat in beats} == {"ask-7"}
    assert data_of(sent[-1]) == result


async def test_without_a_token_the_stream_keeps_alive_with_comments() -> None:
    sent = await frames(slow({"jsonrpc": "2.0", "id": 4, "result": {}}), None)
    assert sent[0] == OPENING_FRAME
    assert set(sent[1:-1]) == {HEARTBEAT_FRAME}
    assert data_of(sent[-1])["id"] == 4


async def test_a_quick_call_sends_no_beat() -> None:
    sent = await frames(slow({"jsonrpc": "2.0", "id": 1, "result": {}}, 0), "t", seconds=5)
    assert len(sent) == 2 and data_of(sent[1])["result"] == {}


def test_the_heartbeat_beats_inside_the_edge_s_idle_timeouts_and_nginx_does_not_buffer() -> None:
    cloudfront = (REPO / "infra" / "terraform" / "cloudfront.tf").read_text(encoding="utf-8")
    nginx = (REPO / "infra" / "terraform" / "user_data.sh").read_text(encoding="utf-8")
    origin_read = int(re.search(r"origin_read_timeout\s*=\s*(\d+)", cloudfront).group(1))
    proxy_read = int(re.search(r"proxy_read_timeout\s+(\d+)s", nginx).group(1))
    assert STREAM_HEARTBEAT_SECONDS <= EDGE_SECONDS < min(origin_read, proxy_read)
    serving = re.search(r"location / \{(?P<body>[^}]*)\}", nginx)
    assert serving is not None and "proxy_buffering off;" in serving.group("body")
    assert dict(mcp_stream.STREAM_HEADERS) == {
        "Cache-Control": "no-store, no-transform",
        "X-Accel-Buffering": "no",
    }


def streaming_client(session: FakeSession) -> TestClient:
    app = create_app()
    app.dependency_overrides[mcp_route.mcp_enabled] = lambda: None

    async def opened() -> AsyncIterator[Any]:
        yield session

    @asynccontextmanager
    async def alone() -> AsyncIterator[Any]:
        yield None

    app.dependency_overrides[get_session] = opened
    app.dependency_overrides[mcp_route.stream_sessions] = lambda: alone
    return TestClient(app)


def test_a_tool_call_that_accepts_the_stream_is_answered_in_server_sent_events() -> None:
    session = FakeSession()
    response = streaming_client(session).post("/api/mcp", json=CALL, headers={"accept": BOTH})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["x-accel-buffering"] == "no"
    events = [part for part in response.text.split("\n\n") if part.startswith("event: message")]
    reply = data_of(f"{events[-1]}\n\n")
    assert reply["id"] == 4 and reply["result"]["isError"] is False
    assert len(reply["result"]["structuredContent"]["fields"]) == 16
    assert session.commits == 1


def test_a_client_that_takes_only_json_still_gets_plain_json() -> None:
    response = streaming_client(FakeSession()).post(
        "/api/mcp", json=CALL, headers={"accept": "application/json"}
    )
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["result"]["isError"] is False
