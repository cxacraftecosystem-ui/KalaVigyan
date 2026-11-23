from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput
from app.models import ClaimSource, Source
from app.research.front_page import producer_token
from app.research.source_titles import junk_title
from app.research.storable import storable_text

from . import audit

__all__ = [
    "RETITLED",
    "JunkTitled",
    "ProducerAuthored",
    "junk_titled",
    "producer_authored",
    "retitle_junk",
    "retitle_source",
]

RETITLED = "source.retitled"


@dataclass(frozen=True)
class JunkTitled:
    id: uuid.UUID
    title: str
    url: str | None
    citations: int

    def as_dict(self) -> dict[str, Any]:
        return {"id": str(self.id), "title": self.title, "url": self.url, "citations": self.citations}


@dataclass(frozen=True)
class ProducerAuthored:
    id: uuid.UUID
    title: str
    url: str | None
    authors: tuple[str, ...]
    citations: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "title": self.title,
            "url": self.url,
            "authors": list(self.authors),
            "citations": self.citations,
        }


async def retitle_junk(session: AsyncSession, source_id: uuid.UUID, title: str) -> bool:
    if junk_title(title):
        return False
    stored = await session.scalar(select(Source.title).where(Source.id == source_id))
    if stored is None or not junk_title(stored):
        return False
    await session.execute(
        update(Source).where(Source.id == source_id).values(title=storable_text(title.strip()))
    )
    return True


async def junk_titled(session: AsyncSession) -> list[JunkTitled]:
    rows = await session.execute(select(Source.id, Source.title, Source.url))
    junk = [(source_id, title, url) for source_id, title, url in rows.tuples().all() if junk_title(title)]
    counts = await _citation_counts(session, [source_id for source_id, _, _ in junk])
    return [JunkTitled(source_id, title, url, counts.get(source_id, 0)) for source_id, title, url in junk]


async def producer_authored(session: AsyncSession) -> list[ProducerAuthored]:
    rows = await session.execute(
        select(Source.id, Source.title, Source.url, Source.authors).order_by(Source.id)
    )
    listed = [
        (source_id, title, url, tuple(str(author) for author in authors or ()))
        for source_id, title, url, authors in rows.tuples().all()
    ]
    found = [row for row in listed if any(producer_token(author) for author in row[3])]
    counts = await _citation_counts(session, [source_id for source_id, _, _, _ in found])
    return [
        ProducerAuthored(source_id, title, url, named, counts.get(source_id, 0))
        for source_id, title, url, named in found
    ]


async def retitle_source(session: AsyncSession, source_id: uuid.UUID, title: str, *, actor: Any) -> str:
    if junk_title(title):
        raise InvalidInput(f"{title!r} is not a work's title: give at least three words of it")
    before = await session.scalar(select(Source.title).where(Source.id == source_id))
    if before is None:
        raise InvalidInput(f"No source has the id {source_id}")
    await session.execute(
        update(Source).where(Source.id == source_id).values(title=storable_text(title.strip()))
    )
    await audit.record(
        session,
        action=RETITLED,
        actor=actor,
        target_type="Source",
        target_id=source_id,
        detail={"from": before, "to": title.strip()},
    )
    return before


async def _citation_counts(session: AsyncSession, source_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    if not source_ids:
        return {}
    rows = await session.execute(
        select(ClaimSource.sourceId, func.count())
        .where(ClaimSource.sourceId.in_(source_ids))
        .group_by(ClaimSource.sourceId)
    )
    return {source_id: int(count) for source_id, count in rows.tuples().all()}
