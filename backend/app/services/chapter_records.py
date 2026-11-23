from __future__ import annotations

import uuid
from collections.abc import Collection, Mapping, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.geo.climate import ClimateTrends
from app.geo.datasets import region_dataset
from app.models import Compound, Craft, KnowledgePiece as PieceRow, Source, WikidataPoint
from app.research.blocks_climate import ClimateSeries, ClimateTrend
from app.research.blocks_play import SimulationBlock
from app.research.citations import SourceRef
from app.research.datasets import BOUNDARY_DATASET_CODE
from app.science.records import CompoundRecord

from .category_records import category_page_records
from .chapter_context import ChapterRows, PlacePoint, StoredExplainer
from .chapter_family import family_science, family_slug
from .climate_store import craft_climate
from .craft_page_records import CraftPageRecords
from .knowledge_view import source_ref
from .piece_lookup import stored_piece
from .place_offers import region_offer
from .region_records import dataset_records, district_values
from .season_supply_builders import craft_rainfall

__all__ = ["CONCEPT_TOPIC_PREFIX", "chapter_rows", "place_points", "trend_series"]

CONCEPT_TOPIC_PREFIX = "concept:"
SIMULATION = "simulation"
ENGLISH = "en"
DISTRICT_MEAN = "DISTRICT_MEAN"


async def chapter_rows(session: AsyncSession, craft: Craft, records: CraftPageRecords) -> ChapterRows:
    compounds, linked = await _compounds(session, records)
    climate = await craft_climate(session, craft.slug)
    offer = await region_offer(session, craft.slug)
    lgds = list(offer.craft_districts) if offer is not None else []
    boundary = (await dataset_records(session, [BOUNDARY_DATASET_CODE])).get(BOUNDARY_DATASET_CODE)
    slug = family_slug(records.craft)
    family_records = await category_page_records(session, slug) if slug else None
    return ChapterRows(
        compounds=compounds,
        material_compounds=linked,
        record_sources=await _sources(session, [c.source_id for c in compounds.values() if c.source_id]),
        conformers=await _conformers(session, [c.pubchem_cid for c in compounds.values() if c.pubchem_cid]),
        family=family_science(family_records, records.craft) if family_records else None,
        region=offer,
        climate=climate,
        series=await _series(session, climate),
        rainfall=await craft_rainfall(session, lgds) if lgds else None,
        points=await place_points(session, _wikidata_ids(records)),
        explainers=await _explainers(session, craft.id),
        datasets={BOUNDARY_DATASET_CODE: region_dataset(boundary)} if boundary else {},
        site=get_settings().public_web_url,
    )


async def place_points(session: AsyncSession, wikidata_ids: Collection[str]) -> dict[str, PlacePoint]:
    if not wikidata_ids:
        return {}
    rows = await session.scalars(
        select(WikidataPoint).where(WikidataPoint.wikidataId.in_(sorted(wikidata_ids)))
    )
    return {row.wikidataId: PlacePoint(row.wikidataId, row.latitude, row.longitude) for row in rows}


def _wikidata_ids(records: CraftPageRecords) -> set[str]:
    curated = records.curated
    return {place.wikidata_id for place in curated.places if place.wikidata_id} if curated else set()


def trend_series(trend: ClimateTrend, readings: Mapping[str, float | None]) -> ClimateSeries | None:
    first, last = (int(year) for year in trend.period.split("-"))
    values = [readings.get(str(year)) for year in range(first, last + 1)]
    if all(value is None for value in values):
        return None
    return ClimateSeries(
        district=trend.district,
        variable=trend.variable,
        dataset_code=trend.dataset_code,
        unit=trend.mean_unit,
        first_year=first,
        values=values,
    )


async def _compounds(
    session: AsyncSession, records: CraftPageRecords
) -> tuple[dict[uuid.UUID, CompoundRecord], dict[uuid.UUID, uuid.UUID]]:
    curated = records.curated
    cids = (
        {item.material_id: item.pubchem_cid for item in curated.materials if item.pubchem_cid}
        if curated
        else {}
    )
    stored = {
        use.material_id: use.compound for use in records.process.materials if use.material_id and use.compound
    }
    rows = await session.scalars(select(Compound).where(Compound.pubchemCid.in_(sorted(set(cids.values())))))
    by_cid = {row.pubchemCid: _compound(row) for row in rows}
    compounds = {compound.id: compound for compound in [*by_cid.values(), *stored.values()]}
    linked = {material_id: by_cid[cid].id for material_id, cid in cids.items() if cid in by_cid}
    linked.update({material_id: compound.id for material_id, compound in stored.items()})
    return compounds, linked


def _compound(row: Compound) -> CompoundRecord:
    return CompoundRecord(row.id, row.name, row.formula, row.pubchemCid, row.sourceId)


async def _sources(session: AsyncSession, source_ids: Collection[uuid.UUID]) -> dict[str, SourceRef]:
    if not source_ids:
        return {}
    rows = await session.scalars(select(Source).where(Source.id.in_(sorted(set(source_ids)))))
    return {str(row.id): SourceRef.model_validate(source_ref(row)) for row in rows}


async def _conformers(session: AsyncSession, cids: Sequence[int]) -> frozenset[int]:
    if not cids:
        return frozenset()
    rows = await session.scalars(
        select(Compound.pubchemCid).where(
            Compound.pubchemCid.in_(sorted(set(cids))), Compound.conformerKeptAt.is_not(None)
        )
    )
    return frozenset(cid for cid in rows if cid is not None)


async def _series(session: AsyncSession, climate: ClimateTrends) -> tuple[ClimateSeries, ...]:
    if not climate.trends:
        return ()
    lgds = sorted({trend.district.district_lgd for trend in climate.trends})
    codes = {trend.dataset_code for trend in climate.trends}
    rows = await district_values(session, lgds, codes=codes)
    found = []
    for trend in climate.trends:
        readings = {
            row.depth_or_period: row.value
            for row in rows
            if (row.district_lgd, row.dataset_code, row.variable, row.stat)
            == (trend.district.district_lgd, trend.dataset_code, trend.variable, DISTRICT_MEAN)
        }
        series = trend_series(trend, readings)
        if series is not None:
            found.append(series)
    return tuple(found)


async def _explainers(session: AsyncSession, craft_id: uuid.UUID) -> tuple[StoredExplainer, ...]:
    rows = await session.scalars(
        select(PieceRow)
        .where(
            PieceRow.craftId == craft_id,
            PieceRow.kind == SIMULATION,
            PieceRow.language == ENGLISH,
            PieceRow.readingStyle.is_(None),
            PieceRow.staleSince.is_(None),
            PieceRow.supersededById.is_(None),
            PieceRow.hiddenAt.is_(None),
            PieceRow.topicKey.startswith(CONCEPT_TOPIC_PREFIX),
        )
        .order_by(PieceRow.topicKey, PieceRow.createdAt.desc(), PieceRow.id)
    )
    found: dict[str, StoredExplainer] = {}
    for row in rows:
        piece = stored_piece(row)
        if piece is None or not isinstance(piece.payload, SimulationBlock):
            continue
        term_key = row.topicKey.removeprefix(CONCEPT_TOPIC_PREFIX)
        found.setdefault(term_key, StoredExplainer(piece_id=row.id, term_key=term_key, block=piece.payload))
    sources = await _sources(
        session,
        [uuid.UUID(sid) for e in found.values() for sid in e.block.cited_source_ids() if _is_uuid(sid)],
    )
    return tuple(StoredExplainer(e.piece_id, e.term_key, e.block, sources) for e in found.values())


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True
