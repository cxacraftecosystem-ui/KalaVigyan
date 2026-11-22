import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
from geoalchemy2 import WKTElement
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.composer.region_story import StoryChoice, StoryStepChoice
from app.core.db import get_engine
from app.models import (
    Craft,
    CraftLocation,
    DistrictEnvValue,
    EnvDataset,
    KnowledgePiece as PieceRow,
    RiverBasin,
    RiverReach,
    RiverReachDistrict,
)
from app.research.blocks_place import DistrictRef
from app.services import knowledge_view
from app.services.answer_events import cited_claims
from app.services.piece_lookup import PieceAsk
from app.services.piece_store import BuiltSection
from app.services.place_offers import region_offer, section_map_layer
from app.services.region_story import region_story_block, story_statements

from ..geo.golden_region import GI_JOURNAL, KACHCHH, golden_datasets
from .test_knowledge_pieces_db import AJRAKH, QUESTION, WATER_CLAIMS, answer_row, prose_of, store_for

pytestmark = pytest.mark.db

HEAD, MIDDLE, SIDE, OUTLET, COAST = 91000001, 91000002, 91000003, 91000004, 91000010
SHA = "b" * 64
HYDRORIVERS = "HYDRORIVERS_1_0"
VALUES = (
    ("SOILGRIDS_2_0", "phh2o", "0-5cm", "DISTRICT_MEAN", 8.1, "pH"),
    ("GHCN_CAMS_T2M", "annual_mean_temperature", "1981-2025", "NORMAL", 27.07, "degC"),
    (HYDRORIVERS, "river_density", "", "DENSITY", 0.21, "km/km2"),
    ("ESA_WORLDCOVER_2021_V200", "landcover_cropland", "2021", "SHARE", 0.236, "fraction"),
)


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async with get_engine().connect() as connection:
        transaction = await connection.begin()
        try:
            session = AsyncSession(bind=connection, expire_on_commit=False, autoflush=False)
            await session.execute(delete(RiverBasin))
            await session.execute(delete(EnvDataset))
            yield session
            await session.close()
        finally:
            await transaction.rollback()


async def store_datasets(session: AsyncSession) -> dict[str, uuid.UUID]:
    records = list(golden_datasets().values())
    ids = {record.code: uuid.uuid4() for record in records}
    session.add_all(
        EnvDataset(
            id=ids[record.code],
            code=record.code,
            title=record.title,
            publisher=record.publisher,
            edition=record.edition,
            period=record.period,
            nativeResolution=record.native_resolution,
            licence=record.licence,
            licenceUrl=record.licence_url,
            attribution=record.attribution,
            citation=record.citation,
            url=record.url,
        )
        for record in records
    )
    await session.flush()
    return ids


def reach(hyriv_id: int, next_down: int, main_riv: int, line: str, measures: tuple[float, int, float]) -> Any:
    upland, order, discharge = measures
    return RiverReach(
        hyrivId=hyriv_id,
        nextDown=next_down,
        mainRiv=main_riv,
        ordStra=order,
        uplandSkm=upland,
        disAvCms=discharge,
        lengthKm=20.0,
        geom=WKTElement(f"LINESTRING({line})", srid=4326),
    )


async def store_rivers(session: AsyncSession, dataset_id: uuid.UUID) -> None:
    session.add_all(
        RiverBasin(mainRiv=main, datasetId=dataset_id, reachCount=count, topologySha256=SHA)
        for main, count in ((OUTLET, 4), (COAST, 1))
    )
    await session.flush()
    session.add_all(
        [
            reach(HEAD, MIDDLE, OUTLET, "69.40 23.35, 69.55 23.30", (120.0, 1, 0.3)),
            reach(MIDDLE, OUTLET, OUTLET, "69.55 23.30, 69.70 23.25", (260.0, 2, 0.8)),
            reach(SIDE, OUTLET, OUTLET, "69.80 23.38, 69.70 23.25", (150.0, 1, 0.5)),
            reach(OUTLET, 0, OUTLET, "69.70 23.25, 69.90 23.15", (410.0, 2, 1.2)),
            reach(COAST, 0, COAST, "70.10 23.30, 70.20 23.25", (900.0, 3, 0.6)),
        ]
    )
    await session.flush()
    session.add_all(
        RiverReachDistrict(hyrivId=hyriv_id, districtLgd=KACHCHH, entry=0.0)
        for hyriv_id in (HEAD, MIDDLE, SIDE, OUTLET, COAST)
    )


async def locate_in_kachchh(session: AsyncSession) -> Craft:
    craft = (await session.execute(select(Craft).where(Craft.slug == AJRAKH.slug))).scalar_one()
    await session.execute(delete(CraftLocation).where(CraftLocation.craftId == craft.id))
    session.add(
        CraftLocation(
            id=uuid.uuid4(),
            craftId=craft.id,
            precision="DISTRICT",
            districtLgd=KACHCHH,
            sourceId=uuid.UUID(GI_JOURNAL),
            evidenceLevel="PROVISIONAL",
        )
    )
    return craft


async def store_place(session: AsyncSession) -> Craft:
    ids = await store_datasets(session)
    await store_rivers(session, ids[HYDRORIVERS])
    session.add_all(
        DistrictEnvValue(
            districtLgd=KACHCHH,
            datasetId=ids[code],
            variable=variable,
            depthOrPeriod=stored,
            stat=stat,
            value=value,
            unit=unit,
        )
        for code, variable, stored, stat, value, unit in VALUES
    )
    craft = await locate_in_kachchh(session)
    await session.flush()
    return craft


async def test_the_offer_ranks_rivers_by_stream_order_then_discharge_and_traces_each(
    session: AsyncSession,
) -> None:
    await store_place(session)
    offer = await region_offer(session, AJRAKH.slug)
    assert offer is not None
    assert offer.craft_districts == (KACHCHH,)
    rivers = [(r.ref, r.trace.main_riv, r.trace.reach_ids, r.ord_stra, r.dis_av_cms) for r in offer.rivers]
    assert rivers == [("r1", COAST, [COAST], 3, 0.6), ("r2", OUTLET, [HEAD, MIDDLE, OUTLET], 2, 1.2)]
    assert [river.trace.district_lgds for river in offer.rivers] == [[KACHCHH], [KACHCHH]]
    assert offer.districts == {
        KACHCHH: DistrictRef(district_lgd=KACHCHH, name="Kachchh", state_name="Gujarat")
    }
    assert [layer.id for layer in offer.layers] == [
        "soil-ph-0-5cm",
        "annual-mean-temperature",
        "river-density",
    ]
    assert {"DR_DISTRICT_SHAPES", HYDRORIVERS, "SOILGRIDS_2_0"} <= set(offer.datasets)
    assert await region_offer(session, "No-Such-Craft") is None


async def test_a_section_map_highlights_the_craft_s_districts_with_a_value(session: AsyncSession) -> None:
    await store_place(session)
    geology = await section_map_layer(session, AJRAKH.slug, "GEOLOGY", ["The clay holds the dye."])
    assert geology is not None
    assert (geology.values.layer.spec.id, geology.highlighted) == ("soil-ph-0-5cm", (KACHCHH,))
    climate = await section_map_layer(session, AJRAKH.slug, "CLIMATE", [])
    assert climate is not None and climate.values.layer.spec.id == "annual-mean-temperature"
    assert await section_map_layer(session, AJRAKH.slug, "HISTORY", []) is None


async def test_a_stored_region_story_is_a_basin_piece_reused_while_its_river_is_stored(
    session: AsyncSession,
) -> None:
    await store_place(session)
    offer = await region_offer(session, AJRAKH.slug)
    prose = await prose_of(session, WATER_CLAIMS)
    views, sources = await knowledge_view.claims_by_id(session, WATER_CLAIMS)
    statements = story_statements([prose], cited_claims(list(views.values()), sources))
    choice = StoryChoice(
        river="r2",
        steps=[StoryStepChoice(claim=ref, district=f"d{KACHCHH}") for ref in statements],
        layers=["river-density", "annual-mean-temperature"],
    )
    story = region_story_block(offer, statements, choice, block_id="s1.b2")
    assert story is not None and story.river.reach_ids == [HEAD, MIDDLE, OUTLET]
    store = store_for(session)
    lookup = await store.reusable(PieceAsk(QUESTION, AJRAKH, ("GEOGRAPHY",), "EXPERT", fresh=True))
    answer_id = await answer_row(session)
    await store.keep(
        lookup, answer_id=answer_id, depth="EXPERT", sections=[BuiltSection("GEOGRAPHY", (prose, story))]
    )
    rows = (await session.scalars(select(PieceRow).where(PieceRow.createdFromAnswerId == answer_id))).all()
    kept = {row.kind: (row.craftId, row.topicKey) for row in rows}
    assert kept["region_story"] == (None, f"water:basin-{OUTLET}")
    assert kept["prose"][1] == lookup.topics["GEOGRAPHY"]
    found = await store.reusable(PieceAsk(QUESTION, AJRAKH, ("GEOGRAPHY",), "EXPERT"))
    assert [piece.kind for piece in found.reused["GEOGRAPHY"].pieces] == ["prose", "region_story"]
    await session.execute(delete(RiverReach).where(RiverReach.hyrivId == HEAD))
    again = await store.reusable(PieceAsk(QUESTION, AJRAKH, ("GEOGRAPHY",), "EXPERT"))
    assert [piece.kind for piece in again.reused["GEOGRAPHY"].pieces] == ["prose"]
