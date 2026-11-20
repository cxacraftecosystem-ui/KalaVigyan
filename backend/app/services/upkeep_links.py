from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import ColumnElement, Select, and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Source, SourceUpkeep
from app.research.open_work_links import ARCHIVED_URL_KEY

__all__ = [
    "ARCHIVES_ATTACHED_PER_NIGHT",
    "ROTTEN_AFTER_FAILURES",
    "LinksReport",
    "attach_archives",
    "look_after_links",
    "rotten_count",
    "rotten_source_ids",
]

ROTTEN_AFTER_FAILURES = 3
ARCHIVES_ATTACHED_PER_NIGHT = 200


@dataclass
class LinksReport:
    rotten: int = 0
    attached: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {"sourcesRotten": self.rotten, "archivesAttached": len(self.attached)}


def rotten_source_ids() -> Select[tuple[uuid.UUID]]:
    return (
        select(SourceUpkeep.sourceId)
        .join(Source, Source.id == SourceUpkeep.sourceId)
        .where(_rotting(), SourceUpkeep.archiveUrl.is_(None), Source.snapshotKey.is_(None))
    )


async def rotten_count(session: AsyncSession) -> int:
    counted = await session.scalar(select(func.count()).select_from(rotten_source_ids().subquery()))
    return int(counted or 0)


async def attach_archives(session: AsyncSession, *, limit: int = ARCHIVES_ATTACHED_PER_NIGHT) -> list[str]:
    rows = await session.execute(
        select(Source, SourceUpkeep.archiveUrl)
        .join(SourceUpkeep, SourceUpkeep.sourceId == Source.id)
        .where(_rotting(), SourceUpkeep.archiveUrl.is_not(None))
        .order_by(SourceUpkeep.checkedAt, Source.id)
        .limit(limit)
    )
    attached: list[str] = []
    for source, archive_url in rows.all():
        source.externalIds = {**(source.externalIds or {}), ARCHIVED_URL_KEY: archive_url}
        attached.append(str(source.id))
    await session.flush()
    return attached


async def look_after_links(session: AsyncSession) -> LinksReport:
    attached = await attach_archives(session)
    return LinksReport(rotten=await rotten_count(session), attached=attached)


def _rotting() -> ColumnElement[bool]:
    return and_(
        SourceUpkeep.failures >= ROTTEN_AFTER_FAILURES,
        ~Source.externalIds.has_key(ARCHIVED_URL_KEY),
    )
