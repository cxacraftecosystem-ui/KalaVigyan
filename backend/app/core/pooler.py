from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Sequence

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

__all__ = ["POOLER_FULL_MARKS", "POOLER_RETRY_WAITS", "connected_session", "pooler_full"]

logger = logging.getLogger(__name__)

POOLER_FULL_MARKS = ("EMAXCONNSESSION", "max clients reached")
POOLER_RETRY_WAITS = (0.2, 0.5, 1.0)

Sleep = Callable[[float], Awaitable[None]]


def pooler_full(error: BaseException) -> bool:
    seen: set[int] = set()
    found: BaseException | None = error
    while found is not None and id(found) not in seen:
        if any(mark in str(found) for mark in POOLER_FULL_MARKS):
            return True
        seen.add(id(found))
        found = found.__cause__ or found.__context__
    return False


async def connected_session(
    sessions: Callable[[], AsyncSession],
    *,
    waits: Sequence[float] = POOLER_RETRY_WAITS,
    sleep: Sleep = asyncio.sleep,
) -> AsyncSession:
    for wait in waits:
        try:
            return await _connected(sessions())
        except (SQLAlchemyError, OSError) as error:
            if not pooler_full(error):
                raise
            logger.warning("the session pooler refused a connection; trying again in %.1f s", wait)
            await sleep(wait)
    return await _connected(sessions())


async def _connected(session: AsyncSession) -> AsyncSession:
    try:
        await session.connection()
    except BaseException:
        await session.close()
        raise
    return session
