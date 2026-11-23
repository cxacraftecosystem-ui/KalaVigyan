from __future__ import annotations

import logging
from contextlib import AbstractAsyncContextManager, nullcontext
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.http_cache import body_version
from app.models import Craft, CraftPageSnapshot
from app.research.craft_page import CRAFT_PAGE_SCHEMA_VERSION, CraftPage
from app.research.retrieval import EVERY_CHUNK_ACLS, chunk_acls_for

from .chapter_records import chapter_rows
from .craft_page import craft_page
from .craft_page_cache import PageCache, PageKey, ServedPage, served_content
from .craft_page_records import craft_page_records
from .craft_page_stamp import PAGE_VARIANTS, page_stamp

__all__ = [
    "OPEN",
    "RESEARCHER",
    "VARIANT_ACLS",
    "built_page",
    "rebuild_snapshots",
    "served_page",
]

logger = logging.getLogger(__name__)

OPEN, RESEARCHER = PAGE_VARIANTS
VARIANT_ACLS = {OPEN: chunk_acls_for(None), RESEARCHER: EVERY_CHUNK_ACLS}
BUILD_LOCK = "craft-page:{craft}:{variant}"


async def built_page(session: AsyncSession, craft: Craft, variant: str) -> CraftPage:
    records = await craft_page_records(session, craft, acls=VARIANT_ACLS[variant])
    return craft_page(records, await chapter_rows(session, craft, records))


async def served_page(
    session: AsyncSession, craft: Craft, variant: str, *, cache: PageCache | None = None
) -> ServedPage:
    stamp = await page_stamp(session, craft, variant)
    key: PageKey = (craft.id, variant)
    kept = cache.kept(key, stamp) if cache is not None else None
    if kept is not None:
        return kept
    guard: AbstractAsyncContextManager[Any] = cache.lock(key) if cache is not None else nullcontext()
    async with guard:
        kept = cache.kept(key, stamp) if cache is not None else None
        if kept is not None:
            return kept
        page = await _snapshot(session, craft, variant, stamp)
        if cache is not None:
            cache.keep(key, page)
        return page


async def rebuild_snapshots(session: AsyncSession, craft: Craft) -> bool:
    changed = False
    for variant in PAGE_VARIANTS:
        stamp = await page_stamp(session, craft, variant)
        stored = await session.get(CraftPageSnapshot, (craft.id, variant), populate_existing=True)
        before = (stored.etag, stored.stamp) if stored is not None else None
        served = await _stored(session, craft, variant, stamp)
        if before is not None and before[0] != served.etag:
            changed = True
            if before[1] == stamp:
                logger.error(
                    "the %s page of %s changed under an unchanged stamp; an input the stamp misses moved",
                    variant,
                    craft.slug,
                )
    return changed


async def _snapshot(session: AsyncSession, craft: Craft, variant: str, stamp: str) -> ServedPage:
    stored = await _current(session, craft, variant, stamp)
    if stored is not None:
        return stored
    lock = BUILD_LOCK.format(craft=craft.id, variant=variant)
    await session.execute(select(func.pg_advisory_xact_lock(func.hashtextextended(lock, 0))))
    stored = await _current(session, craft, variant, stamp)
    if stored is not None:
        await session.commit()
        return stored
    return await _stored(session, craft, variant, stamp)


async def _current(session: AsyncSession, craft: Craft, variant: str, stamp: str) -> ServedPage | None:
    stored = await session.get(CraftPageSnapshot, (craft.id, variant), populate_existing=True)
    if stored is None or stored.stamp != stamp or stored.schemaVersion != CRAFT_PAGE_SCHEMA_VERSION:
        return None
    return ServedPage(served_content(stored.body), stored.etag, stamp)


async def _stored(session: AsyncSession, craft: Craft, variant: str, stamp: str) -> ServedPage:
    page = await built_page(session, craft, variant)
    body = page.model_dump(mode="json", by_alias=True)
    etag = body_version(body)
    now = utc_now()
    values = {
        "craftId": craft.id,
        "variant": variant,
        "stamp": stamp,
        "schemaVersion": CRAFT_PAGE_SCHEMA_VERSION,
        "body": body,
        "etag": etag,
        "builtAt": now,
    }
    statement = insert(CraftPageSnapshot).values(**values)
    await session.execute(
        statement.on_conflict_do_update(
            index_elements=[CraftPageSnapshot.craftId, CraftPageSnapshot.variant],
            set_={
                key: statement.excluded[key] for key in ("stamp", "schemaVersion", "body", "etag", "builtAt")
            },
        )
    )
    await session.commit()
    return ServedPage(served_content(body), etag, stamp)


def utc_now() -> datetime:
    return datetime.now(UTC)
