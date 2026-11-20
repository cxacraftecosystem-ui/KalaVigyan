from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Craft, CraftPageSnapshot, Source
from app.research.citations import SourceRef
from app.research.craft_page import CRAFT_PAGE_SCHEMA_VERSION, CraftPage
from app.research.retrieval import RESTRICTED_SENSITIVITY

from . import knowledge_view
from .craft_page_snapshots import OPEN, built_page
from .craft_page_stamp import page_stamp
from .document_components import DocumentStructure, block_citations, document_structure
from .open_work_subjects import WorkSubject

__all__ = ["open_page", "subject_structure"]

CRAFT = "craft"


async def subject_structure(session: AsyncSession, subject: WorkSubject) -> DocumentStructure | None:
    if subject.kind != CRAFT or not subject.curated:
        return None
    craft = await session.get(Craft, subject.id)
    if craft is None:
        return None
    page = await open_page(session, craft)
    return document_structure(page, await _unlisted_sources(session, page))


async def open_page(session: AsyncSession, craft: Craft) -> CraftPage:
    stamp = await page_stamp(session, craft, OPEN)
    stored = await session.get(CraftPageSnapshot, (craft.id, OPEN))
    if stored is not None and stored.stamp == stamp and stored.schemaVersion == CRAFT_PAGE_SCHEMA_VERSION:
        return CraftPage.model_validate(stored.body)
    return await built_page(session, craft, OPEN)


async def _unlisted_sources(session: AsyncSession, page: CraftPage) -> dict[str, SourceRef]:
    listed = {source.id for source in page.sources}
    wanted: set[uuid.UUID] = set()
    for chapter in page.chapters:
        for item in chapter.items:
            if item.block is None:
                continue
            for source_id in block_citations(item.block)[0]:
                if source_id not in listed and (found := _uuid(source_id)) is not None:
                    wanted.add(found)
    if not wanted:
        return {}
    rows = await session.scalars(
        select(Source).where(Source.id.in_(sorted(wanted)), Source.sensitivity != RESTRICTED_SENSITIVITY)
    )
    return {str(row.id): SourceRef.model_validate(knowledge_view.source_ref(row)) for row in rows.all()}


def _uuid(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(value)
    except ValueError:
        return None
