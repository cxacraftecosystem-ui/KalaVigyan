from __future__ import annotations

from collections.abc import Awaitable, Callable, Collection, Mapping
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.data.district_register import load_district_codes
from app.models import AdminDistrict, CuratedCraft, WikidataPoint

from . import knowledge_view
from .curated_index import stored_curated_page
from .place_points import OriginPlace, RegisterPoint
from .stated_names import register_places

__all__ = [
    "KnownPoints",
    "KnownPointsLoader",
    "curated_points",
    "known_points",
    "register_district",
    "register_points",
    "stored_known_points",
]


@dataclass(frozen=True)
class KnownPoints:
    register: Mapping[str, RegisterPoint] = field(default_factory=dict)
    curated: Mapping[str, OriginPlace] = field(default_factory=dict)

    def placed(self, key: str) -> bool:
        return key in self.register or key in self.curated


KnownPointsLoader = Callable[[str | None, Collection[str]], Awaitable[KnownPoints]]


def register_district(name: str) -> int | None:
    found = register_places(name)
    if len(found) != 1 or found[0].written != name.strip():
        return None
    codes = load_district_codes()
    pairs = [pair for pair in codes.districts if pair[1] == found[0].register]
    return codes.districts[pairs[0]] if len(pairs) == 1 else None


async def register_points(session: AsyncSession, names: Collection[str]) -> dict[str, RegisterPoint]:
    wanted = {name.casefold(): lgd for name in names if (lgd := register_district(name)) is not None}
    if not wanted:
        return {}
    rows = await session.execute(
        select(AdminDistrict.lgd, func.ST_Y(AdminDistrict.centroid), func.ST_X(AdminDistrict.centroid)).where(
            AdminDistrict.lgd.in_(set(wanted.values())), AdminDistrict.centroid.is_not(None)
        )
    )
    found = {int(lgd): (float(latitude), float(longitude)) for lgd, latitude, longitude in rows.all()}
    return {key: RegisterPoint(lgd, *found[lgd]) for key, lgd in wanted.items() if lgd in found}


async def curated_points(
    session: AsyncSession, craft_slug: str, names: Collection[str]
) -> dict[str, OriginPlace]:
    craft = await knowledge_view.resolve_craft(session, craft_slug)
    page = (
        await session.scalar(select(CuratedCraft.page).where(CuratedCraft.craftId == craft.id))
        if craft
        else None
    )
    curated = stored_curated_page(craft.id, page) if craft is not None else None
    if curated is None:
        return {}
    wanted = {name.casefold() for name in names}
    items = {
        place.name.casefold(): place.wikidata_id
        for place in curated.places
        if place.wikidata_id and place.name.casefold() in wanted
    }
    rows = await session.execute(
        select(WikidataPoint.wikidataId, WikidataPoint.latitude, WikidataPoint.longitude).where(
            WikidataPoint.wikidataId.in_(set(items.values()))
        )
    )
    found = {str(item): (float(latitude), float(longitude)) for item, latitude, longitude in rows.all()}
    return {key: OriginPlace(item, *found[item]) for key, item in items.items() if item in found}


async def known_points(session: AsyncSession, craft_slug: str | None, names: Collection[str]) -> KnownPoints:
    register = await register_points(session, names)
    rest = [name for name in names if name.casefold() not in register]
    curated = await curated_points(session, craft_slug, rest) if craft_slug and rest else {}
    return KnownPoints(register=register, curated=curated)


def stored_known_points(sessions: async_sessionmaker[AsyncSession]) -> KnownPointsLoader:
    async def load(craft_slug: str | None, names: Collection[str]) -> KnownPoints:
        async with sessions() as session:
            return await known_points(session, craft_slug, names)

    return load
