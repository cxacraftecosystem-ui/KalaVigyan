from __future__ import annotations

from collections.abc import Iterable, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AdminDistrict, DistrictEnvValue, EnvDataset
from app.research.datasets import DatasetRef
from app.research.explainer import Block
from app.research.simulation_draft import RowValue

from .knowledge_view import resolve_craft
from .place_offers import mapped_districts

__all__ = ["cited_datasets", "first_district_rows"]

DATASETS_FIELD = "datasets"


def cited_datasets(blocks: Iterable[Block]) -> dict[str, DatasetRef]:
    found: dict[str, DatasetRef] = {}
    for block in blocks:
        if not block.cites_datasets():
            continue
        for ref in getattr(block, DATASETS_FIELD, ()):
            if isinstance(ref, DatasetRef):
                found.setdefault(ref.code, ref)
    return found


async def first_district_rows(
    session: AsyncSession, craft_slug: str, blocks: Sequence[Block]
) -> list[RowValue]:
    cited = cited_datasets(blocks)
    craft = await resolve_craft(session, craft_slug) if cited else None
    districts = await mapped_districts(session, craft) if craft is not None else ()
    if not districts:
        return []
    rows = await session.execute(
        select(
            EnvDataset.code,
            DistrictEnvValue.variable,
            DistrictEnvValue.depthOrPeriod,
            DistrictEnvValue.stat,
            DistrictEnvValue.value,
            DistrictEnvValue.unit,
            AdminDistrict.name,
        )
        .join(EnvDataset, EnvDataset.id == DistrictEnvValue.datasetId)
        .join(AdminDistrict, AdminDistrict.lgd == DistrictEnvValue.districtLgd)
        .where(
            DistrictEnvValue.districtLgd == districts[0],
            EnvDataset.code.in_(sorted(cited)),
            DistrictEnvValue.value.is_not(None),
        )
        .order_by(
            EnvDataset.code, DistrictEnvValue.variable, DistrictEnvValue.depthOrPeriod, DistrictEnvValue.stat
        )
    )
    return [
        RowValue(
            float(row.value),
            row.unit,
            _stated(row.variable, row.stat, row.depthOrPeriod, row.name),
            cited[row.code],
        )
        for row in rows
    ]


def _stated(variable: str, stat: str, period: str, district: str) -> str:
    when = f", {period}" if period else ""
    return f"{variable} ({stat.lower()}{when}) in {district}"
