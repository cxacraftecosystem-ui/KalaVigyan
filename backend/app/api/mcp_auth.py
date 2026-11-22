from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.mcp_protocol import INTERNAL_ERROR, error_reply
from app.api.mcp_tool_base import Tool
from app.api.mcp_tools import TOOLS
from app.api.oauth_hosts import configured_endpoints, endpoints_or_none
from app.api.public_deps import counted_anonymous_read
from app.core.mcp_scopes import READ_SCOPE
from app.core.rate_limit import mcp_connection_attempt
from app.core.throttle_refusal import refuse_when_throttled
from app.research.mcp_activity import failure_reason, sent_texts
from app.research.oauth_metadata import bearer_challenge
from app.research.oauth_rules import joined_scopes, ordered_scopes
from app.services import oauth_bearer
from app.services.oauth_bearer import BearerRefused, McpCaller

__all__ = [
    "CALL_METHOD",
    "SERVER_FAILED",
    "UNKNOWN_TOOL",
    "call_outcome",
    "call_reason",
    "called_tool_name",
    "mcp_caller",
    "record_call",
    "record_failed_call",
    "scope_challenge",
]

CALL_METHOD = "tools/call"
UNKNOWN_TOOL = "(unknown)"
OK = "OK"
BEARER = "bearer"
NOT_BEARER = "Send the access token as Authorization: Bearer."
CONNECTION_SPENT = "This connection made many calls in the last few minutes. Wait a little and try again."
SIGN_IN_NEEDED = "This tool needs a signed-in connection."
SCOPE_NEEDED = "This connection was not given the scope this tool needs."
SERVER_FAILED = "The server failed while answering; call the tool again."
NOTIFIED = "The call was sent as a notification, so it had no reply."
UNSAID = "The reply gave no reason."


async def mcp_caller(request: Request, session: AsyncSession) -> McpCaller | None:
    header = request.headers.get("authorization")
    if header is None:
        await counted_anonymous_read(request)
        return None
    endpoints = configured_endpoints()
    scheme, _, raw = header.partition(" ")
    try:
        if scheme.lower() != BEARER or not raw.strip():
            raise BearerRefused(NOT_BEARER)
        caller = await oauth_bearer.caller_for(session, raw.strip(), resource=endpoints.resource, now=_now())
    except BearerRefused as refused:
        await counted_anonymous_read(request)
        challenge = bearer_challenge(endpoints, error="invalid_token", description=refused.description)
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, refused.description, {"WWW-Authenticate": challenge}
        ) from refused
    refuse_when_throttled(await mcp_connection_attempt(str(caller.grant_id)), CONNECTION_SPENT)
    return caller


def scope_challenge(message: Any, caller: McpCaller | None) -> JSONResponse | None:
    tool = _called_tool(message)
    scope = READ_SCOPE if tool is None else tool.scope_for(message["params"].get("arguments"))
    if tool is None or scope == READ_SCOPE:
        return None
    if caller is not None and scope in caller.scopes:
        return None
    endpoints = endpoints_or_none()
    if endpoints is None:
        return None
    if caller is None:
        challenge = bearer_challenge(endpoints, scope=joined_scopes((READ_SCOPE, scope)))
        return _refusal(status.HTTP_401_UNAUTHORIZED, SIGN_IN_NEEDED, challenge)
    wanted = joined_scopes(ordered_scopes({*caller.scopes, scope}))
    challenge = bearer_challenge(
        endpoints, error="insufficient_scope", description=SCOPE_NEEDED, scope=wanted
    )
    return _refusal(status.HTTP_403_FORBIDDEN, SCOPE_NEEDED, challenge)


async def record_call(
    session: AsyncSession, caller: McpCaller, message: Any, reply: dict[str, Any] | None
) -> None:
    tool = called_tool_name(message)
    if tool is None:
        await oauth_bearer.touch(session, caller, now=_now())
    else:
        await oauth_bearer.record_tool_call(
            session,
            caller,
            tool=tool,
            outcome=call_outcome(reply),
            reason=call_reason(message, reply),
            now=_now(),
        )
    await session.commit()


async def record_failed_call(session: AsyncSession, caller: McpCaller, message: Any) -> None:
    await session.rollback()
    request_id = message.get("id") if isinstance(message, dict) else None
    await record_call(session, caller, message, error_reply(request_id, INTERNAL_ERROR, SERVER_FAILED))


def called_tool_name(message: Any) -> str | None:
    if not isinstance(message, dict) or message.get("method") != CALL_METHOD:
        return None
    tool = _called_tool(message)
    return UNKNOWN_TOOL if tool is None else tool.name


def call_outcome(reply: dict[str, Any] | None) -> str:
    if reply is None or "error" in reply:
        return "PROTOCOL_ERROR"
    result = reply.get("result")
    if isinstance(result, dict) and result.get("isError"):
        return "TOOL_ERROR"
    return OK


def call_reason(message: Any, reply: dict[str, Any] | None) -> str | None:
    if call_outcome(reply) == OK:
        return None
    params = message.get("params") if isinstance(message, dict) else None
    sent = sent_texts(params.get("arguments")) if isinstance(params, dict) else ()
    if isinstance(params, dict) and called_tool_name(message) == UNKNOWN_TOOL:
        sent += sent_texts(params.get("name"))
    return failure_reason(_refusal_text(reply), sent=sent)


def _refusal_text(reply: dict[str, Any] | None) -> str:
    if reply is None:
        return NOTIFIED
    error = reply.get("error")
    if isinstance(error, dict):
        return str(error.get("message") or UNSAID)
    result = reply.get("result")
    content = result.get("content") if isinstance(result, dict) else None
    items = content if isinstance(content, list) else []
    said = [item["text"] for item in items if isinstance(item, dict) and isinstance(item.get("text"), str)]
    return " ".join(said) or UNSAID


def _called_tool(message: Any) -> Tool | None:
    if not isinstance(message, dict) or message.get("method") != CALL_METHOD:
        return None
    params = message.get("params")
    if not isinstance(params, dict):
        return None
    return TOOLS.get(str(params.get("name")))


def _refusal(code: int, detail: str, challenge: str) -> JSONResponse:
    return JSONResponse({"detail": detail}, status_code=code, headers={"WWW-Authenticate": challenge})


def _now() -> datetime:
    return datetime.now(UTC)
