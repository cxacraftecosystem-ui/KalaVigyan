import uuid
from datetime import datetime
from typing import Any

import pytest

from app.api import mcp_auth
from app.api.mcp_tools import ToolContext
from app.api.routes import mcp
from app.research.mcp_activity import failure_reason, sent_texts
from app.services import oauth_bearer
from app.services.oauth_bearer import McpCaller

from .oauth_fakes import FakeSession, client, person, with_hosts

GRANT = uuid.UUID("5b1f7a9e-0000-4000-8000-0000000000cc")
TOKEN = uuid.UUID("5b1f7a9e-0000-4000-8000-0000000000dd")
PRIVATE_WORDS = "Ravi Shah's village near Ajrakhpur"
BEARER = {"authorization": "Bearer kvmcp_at_live"}
FIND = {
    "jsonrpc": "2.0",
    "id": 9,
    "method": "tools/call",
    "params": {"name": "find_crafts", "arguments": {"query": PRIVATE_WORDS}},
}


def tool_error(text: str) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": 9,
        "result": {"content": [{"type": "text", "text": text}], "isError": True},
    }


def recorded_calls(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    reader = person("RESEARCHER")

    async def fake_caller(session: Any, raw: str, *, resource: str, now: datetime) -> McpCaller:
        return McpCaller(
            user=reader, scopes=frozenset({"read"}), grant_id=GRANT, token_id=TOKEN, client_name="Claude"
        )

    async def fake_record(session: Any, caller: McpCaller, **call: Any) -> None:
        calls.append(
            {"client": caller.client_name, **{key: call[key] for key in ("tool", "outcome", "reason")}}
        )

    monkeypatch.setattr(oauth_bearer, "caller_for", fake_caller)
    monkeypatch.setattr(oauth_bearer, "record_tool_call", fake_record)
    return calls


def test_a_reason_withholds_every_argument_the_call_sent() -> None:
    sent = sent_texts({"craft": "Kutch-Ajrakh", "quotes": [{"text": PRIVATE_WORDS}], "limit": 5})
    assert sent == ("Kutch-Ajrakh", PRIVATE_WORDS)
    text = f"No craft named {PRIVATE_WORDS} is in Kutch-Ajrakh's  list."
    assert failure_reason(text, sent=sent) == "No craft named … is in …'s list."


def test_a_reason_keeps_no_personal_data_or_secret() -> None:
    text = "Write to ravi@example.org or call 98765 43210 with Bearer abcdefghijklmnopqrstuvwx today."
    assert failure_reason(text, sent=()) == "Write to [email] or call [number] with Bearer [redacted] today."
    token = "kvmcp_at_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8S9t0U1v"
    assert failure_reason(f"refused {token} here", sent=()) == "refused [redacted] here"


def test_a_reason_is_cut_to_three_hundred_characters() -> None:
    reason = failure_reason("a" * 400, sent=())
    assert reason == "a" * 299 + "…"
    assert len(reason) == 300
    assert failure_reason("   ", sent=()) == "…"


def test_only_a_failed_call_keeps_a_reason_and_it_is_the_refusal_s_own_message() -> None:
    ok = {"jsonrpc": "2.0", "id": 9, "result": {"content": [], "isError": False}}
    assert mcp_auth.call_reason(FIND, ok) is None
    refused = tool_error(f"find_crafts found nothing for {PRIVATE_WORDS}; try a craft's own name.")
    assert mcp_auth.call_reason(FIND, refused) == "find_crafts found nothing for …; try a craft's own name."
    assert mcp_auth.call_reason(FIND, None) == "The call was sent as a notification, so it had no reply."


def test_an_unknown_tool_s_name_is_withheld_from_its_reason() -> None:
    sent = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": PRIVATE_WORDS}}
    reply = {
        "jsonrpc": "2.0",
        "id": 1,
        "error": {"code": -32602, "message": f"no tool is named {PRIVATE_WORDS}"},
    }
    assert mcp_auth.call_reason(sent, reply) == "no tool is named …"


def test_a_refused_call_through_the_route_records_its_client_and_reason_never_its_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with_hosts(monkeypatch)
    calls = recorded_calls(monkeypatch)

    async def refusing(message: Any, context: ToolContext) -> dict[str, Any]:
        return tool_error(f"No craft is named {PRIVATE_WORDS}.")

    monkeypatch.setattr(mcp, "answer", refusing)
    reply = client().post("/api/mcp", json=FIND, headers=BEARER)
    assert reply.status_code == 200
    assert calls == [
        {"client": "Claude", "tool": "find_crafts", "outcome": "TOOL_ERROR", "reason": "No craft is named …."}
    ]


def test_a_call_the_server_failed_is_recorded_with_its_reason_after_a_rollback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with_hosts(monkeypatch)
    calls = recorded_calls(monkeypatch)

    async def failing(message: Any, context: ToolContext) -> dict[str, Any]:
        raise RuntimeError("the database went away")

    monkeypatch.setattr(mcp, "answer", failing)
    session = FakeSession()
    with pytest.raises(RuntimeError, match="the database went away"):
        client(session).post("/api/mcp", json=FIND, headers=BEARER)
    assert (session.rollbacks, session.commits) == (1, 1)
    assert calls == [
        {
            "client": "Claude",
            "tool": "find_crafts",
            "outcome": "PROTOCOL_ERROR",
            "reason": "The server failed while answering; call the tool again.",
        }
    ]
