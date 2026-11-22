from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models import McpToolCall, OAuthClient, OAuthGrant, OAuthToken, User
from app.models.oauth import MCP_REASON_CHARS, MCP_TOOL_OUTCOMES
from app.research.oauth_rules import ACCESS_TOKEN_PREFIX, held_scopes

from .oauth_tokens import ACCESS, grant_matches_user, stored_secret

__all__ = ["LAST_USED_STEP", "BearerRefused", "McpCaller", "caller_for", "record_tool_call", "touch"]

LAST_USED_STEP = timedelta(minutes=1)
NOT_OURS = "This is not a KalaVigyan MCP access token."
UNKNOWN = "The access token is unknown or was revoked; sign in again."
EXPIRED = "The access token has expired; refresh it."
FOREIGN = "The access token was issued for another server."
ENDED = "The account's sessions were ended; connect the app again."
OK = "OK"


class BearerRefused(AppError):
    def __init__(self, description: str) -> None:
        super().__init__(description)
        self.description = description


@dataclass(frozen=True)
class McpCaller:
    user: User
    scopes: frozenset[str]
    grant_id: uuid.UUID
    token_id: uuid.UUID
    client_name: str


async def caller_for(session: AsyncSession, raw: str, *, resource: str, now: datetime) -> McpCaller:
    digest = stored_secret(raw, ACCESS_TOKEN_PREFIX)
    if digest is None:
        raise BearerRefused(NOT_OURS)
    found = (
        await session.execute(
            select(OAuthToken, OAuthGrant, User, OAuthClient.name)
            .join(OAuthGrant, OAuthGrant.id == OAuthToken.grantId)
            .join(User, User.id == OAuthGrant.userId)
            .join(OAuthClient, OAuthClient.id == OAuthGrant.clientId)
            .where(OAuthToken.tokenHash == digest, OAuthToken.kind == ACCESS)
        )
    ).one_or_none()
    if found is None:
        raise BearerRefused(UNKNOWN)
    token, grant, user, client_name = found
    if token.revokedAt is not None or grant.revokedAt is not None:
        raise BearerRefused(UNKNOWN)
    if token.expiresAt <= now:
        raise BearerRefused(EXPIRED)
    if grant.resource != resource:
        raise BearerRefused(FOREIGN)
    if not grant_matches_user(grant, user):
        raise BearerRefused(ENDED)
    return McpCaller(
        user=user,
        scopes=frozenset(held_scopes(user, token.scopes)),
        grant_id=grant.id,
        token_id=token.id,
        client_name=client_name,
    )


async def record_tool_call(
    session: AsyncSession, caller: McpCaller, *, tool: str, outcome: str, reason: str | None, now: datetime
) -> None:
    _check_record(outcome, reason)
    session.add(
        McpToolCall(
            grantId=caller.grant_id,
            tokenId=caller.token_id,
            clientName=caller.client_name,
            tool=tool,
            outcome=outcome,
            reason=reason,
            calledAt=now,
        )
    )
    await touch(session, caller, now=now)


async def touch(session: AsyncSession, caller: McpCaller, *, now: datetime) -> None:
    await session.execute(
        update(OAuthGrant)
        .where(
            OAuthGrant.id == caller.grant_id,
            or_(OAuthGrant.lastUsedAt.is_(None), OAuthGrant.lastUsedAt < now - LAST_USED_STEP),
        )
        .values(lastUsedAt=now)
    )


def _check_record(outcome: str, reason: str | None) -> None:
    if outcome not in MCP_TOOL_OUTCOMES:
        raise ValueError(
            f"an MCP tool call's outcome is one of {', '.join(MCP_TOOL_OUTCOMES)}, not {outcome}"
        )
    if (outcome == OK) != (reason is None):
        raise ValueError(f"an MCP tool call keeps a reason exactly when it failed, and this one is {outcome}")
    if reason is not None and not 0 < len(reason) <= MCP_REASON_CHARS:
        raise ValueError(
            f"an MCP tool call's reason is 1 to {MCP_REASON_CHARS} characters, not {len(reason)}"
        )
