import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import session_id_of
from app.models import SiteSession

__all__ = ["continued_site_session", "end_site_session", "open_site_session", "site_session_live"]


async def open_site_session(session: AsyncSession, user_id: uuid.UUID, *, now: datetime) -> uuid.UUID:
    opened = SiteSession(userId=user_id, createdAt=now, renewedAt=now)
    session.add(opened)
    await session.flush()
    return opened.id


async def site_session_live(session: AsyncSession, user_id: uuid.UUID, session_id: uuid.UUID | None) -> bool:
    if session_id is None:
        return True
    found = await session.get(SiteSession, session_id)
    return found is not None and found.userId == user_id and found.endedAt is None


async def continued_site_session(
    session: AsyncSession, user_id: uuid.UUID, session_id: uuid.UUID | None, *, now: datetime
) -> uuid.UUID:
    if session_id is None:
        return await open_site_session(session, user_id, now=now)
    await session.execute(
        update(SiteSession)
        .where(SiteSession.id == session_id, SiteSession.userId == user_id, SiteSession.endedAt.is_(None))
        .values(renewedAt=now)
    )
    return session_id


async def end_site_session(session: AsyncSession, claims: dict[str, Any], *, now: datetime) -> None:
    session_id = session_id_of(claims)
    user_id = _subject(claims)
    if session_id is None or user_id is None:
        return
    await session.execute(
        update(SiteSession)
        .where(SiteSession.id == session_id, SiteSession.userId == user_id, SiteSession.endedAt.is_(None))
        .values(endedAt=now)
    )


def _subject(claims: dict[str, Any]) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(claims.get("sub")))
    except ValueError:
        return None
