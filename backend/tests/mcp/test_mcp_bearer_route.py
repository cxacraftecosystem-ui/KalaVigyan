import uuid
from datetime import datetime
from types import MappingProxyType
from typing import Any

import pytest
from pydantic import BaseModel

from app.api import mcp_auth
from app.api.mcp_tool_base import WRITES, NoArguments, Tool, ToolContext
from app.api.routes import mcp
from app.core import rate_limit
from app.services import oauth_bearer
from app.services.oauth_bearer import BearerRefused, McpCaller

from .oauth_fakes import RESOURCE, RESOURCE_METADATA, FakeSession, client, person, with_hosts

GRANT = uuid.UUID("5b1f7a9e-0000-4000-8000-0000000000aa")
TOKEN = uuid.UUID("5b1f7a9e-0000-4000-8000-0000000000bb")
PRIVATE_WORDS = "Ravi Shah's village near Ajrakhpur"
FIND = {
    "jsonrpc": "2.0",
    "id": 7,
    "method": "tools/call",
    "params": {"name": "find_crafts", "arguments": {"query": PRIVATE_WORDS}},
}
BEARER = {"authorization": "Bearer kvmcp_at_live"}


class Proposed(BaseModel):
    ok: bool


async def _propose(context: ToolContext, arguments: NoArguments) -> Proposed:
    return Proposed(ok=True)


PROPOSE = Tool(
    "propose_fact", "Propose a fact", "Test tool.", NoArguments, Proposed, _propose, "contribute", WRITES
)


def signed_in(monkeypatch: pytest.MonkeyPatch, scopes: frozenset[str]) -> dict[str, Any]:
    seen: dict[str, Any] = {"calls": []}
    reader = person("RESEARCHER")

    async def fake_caller(session: Any, raw: str, *, resource: str, now: datetime) -> McpCaller:
        seen.update(raw=raw, resource=resource)
        return McpCaller(user=reader, scopes=scopes, grant_id=GRANT, token_id=TOKEN, client_name="Claude")

    async def fake_record(
        session: Any, caller: McpCaller, *, tool: str, outcome: str, reason: str | None, now: datetime
    ) -> None:
        seen["calls"].append({"grant": caller.grant_id, "tool": tool, "outcome": outcome, "reason": reason})

    async def fake_touch(session: Any, caller: McpCaller, *, now: datetime) -> None:
        seen["touched"] = caller.grant_id

    monkeypatch.setattr(oauth_bearer, "caller_for", fake_caller)
    monkeypatch.setattr(oauth_bearer, "record_tool_call", fake_record)
    monkeypatch.setattr(oauth_bearer, "touch", fake_touch)
    seen["reader"] = reader
    return seen


def test_an_unknown_token_is_401_naming_the_resource_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    with_hosts(monkeypatch)

    async def refuse(*_: Any, **__: Any) -> McpCaller:
        raise BearerRefused("The access token has expired; refresh it.")

    monkeypatch.setattr(oauth_bearer, "caller_for", refuse)
    reply = client().post("/api/mcp", json=FIND, headers=BEARER)
    assert reply.status_code == 401
    assert reply.headers["www-authenticate"] == (
        'Bearer error="invalid_token", error_description="The access token has expired; refresh it.", '
        f'resource_metadata="{RESOURCE_METADATA}"'
    )


def test_a_header_that_is_not_bearer_is_refused_without_a_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    with_hosts(monkeypatch)

    async def never(*_: Any, **__: Any) -> McpCaller:
        raise AssertionError("no lookup for a Basic header")

    monkeypatch.setattr(oauth_bearer, "caller_for", never)
    reply = client().post("/api/mcp", json=FIND, headers={"authorization": "Basic a2F2aTpzZWNyZXQ="})
    assert reply.status_code == 401
    assert 'error="invalid_token"' in reply.headers["www-authenticate"]


def test_a_valid_token_puts_the_account_and_scopes_on_the_tool_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with_hosts(monkeypatch)
    seen = signed_in(monkeypatch, frozenset({"read", "ask"}))
    contexts: list[ToolContext] = []

    async def fake_answer(message: Any, context: ToolContext) -> dict[str, Any]:
        contexts.append(context)
        return {"jsonrpc": "2.0", "id": 7, "result": {"content": [], "isError": False}}

    monkeypatch.setattr(mcp, "answer", fake_answer)
    session = FakeSession()
    reply = client(session).post("/api/mcp", json=FIND, headers=BEARER)
    assert reply.status_code == 200
    assert (seen["raw"], seen["resource"]) == ("kvmcp_at_live", RESOURCE)
    assert (contexts[0].user, contexts[0].scopes) == (seen["reader"], frozenset({"read", "ask"}))
    assert seen["calls"] == [{"grant": GRANT, "tool": "find_crafts", "outcome": "OK", "reason": None}]
    assert PRIVATE_WORDS not in repr(seen["calls"])
    assert session.commits == 1


def test_calls_are_limited_per_connection_across_its_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    with_hosts(monkeypatch)
    signed_in(monkeypatch, frozenset({"read"}))
    monkeypatch.setattr(rate_limit, "MCP_CALLS_PER_CONNECTION_WINDOW", 2)
    http = client()
    ping = {"jsonrpc": "2.0", "id": 1, "method": "ping"}
    answered = [http.post("/api/mcp", json=ping, headers=BEARER).status_code for _ in range(3)]
    assert answered == [200, 200, 429]
    assert client().post("/api/mcp", json=ping).status_code == 200


def test_a_tool_beyond_read_challenges_for_sign_in_or_for_its_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    with_hosts(monkeypatch)
    monkeypatch.setattr(mcp_auth, "TOOLS", MappingProxyType({PROPOSE.name: PROPOSE}))
    call = {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "propose_fact"}}
    anonymous = client().post("/api/mcp", json=call)
    assert anonymous.status_code == 401
    assert anonymous.headers["www-authenticate"] == (
        f'Bearer scope="read contribute", resource_metadata="{RESOURCE_METADATA}"'
    )
    signed_in(monkeypatch, frozenset({"read"}))
    narrow = client().post("/api/mcp", json=call, headers=BEARER)
    assert narrow.status_code == 403
    assert narrow.headers["www-authenticate"].startswith('Bearer error="insufficient_scope"')
    assert 'scope="read contribute"' in narrow.headers["www-authenticate"]


@pytest.mark.parametrize(
    ("reply", "outcome"),
    [
        ({"jsonrpc": "2.0", "id": 1, "error": {"code": -32602, "message": "no tool"}}, "PROTOCOL_ERROR"),
        ({"jsonrpc": "2.0", "id": 1, "result": {"isError": True}}, "TOOL_ERROR"),
        ({"jsonrpc": "2.0", "id": 1, "result": {"isError": False}}, "OK"),
    ],
)
def test_the_audit_outcome_reads_only_the_reply_s_shape(reply: dict[str, Any], outcome: str) -> None:
    assert mcp_auth.call_outcome(reply) == outcome


def test_an_unknown_tool_name_is_audited_as_unknown_never_as_the_sent_text() -> None:
    sent = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": PRIVATE_WORDS}}
    assert mcp_auth.called_tool_name(sent) == "(unknown)"
    assert mcp_auth.called_tool_name({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}) is None
