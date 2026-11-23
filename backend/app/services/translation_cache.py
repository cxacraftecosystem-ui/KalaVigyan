from __future__ import annotations

import hashlib
import uuid
from collections.abc import Mapping

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import ClaimTranslation
from app.research.translation_meaning import TRANSLATION_CHECKS_EDITION

__all__ = ["SqlTranslationCache", "checked_source_sha256", "source_sha256"]


def source_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def checked_source_sha256(text: str) -> str:
    return source_sha256(f"{TRANSLATION_CHECKS_EDITION}\n{text}")


class SqlTranslationCache:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def known(self, language: str, texts: Mapping[uuid.UUID, str]) -> dict[uuid.UUID, str]:
        if not texts:
            return {}
        query = select(ClaimTranslation.claimId, ClaimTranslation.sourceSha256, ClaimTranslation.text).where(
            ClaimTranslation.language == language, ClaimTranslation.claimId.in_(list(texts))
        )
        async with self._sessions() as session:
            rows = (await session.execute(query)).all()
        return {
            row.claimId: row.text
            for row in rows
            if row.sourceSha256 == checked_source_sha256(texts[row.claimId])
        }

    async def remember(self, language: str, entries: Mapping[uuid.UUID, tuple[str, str]]) -> None:
        if not entries:
            return
        values = [
            {
                "claimId": claim_id,
                "language": language,
                "sourceSha256": checked_source_sha256(source),
                "text": text,
            }
            for claim_id, (source, text) in entries.items()
        ]
        statement = insert(ClaimTranslation).values(values)
        statement = statement.on_conflict_do_update(
            index_elements=["claimId", "language"],
            set_={
                "sourceSha256": statement.excluded.sourceSha256,
                "text": statement.excluded.text,
                "updatedAt": func.now(),
            },
        )
        async with self._sessions() as session:
            await session.execute(statement)
            await session.commit()
