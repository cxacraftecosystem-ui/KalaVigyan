from __future__ import annotations

import logging
import uuid
from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models import Craft, CraftPageSnapshot, CuratedCraft
from app.research.craft_page import CRAFT_PAGE_SCHEMA_VERSION
from app.research.monograph_page import MonographContent
from app.research.page_revalidation import PageOwners

from .craft_chapters_job import chapter_crafts
from .craft_page_snapshots import rebuild_snapshots
from .craft_page_stamp import PAGE_VARIANTS, page_stamp
from .monograph_load import load_monograph
from .page_revalidation import merged_owners
from .stored_document_rebuilds import DocumentsReport, rebuild_stale_documents, subject_owners

__all__ = [
    "DOCUMENTS_PER_NIGHT",
    "MONOGRAPHS_PER_NIGHT",
    "PAGES_PER_NIGHT",
    "MonographLoader",
    "PagesReport",
    "StalePage",
    "rebuild_documents",
    "rebuild_monographs",
    "rebuild_order",
    "rebuild_stale_pages",
    "rotating_window",
    "stale_crafts",
]

logger = logging.getLogger(__name__)

MONOGRAPHS_PER_NIGHT = 20
PAGES_PER_NIGHT = 60
DOCUMENTS_PER_NIGHT = 200
NEVER_BUILT = datetime.min.replace(tzinfo=UTC)

MonographLoader = Callable[[str], MonographContent]


@dataclass
class PagesReport:
    monographs: list[dict[str, Any]] = field(default_factory=list)
    pages_stale: int = 0
    pages_rebuilt: list[str] = field(default_factory=list)
    pages_changed: int = 0
    failed: list[str] = field(default_factory=list)
    documents: DocumentsReport = field(default_factory=DocumentsReport)
    changed_crafts: list[str] = field(default_factory=list)

    def changed_owners(self) -> PageOwners:
        documents = [subject_owners(*named.split(":", 1)) for named in self.documents.moved]
        return merged_owners(PageOwners(crafts=tuple(self.changed_crafts)), *documents)

    def as_dict(self) -> dict[str, Any]:
        return {
            "monographs": self.monographs,
            "pagesStale": self.pages_stale,
            "pagesRebuilt": len(self.pages_rebuilt),
            "pagesChanged": self.pages_changed,
            "pagesFailed": self.failed,
            **self.documents.as_dict(),
        }


def rotating_window[Item](items: Sequence[Item], size: int, night: int) -> list[Item]:
    if size < 1:
        raise ValueError(f"a nightly window holds at least one item, not {size}")
    if len(items) <= size:
        return list(items)
    start = (night * size) % len(items)
    return [items[(start + offset) % len(items)] for offset in range(size)]


async def rebuild_monographs(
    session: AsyncSession,
    slugs: Sequence[str],
    load: MonographLoader,
    *,
    now: datetime,
    report: PagesReport,
) -> None:
    for slug in rotating_window(sorted(slugs), MONOGRAPHS_PER_NIGHT, now.date().toordinal()):
        try:
            loaded = await load_monograph(session, load(slug), now=now)
            await session.commit()
        except (AppError, ValidationError, OSError) as error:
            await session.rollback()
            logger.error("the monograph of %s could not be loaded: %s", slug, error)
            report.failed.append(f"monograph:{slug}")
            continue
        report.monographs.append(loaded.as_dict())
        if loaded.sections_written or loaded.components_written:
            report.changed_crafts.append(loaded.craft_slug)


async def stale_crafts(session: AsyncSession, *, skip: Collection[str]) -> list[tuple[uuid.UUID, str]]:
    curated = set((await session.scalars(select(CuratedCraft.craftId))).all())
    found: list[StalePage] = []
    for craft in await chapter_crafts(session, None):
        if craft.slug in skip:
            continue
        built = await _stale_since(session, craft)
        if built is not None:
            found.append(StalePage(craft.id, craft.slug, built, craft.id in curated))
    return [(page.craft_id, page.slug) for page in rebuild_order(found)]


@dataclass(frozen=True)
class StalePage:
    craft_id: uuid.UUID
    slug: str
    built_at: datetime
    curated: bool


def rebuild_order(pages: Sequence[StalePage]) -> list[StalePage]:
    return sorted(pages, key=lambda page: (not page.curated, page.built_at, page.slug))


async def rebuild_stale_pages(
    session: AsyncSession, *, skip: Collection[str], report: PagesReport, limit: int = PAGES_PER_NIGHT
) -> None:
    stale = await stale_crafts(session, skip=skip)
    report.pages_stale = len(stale)
    for craft_id, slug in stale[:limit]:
        craft = await session.get(Craft, craft_id)
        if craft is None:
            continue
        try:
            changed = await rebuild_snapshots(session, craft)
            await session.commit()
        except (AppError, ValidationError) as error:
            await session.rollback()
            logger.error("the page of %s could not be rebuilt: %s", slug, error)
            report.failed.append(f"page:{slug}")
            continue
        report.pages_rebuilt.append(slug)
        report.pages_changed += int(changed)
        if changed:
            report.changed_crafts.append(slug)


async def rebuild_documents(
    session: AsyncSession, *, report: PagesReport, limit: int = DOCUMENTS_PER_NIGHT
) -> None:
    await rebuild_stale_documents(session, report=report.documents, limit=limit)
    report.failed.extend(f"document:{named}" for named in report.documents.failed)


async def _stale_since(session: AsyncSession, craft: Craft) -> datetime | None:
    oldest: datetime | None = None
    for variant in PAGE_VARIANTS:
        stored = await session.get(CraftPageSnapshot, (craft.id, variant), populate_existing=True)
        if stored is None:
            return NEVER_BUILT
        current = stored.schemaVersion == CRAFT_PAGE_SCHEMA_VERSION
        if current and stored.stamp == await page_stamp(session, craft, variant):
            continue
        oldest = stored.builtAt if oldest is None else min(oldest, stored.builtAt)
    return oldest
