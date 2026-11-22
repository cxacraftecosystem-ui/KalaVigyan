from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from datetime import datetime

from sqlalchemy import ColumnElement, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import McpToolCall, OAuthClient, OAuthGrant, User
from app.research.mcp_activity import (
    CONNECTIONS_SHOWN,
    FAILED_CALLS_SHOWN,
    FAILED_OUTCOMES,
    ClientActivity,
    ConnectionActivity,
    FailedCall,
    calls_made,
    outcome_fields,
    tally,
)

from .mcp_activity_days import DayWindow

__all__ = ["client_activity", "connection_activity", "failed_calls"]


async def client_activity(
    session: AsyncSession, counts: Mapping[str, Mapping[str, int]], *, now: datetime
) -> list[ClientActivity]:
    rows = await session.execute(
        select(
            OAuthClient.name, func.count(OAuthGrant.id).filter(_live(now)), func.max(OAuthGrant.lastUsedAt)
        )
        .join(OAuthGrant, OAuthGrant.clientId == OAuthClient.id)
        .group_by(OAuthClient.name)
    )
    grants = {name: (int(live), last_used) for name, live, last_used in rows.all()}
    names = {name for name, (live, _) in grants.items() if live} | set(counts)
    shown = [
        ClientActivity(
            client_name=name,
            connections=grants.get(name, (0, None))[0],
            last_used_at=grants.get(name, (0, None))[1],
            **outcome_fields(counts.get(name, {})),
        )
        for name in names
    ]
    return sorted(shown, key=lambda client: (-calls_made(client), client.client_name))


async def connection_activity(
    session: AsyncSession, window: DayWindow, *, now: datetime
) -> list[ConnectionActivity]:
    called = select(McpToolCall.grantId).where(*window.holds_call())
    found = (
        await session.execute(
            select(OAuthGrant, OAuthClient.name, User.name, User.email)
            .join(OAuthClient, OAuthClient.id == OAuthGrant.clientId)
            .join(User, User.id == OAuthGrant.userId)
            .where(or_(_live(now), OAuthGrant.id.in_(called)))
            .order_by(OAuthGrant.lastUsedAt.desc().nulls_last(), OAuthGrant.createdAt.desc(), OAuthGrant.id)
            .limit(CONNECTIONS_SHOWN)
        )
    ).all()
    counts = await _grant_counts(session, window, [grant.id for grant, *_ in found])
    return [
        ConnectionActivity(
            id=grant.id,
            client_name=client,
            account_name=name,
            account_email=email,
            scopes=list(grant.scopes),
            connected_at=grant.createdAt,
            last_used_at=grant.lastUsedAt,
            ended=grant.revokedAt is not None or grant.expiresAt <= now,
            **outcome_fields(counts.get(grant.id, {})),
        )
        for grant, client, name, email in found
    ]


async def failed_calls(
    session: AsyncSession, window: DayWindow, *, client: str | None, connection: uuid.UUID | None
) -> list[FailedCall]:
    scope = [McpToolCall.outcome.in_(FAILED_OUTCOMES), *window.holds_call()]
    if client is not None:
        scope.append(McpToolCall.clientName == client)
    if connection is not None:
        scope.append(McpToolCall.grantId == connection)
    calls = await session.scalars(
        select(McpToolCall)
        .where(*scope)
        .order_by(McpToolCall.calledAt.desc(), McpToolCall.id)
        .limit(FAILED_CALLS_SHOWN)
    )
    return [
        FailedCall(
            called_at=call.calledAt,
            client_name=call.clientName,
            connection_id=call.grantId,
            tool=call.tool,
            outcome=call.outcome,
            reason=call.reason,
        )
        for call in calls
    ]


async def _grant_counts(
    session: AsyncSession, window: DayWindow, grants: Sequence[uuid.UUID]
) -> dict[uuid.UUID, dict[str, int]]:
    if not grants:
        return {}
    rows = await session.execute(
        select(McpToolCall.grantId, McpToolCall.outcome, func.count())
        .where(*window.holds_call(), McpToolCall.grantId.in_(grants))
        .group_by(McpToolCall.grantId, McpToolCall.outcome)
    )
    return tally((grant, outcome, int(calls)) for grant, outcome, calls in rows.all())


def _live(now: datetime) -> ColumnElement[bool]:
    return and_(OAuthGrant.revokedAt.is_(None), OAuthGrant.expiresAt > now)
