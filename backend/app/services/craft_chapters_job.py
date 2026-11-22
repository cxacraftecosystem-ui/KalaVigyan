from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

import httpx
from pydantic import ValidationError
from sqlalchemy import or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, InvalidInput
from app.models import Compound, Craft, CraftPageSnapshot, CuratedCraft, WikidataPoint
from app.sources.reference.pubchem import PubChemAdapter
from app.sources.reference.registry import reference_sources
from app.sources.reference.wikidata import WikidataAdapter
from app.sources.reference.wikidata_places import COORDINATES_IDS_MAX, PlacePoint

from . import knowledge_view
from .craft_ai_media import PageCopyObjects, copied_older_media
from .craft_page_snapshots import rebuild_snapshots
from .craft_page_stamp import craft_compound_ids
from .curated_index import stored_curated_page
from .molecule_conformers import ConformerCache
from .object_store import media_bucket

__all__ = [
    "ChaptersReport",
    "ConformerKeeper",
    "PointFinder",
    "build_craft_chapters",
    "chapter_crafts",
    "chapter_lookups",
]

logger = logging.getLogger(__name__)


class ConformerKeeper(Protocol):
    async def conformer(self, cid: int) -> str | None: ...


class PointFinder(Protocol):
    async def place_points(self, item_ids: Sequence[str]) -> dict[str, PlacePoint]: ...


@dataclass
class ChaptersReport:
    crafts: int = 0
    conformers_kept: int = 0
    conformers_without_3d: int = 0
    points_kept: int = 0
    ai_media_copied: int = 0
    pages_rebuilt: int = 0
    pages_changed: int = 0
    failed: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failed

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "crafts": self.crafts,
            "conformersKept": self.conformers_kept,
            "conformersWithout3d": self.conformers_without_3d,
            "pointsKept": self.points_kept,
            "aiMediaCopied": self.ai_media_copied,
            "pagesRebuilt": self.pages_rebuilt,
            "pagesChanged": self.pages_changed,
            "failed": self.failed,
        }


def chapter_lookups(client: httpx.AsyncClient) -> tuple[ConformerKeeper | None, PointFinder]:
    sources = reference_sources(client)
    pubchem = next(adapter for adapter in sources if isinstance(adapter, PubChemAdapter))
    wikidata = next(adapter for adapter in sources if isinstance(adapter, WikidataAdapter))
    objects = media_bucket()
    return (ConformerCache(objects=objects, source=pubchem) if objects is not None else None), wikidata


async def chapter_crafts(session: AsyncSession, slug: str | None) -> list[Craft]:
    if slug is not None:
        craft = await knowledge_view.resolve_craft(session, slug)
        if craft is None:
            raise InvalidInput(f"no craft has the slug {slug!r}")
        return [craft]
    curated = select(CuratedCraft.craftId)
    snapshotted = select(CraftPageSnapshot.craftId)
    statement = (
        select(Craft).where(or_(Craft.id.in_(curated), Craft.id.in_(snapshotted))).order_by(Craft.slug)
    )
    return list((await session.scalars(statement)).all())


async def build_craft_chapters(
    session: AsyncSession,
    crafts: Sequence[Craft],
    *,
    lookups: tuple[ConformerKeeper | None, PointFinder],
    now: datetime,
    media: PageCopyObjects | None = None,
) -> ChaptersReport:
    conformers, points = lookups
    report = ChaptersReport(crafts=len(crafts))
    if conformers is not None:
        await _keep_conformers(session, crafts, conformers, (report, now))
    await _keep_points(session, crafts, points, (report, now))
    if media is not None:
        report.ai_media_copied = await copied_older_media(session, media)
    for craft in crafts:
        try:
            changed = await rebuild_snapshots(session, craft)
        except (AppError, ValidationError) as error:
            await session.rollback()
            logger.error("the page of %s could not be rebuilt: %s", craft.slug, error)
            report.failed.append(f"page:{craft.slug}")
            continue
        report.pages_rebuilt += 1
        report.pages_changed += int(changed)
    return report


async def _keep_conformers(
    session: AsyncSession,
    crafts: Sequence[Craft],
    keeper: ConformerKeeper,
    found: tuple[ChaptersReport, datetime],
) -> None:
    report, now = found
    wanted = or_(*(Compound.id.in_(craft_compound_ids(craft)) for craft in crafts)) if crafts else None
    if wanted is None:
        return
    statement = select(Compound.id, Compound.pubchemCid).where(
        wanted, Compound.pubchemCid.is_not(None), Compound.conformerKeptAt.is_(None)
    )
    for compound_id, cid in (await session.execute(statement.order_by(Compound.pubchemCid))).all():
        try:
            sdf = await keeper.conformer(cid)
        except AppError as error:
            logger.error("the 3D conformer of CID %s could not be kept: %s", cid, error)
            report.failed.append(f"conformer:{cid}")
            continue
        if sdf is None:
            report.conformers_without_3d += 1
            continue
        await session.execute(update(Compound).where(Compound.id == compound_id).values(conformerKeptAt=now))
        await session.commit()
        report.conformers_kept += 1


async def _keep_points(
    session: AsyncSession,
    crafts: Sequence[Craft],
    finder: PointFinder,
    found: tuple[ChaptersReport, datetime],
) -> None:
    report, now = found
    rows = await session.execute(
        select(CuratedCraft.craftId, CuratedCraft.page).where(
            CuratedCraft.craftId.in_([c.id for c in crafts])
        )
    )
    named: set[str] = set()
    for craft_id, page in rows.all():
        curated = stored_curated_page(craft_id, page)
        named |= {place.wikidata_id for place in curated.places if place.wikidata_id} if curated else set()
    kept = set(
        await session.scalars(select(WikidataPoint.wikidataId).where(WikidataPoint.wikidataId.in_(named)))
    )
    missing = sorted(named - kept)
    for start in range(0, len(missing), COORDINATES_IDS_MAX):
        batch = missing[start : start + COORDINATES_IDS_MAX]
        try:
            points = await finder.place_points(batch)
        except AppError as error:
            logger.error("the Wikidata points of %s could not be read: %s", ", ".join(batch), error)
            report.failed.append(f"points:{batch[0]}")
            continue
        for item_id, point in sorted(points.items()):
            values = {
                "wikidataId": item_id,
                "latitude": point.latitude,
                "longitude": point.longitude,
                "keptAt": now,
            }
            await session.execute(insert(WikidataPoint).values(**values).on_conflict_do_nothing())
        await session.commit()
        report.points_kept += len(points)
