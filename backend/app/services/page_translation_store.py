from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PageTranslation
from app.research.monograph_page import MonographContent
from app.research.page_translation_variant import ServedTranslations, translations_digest
from app.research.page_translations import (
    LIVE_TRANSLATION_STATUSES,
    SERVED_TRANSLATION_STATUSES,
    SUPERSEDED_STATUS,
)
from app.research.translation_passages import is_translatable, unit_hash

from .page_text_index import PageKey

__all__ = [
    "TranslationRow",
    "live_hashes",
    "page_rows",
    "remaining_passages",
    "served_translations",
    "supersede_others",
]


@dataclass(frozen=True)
class TranslationRow:
    id: str
    unit_key: str
    source_hash: str
    texts: tuple[str, ...]
    status: str


async def page_rows(
    session: AsyncSession, page: PageKey, language: str, statuses: Sequence[str]
) -> list[TranslationRow]:
    kind, slug = page
    rows = await session.execute(
        select(
            PageTranslation.id,
            PageTranslation.unitKey,
            PageTranslation.sourceHash,
            PageTranslation.texts,
            PageTranslation.status,
        )
        .where(
            PageTranslation.subjectKind == kind,
            PageTranslation.subjectSlug == slug,
            PageTranslation.language == language,
            PageTranslation.status.in_(statuses),
        )
        .order_by(PageTranslation.createdAt, PageTranslation.id)
    )
    return [
        TranslationRow(str(row_id), key, digest, tuple(texts), status)
        for row_id, key, digest, texts, status in rows.all()
    ]


async def served_translations(session: AsyncSession, page: PageKey, language: str) -> ServedTranslations:
    rows = await page_rows(session, page, language, SERVED_TRANSLATION_STATUSES)
    return ServedTranslations(
        by_hash={row.source_hash: row.texts for row in rows},
        earlier=frozenset(row.unit_key for row in rows),
        digest=translations_digest(row.id for row in rows),
    )


async def live_hashes(session: AsyncSession, page: PageKey, language: str) -> frozenset[str]:
    rows = await page_rows(session, page, language, LIVE_TRANSLATION_STATUSES)
    return frozenset(row.source_hash for row in rows)


async def remaining_passages(
    session: AsyncSession, page: PageKey, language: str, content: MonographContent
) -> int:
    live = await live_hashes(session, page, language)
    return sum(
        1
        for key, unit in content.units.items()
        if is_translatable(key, unit.nodes) and unit_hash(unit.nodes, unit.claim_ids) not in live
    )


async def supersede_others(session: AsyncSession, row: PageTranslation) -> None:
    await session.execute(
        update(PageTranslation)
        .where(
            PageTranslation.subjectKind == row.subjectKind,
            PageTranslation.subjectSlug == row.subjectSlug,
            PageTranslation.language == row.language,
            PageTranslation.sourceHash == row.sourceHash,
            PageTranslation.status.in_(SERVED_TRANSLATION_STATUSES),
            PageTranslation.id != row.id,
        )
        .values(status=SUPERSEDED_STATUS)
        .execution_options(synchronize_session="fetch")
    )
