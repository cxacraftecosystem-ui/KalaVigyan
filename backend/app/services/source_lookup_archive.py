from __future__ import annotations

import re
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ExternalFailure
from app.curation.parts import WAYBACK_SNAPSHOT_PATTERN
from app.models import Source, SourceUpkeep
from app.sources.http import RatePolicy, ResponseCache, SourceHttp

from .source_lookup_models import ArchivedSource
from .source_lookup_sources import Archiver, SnapshotFinder
from .upkeep_archive import ARCHIVED_KEY

__all__ = [
    "WAYBACK_AVAILABLE",
    "WaybackSnapshots",
    "archived_copy",
    "archived_source",
    "wayback_snapshots",
]

WAYBACK_AVAILABLE = "https://archive.org/wayback/available"
AVAILABILITY_SERVICE = "wayback-available"
AVAILABILITY_RATE = RatePolicy(min_interval=1.0)
SNAPSHOT = re.compile(WAYBACK_SNAPSHOT_PATTERN)
PLAIN_ARCHIVE = "http://web.archive.org/"
SECURE_ARCHIVE = "https://web.archive.org/"
SAVED = (
    "The Wayback Machine saved {url} as {snapshot}. Cite the snapshot beside the live page when the live "
    "page blocks automated reading or may change."
)


class WaybackSnapshots:
    def __init__(self, http: SourceHttp) -> None:
        self.http = http

    async def closest(self, url: str) -> str | None:
        try:
            response = await self.http.get(WAYBACK_AVAILABLE, params={"url": url})
            payload = response.json(self.http.service)
        except ExternalFailure:
            return None
        return _snapshot_of(payload)


def wayback_snapshots(client: httpx.AsyncClient) -> WaybackSnapshots:
    http = SourceHttp(
        client=client, service=AVAILABILITY_SERVICE, policy=AVAILABILITY_RATE, cache=ResponseCache()
    )
    return WaybackSnapshots(http)


async def archived_copy(
    session: AsyncSession, stored: Source | None, url: str, snapshots: SnapshotFinder | None
) -> str | None:
    if SNAPSHOT.match(url):
        return url
    held = await _held_snapshot(session, stored)
    if held is not None:
        return held
    return None if snapshots is None else await snapshots.closest(url)


async def archived_source(archiver: Archiver, url: str) -> ArchivedSource:
    snapshot = await archiver.save(url)
    return ArchivedSource(url=url, archived_url=snapshot, message=SAVED.format(url=url, snapshot=snapshot))


async def _held_snapshot(session: AsyncSession, stored: Source | None) -> str | None:
    if stored is None:
        return None
    recorded = (stored.externalIds or {}).get(ARCHIVED_KEY)
    if isinstance(recorded, str) and recorded:
        return recorded
    found = await session.scalar(select(SourceUpkeep.archiveUrl).where(SourceUpkeep.sourceId == stored.id))
    return found if isinstance(found, str) and found else None


def _snapshot_of(payload: Any) -> str | None:
    snapshots = payload.get("archived_snapshots") if isinstance(payload, dict) else None
    closest = snapshots.get("closest") if isinstance(snapshots, dict) else None
    if not isinstance(closest, dict) or closest.get("available") is not True:
        return None
    found = closest.get("url")
    if not isinstance(found, str):
        return None
    secure = SECURE_ARCHIVE + found.removeprefix(PLAIN_ARCHIVE) if found.startswith(PLAIN_ARCHIVE) else found
    return secure if SNAPSHOT.match(secure) else None
