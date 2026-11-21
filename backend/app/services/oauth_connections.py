from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import OAuthClient, OAuthGrant, User
from app.research.oauth_contract import Connection

from .oauth_clients import shown_host
from .oauth_tokens import revoke_grant

__all__ = ["connections", "revoke_connection"]


async def connections(session: AsyncSession, user: User, *, now: datetime) -> list[Connection]:
    rows = await session.execute(
        select(OAuthGrant, OAuthClient)
        .join(OAuthClient, OAuthClient.id == OAuthGrant.clientId)
        .where(OAuthGrant.userId == user.id, OAuthGrant.revokedAt.is_(None), OAuthGrant.expiresAt > now)
        .order_by(OAuthGrant.createdAt.desc(), OAuthGrant.id)
    )
    return [
        Connection(
            id=grant.id,
            client_name=client.name,
            client_host=shown_host(client),
            scopes=list(grant.scopes),
            connected_at=grant.createdAt,
            last_used_at=grant.lastUsedAt,
        )
        for grant, client in rows.all()
    ]


async def revoke_connection(session: AsyncSession, user: User, grant_id: uuid.UUID, *, now: datetime) -> bool:
    found = await session.execute(
        select(OAuthGrant.id).where(
            OAuthGrant.id == grant_id, OAuthGrant.userId == user.id, OAuthGrant.revokedAt.is_(None)
        )
    )
    if found.scalar_one_or_none() is None:
        return False
    await revoke_grant(session, grant_id, now=now)
    return True
