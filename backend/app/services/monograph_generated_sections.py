from __future__ import annotations

import uuid
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ArticleSection
from app.research.article_sections import SectionSentence

__all__ = ["PUBLISHED", "SUPERSEDED", "SectionOwner", "publish_section", "retire_sections"]

PUBLISHED = "PUBLISHED"
SUPERSEDED = "SUPERSEDED"
CRAFT_COLUMN = "craftId"
CATEGORY_COLUMN = "categoryId"


@dataclass(frozen=True)
class SectionOwner:
    column: str
    id: uuid.UUID

    @classmethod
    def craft(cls, craft_id: uuid.UUID) -> SectionOwner:
        return cls(CRAFT_COLUMN, craft_id)

    @classmethod
    def category(cls, category_id: uuid.UUID) -> SectionOwner:
        return cls(CATEGORY_COLUMN, category_id)

    def owns(self) -> ColumnElement[bool]:
        column: Any = ArticleSection.categoryId if self.column == CATEGORY_COLUMN else ArticleSection.craftId
        return column == self.id


async def publish_section(
    session: AsyncSession, owner: SectionOwner, field: str, sentences: Sequence[SectionSentence]
) -> bool:
    stored = [sentence.model_dump(mode="json", by_alias=True) for sentence in sentences]
    current = await session.scalar(
        select(ArticleSection).where(
            owner.owns(), ArticleSection.field == field, ArticleSection.status == PUBLISHED
        )
    )
    if current is not None and current.sentences == stored:
        return False
    latest = await session.scalar(
        select(func.max(ArticleSection.version)).where(owner.owns(), ArticleSection.field == field)
    )
    if current is not None:
        current.status = SUPERSEDED
        await session.flush()
    session.add(
        ArticleSection(
            **{owner.column: owner.id},
            field=field,
            version=(latest or 0) + 1,
            sentences=stored,
            status=PUBLISHED,
        )
    )
    return True


async def retire_sections(session: AsyncSession, owner: SectionOwner, kept: Collection[str]) -> list[str]:
    rows = await session.scalars(
        select(ArticleSection).where(
            owner.owns(), ArticleSection.status == PUBLISHED, ArticleSection.field.not_in(sorted(kept))
        )
    )
    retired = []
    for row in rows.all():
        row.status = SUPERSEDED
        retired.append(row.field)
    if retired:
        await session.flush()
    return sorted(retired)
