from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Refused
from app.core.roles import PROFESSOR, has_rank
from app.models import TranslationReader, User
from app.research.open_work_translation_keys import TRANSLATION_LANGUAGES

__all__ = ["NOT_A_REVIEWER", "reader_languages", "reads_language", "set_reader_languages"]

NOT_A_REVIEWER = "not_a_reviewer"
REVIEWERS_ONLY = "Only a Professor or Admin reviews translations, so only they name the languages they read."


async def reader_languages(session: AsyncSession, user_id: uuid.UUID) -> tuple[str, ...]:
    rows = await session.scalars(
        select(TranslationReader.language).where(TranslationReader.userId == user_id)
    )
    held = set(rows.all())
    return tuple(language for language in TRANSLATION_LANGUAGES if language in held)


async def reads_language(session: AsyncSession, user_id: uuid.UUID, language: str) -> bool:
    found = await session.scalar(
        select(TranslationReader.language).where(
            TranslationReader.userId == user_id, TranslationReader.language == language
        )
    )
    return found is not None


async def set_reader_languages(
    session: AsyncSession, user: User, languages: Sequence[str]
) -> tuple[str, ...]:
    if not has_rank(user, PROFESSOR):
        raise Refused(NOT_A_REVIEWER, REVIEWERS_ONLY)
    await session.execute(delete(TranslationReader).where(TranslationReader.userId == user.id))
    chosen = [language for language in TRANSLATION_LANGUAGES if language in set(languages)]
    session.add_all([TranslationReader(userId=user.id, language=language) for language in chosen])
    await session.flush()
    return tuple(chosen)
