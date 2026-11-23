from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.geo.climate import TREND_DATASETS, ClimateTrends, climate_trends
from app.geo.groundwater import GROUNDWATER_DATASETS, with_groundwater

from .knowledge_view import resolve_craft
from .place_offers import district_refs, mapped_districts
from .region_records import dataset_records, district_values

__all__ = ["CLIMATE_DISTRICTS_MAX", "craft_climate"]

CLIMATE_DISTRICTS_MAX = 4


async def craft_climate(session: AsyncSession, craft_slug: str) -> ClimateTrends:
    craft = await resolve_craft(session, craft_slug)
    lgds = (await mapped_districts(session, craft))[:CLIMATE_DISTRICTS_MAX] if craft is not None else ()
    if not lgds:
        return ClimateTrends()
    named = await district_refs(session, lgds)
    districts = [named[lgd] for lgd in lgds if lgd in named]
    codes = {*TREND_DATASETS.values(), *GROUNDWATER_DATASETS}
    datasets = await dataset_records(session, codes)
    values = await district_values(session, [district.district_lgd for district in districts], codes=codes)
    return with_groundwater(climate_trends(districts, values, datasets), districts, values, datasets)
