from __future__ import annotations

from collections.abc import Collection

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Term

from .answer_translation import LocalNames

__all__ = ["glossary_local_names"]


def glossary_local_names(sessions: async_sessionmaker[AsyncSession]) -> LocalNames:
    async def lookup(keys: Collection[str]) -> dict[str, tuple[str, ...]]:
        async with sessions() as session:
            rows = await session.execute(select(Term.key, Term.localNames).where(Term.key.in_(sorted(keys))))
            return {key: tuple(names) for key, names in rows.tuples().all() if names}

    return lookup
