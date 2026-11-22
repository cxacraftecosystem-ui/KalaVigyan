from __future__ import annotations

import json
import logging
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.mcp_auth import SERVER_FAILED, mcp_caller, record_call, record_failed_call, scope_challenge
from app.api.mcp_cors import is_web_origin
from app.api.mcp_protocol import INTERNAL_ERROR, PARSE_ERROR, error_reply, supported_version
from app.api.mcp_stream import EVENT_STREAM, STREAM_HEADERS, progress_token, reply_stream, streams
from app.api.mcp_tools import ToolContext, answer
from app.api.oauth_hosts import MCP_ROUTE
from app.core.config import get_settings
from app.core.db import get_session, release_connection, sessionmaker
from app.core.shielded import ShieldedWork
from app.services.oauth_bearer import McpCaller

router = APIRouter(tags=["mcp"])
logger = logging.getLogger(__name__)

MCP_PATH = MCP_ROUTE
VERSION_HEADER = "mcp-protocol-version"
NOT_ENABLED = "The KalaVigyan MCP server is not switched on."
FOREIGN_ORIGIN = "This web origin may not call the KalaVigyan MCP server."
UNKNOWN_VERSION = "This MCP protocol version is not supported; initialize again."
UNREADABLE = "The body is not JSON."
STREAMED_CALL = "mcp tools/call"

Sessions = Callable[[], AbstractAsyncContextManager[AsyncSession]]


def mcp_enabled() -> None:
    if not get_settings().mcp_server_enabled:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_ENABLED)


def stream_sessions() -> Sessions:
    return sessionmaker()


@router.post(MCP_PATH, dependencies=[Depends(mcp_enabled)])
async def mcp_message(
    request: Request,
    session: AsyncSession = Depends(get_session),
    sessions: Sessions = Depends(stream_sessions),
) -> Response:
    _check_origin(request)
    _check_version(request)
    caller = await mcp_caller(request, session)
    try:
        message = json.loads(await request.body())
    except ValueError:
        return JSONResponse(
            error_reply(None, PARSE_ERROR, UNREADABLE), status_code=status.HTTP_400_BAD_REQUEST
        )
    challenge = scope_challenge(message, caller)
    if challenge is not None:
        return challenge
    if streams(request.headers.get("accept"), message):
        await release_connection(session)
        return _streamed(request, message, caller, sessions)
    reply = await _answered(message, _context(request, caller, session), caller)
    if reply is None:
        return Response(status_code=status.HTTP_202_ACCEPTED)
    return JSONResponse(reply)


def _streamed(
    request: Request, message: Any, caller: McpCaller | None, sessions: Sessions
) -> StreamingResponse:
    shield: ShieldedWork = request.app.state.shielded_work
    work = shield.run(_answered_alone(request, message, caller, sessions), name=STREAMED_CALL)
    return StreamingResponse(
        reply_stream(work, progress_token(message)), media_type=EVENT_STREAM, headers=dict(STREAM_HEADERS)
    )


async def _answered_alone(
    request: Request, message: Any, caller: McpCaller | None, sessions: Sessions
) -> dict[str, Any] | None:
    try:
        async with sessions() as session:
            return await _answered(message, _context(request, caller, session), caller)
    except Exception:
        logger.exception("a streamed MCP call failed")
        return error_reply(message.get("id"), INTERNAL_ERROR, SERVER_FAILED)


async def _answered(message: Any, context: ToolContext, caller: McpCaller | None) -> dict[str, Any] | None:
    try:
        reply = await answer(message, context)
    except Exception:
        if caller is not None:
            await record_failed_call(context.session, caller, message)
        raise
    if caller is not None:
        await record_call(context.session, caller, message, reply)
    return reply


def _context(request: Request, caller: McpCaller | None, session: AsyncSession) -> ToolContext:
    return ToolContext(
        session=session,
        index=request.app.state.craft_index,
        site=get_settings().public_web_url.rstrip("/"),
        user=None if caller is None else caller.user,
        scopes=frozenset() if caller is None else caller.scopes,
    )


def _check_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin is not None and not is_web_origin(origin):
        raise HTTPException(status.HTTP_403_FORBIDDEN, FOREIGN_ORIGIN)


def _check_version(request: Request) -> None:
    version = request.headers.get(VERSION_HEADER)
    if version is not None and not supported_version(version):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, UNKNOWN_VERSION)
