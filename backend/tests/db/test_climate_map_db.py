import json
import uuid
from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import delete, select, update
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
)
from app.research.planning import PlanRequest
from app.research.retrieval import EVERY_CHUNK_ACLS, OPEN_CHUNK_ACLS
from app.research.sections import SectionSpec
from app.research.structured import StructuredReply
from app.services import knowledge_view
from app.services.answer_events import cited_claims
from app.services.builder_interface import BuildAsk, BuilderTools
from app.services.climate_risk import ClimateRiskBuilder
from app.services.climate_store import craft_climate
from app.services.district_crafts import district_records
from app.services.piece_lookup import PieceAsk
from app.services.piece_store import BuiltSection
from app.services.place_offers import region_offer
from app.services.region_story import region_story_block, story_statements

from ..geo.golden_region import GI_JOURNAL
from .closed_quotes import CLOSED_QUOTE, quote_closed, store_closed_sources
from .test_knowledge_pieces_db import AJRAKH, QUESTION, WATER_CLAIMS, answer_row, prose_of, store_for
from .test_place_db import KACHCHH, OUTLET, locate_in_kachchh, store_place

pytestmark = pytest.mark.db

CHIRPS = "CHIRPS_3_0"
PERIOD = "1981-2025"
TREND_ROWS = (
    ("NORMAL", 383.0, "mm/year"),
    ("TREND_PER_DECADE", 21.6, "mm/year per decade"),
    ("TREND_P_VALUE", 0.12, "p-value"),
)
BAGRU = "Bagru-Hand-Block-Print"


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


class MeaningModel:
    def __init__(self, refs: list[str]) -> None:
        self.refs = refs
        self.calls: list[str] = []

    async def __call__(self, *, system: str, user: str, schema: Mapping[str, Any]) -> StructuredReply:
        self.calls.append(user)
        return StructuredReply(text=json.dumps({"meaning": self.refs}), degraded=False)


async def store_trend(session: AsyncSession) -> None:
    chirps = EnvDataset(
        id=uuid.uuid4(),
        code=CHIRPS,
        title="Climate Hazards Center InfraRed Precipitation with Stations v3.0",
        edition="3.0",
        period=PERIOD,
        nativeResolution="0.05 degree",
        licence="CC BY 4.0",
    )
    session.add(chirps)
    await session.flush()
    session.add_all(
        DistrictEnvValue(
            districtLgd=KACHCHH,
            datasetId=chirps.id,
            variable="annual_precipitation",
            depthOrPeriod=PERIOD,
            stat=stat,
            value=value,
            unit=unit,
            resolution="0.05 degree",
        )
        for stat, value, unit in TREND_ROWS
    )
    await session.flush()


async def test_the_craft_s_district_trend_is_read_over_the_dataset_period(session: AsyncSession) -> None:
    await locate_in_kachchh(session)
    await store_trend(session)
    found = await craft_climate(session, AJRAKH.slug)
    (trend,) = found.trends
    assert (trend.district.district_lgd, trend.period, trend.mean, trend.slope_per_decade) == (
        KACHCHH,
        PERIOD,
        383.0,
        21.6,
    )
    assert (trend.p_value, trend.significant) == (0.12, False)
    assert [(row.code, row.period) for row in found.datasets] == [(CHIRPS, PERIOD)]
    assert (await craft_climate(session, "No-Such-Craft")).trends == ()


async def test_the_climate_builder_pairs_the_trend_with_a_cited_groundwater_claim(
    session: AsyncSession,
) -> None:
    await locate_in_kachchh(session)
    await store_trend(session)
    prose = await prose_of(session, WATER_CLAIMS)
    views, sources = await knowledge_view.claims_by_id(session, WATER_CLAIMS)
    request = PlanRequest(question="Is Kutch getting drier for Ajrakh?", mode="HYBRID", craft=AJRAKH)
    spec = SectionSpec(id="s6", discipline="CLIMATE", title="Climate", order=6)
    ask = BuildAsk(uuid.uuid4(), spec, request, (prose,), cited_claims(list(views.values()), sources))
    model = MeaningModel(["c1", "c7"])

    def sessions() -> AsyncSession:
        return AsyncSession(bind=session.bind, expire_on_commit=False, autoflush=False)

    tools = BuilderTools(sessions=sessions, live=None, plan_model=model, compose_model=None)
    (block,) = (await ClimateRiskBuilder(tools).build(ask)).blocks
    assert [trend.district.district_lgd for trend in block.trends] == [KACHCHH]
    assert len(block.meaning) == 1
    assert block.meaning[0].citations[0].claim_id in {str(claim) for claim in WATER_CLAIMS}


async def stored_story(session: AsyncSession, *, acls: Sequence[str] = OPEN_CHUNK_ACLS) -> uuid.UUID:
    offer = await region_offer(session, AJRAKH.slug)
    prose = await prose_of(session, WATER_CLAIMS, acls=acls)
    views, sources = await knowledge_view.claims_by_id(session, WATER_CLAIMS, acls=acls)
    statements = story_statements([prose], cited_claims(list(views.values()), sources))
    choice = StoryChoice(
        river="r2",
        steps=[StoryStepChoice(claim=ref, district=f"d{KACHCHH}") for ref in statements],
        layers=["river-density"],
    )
    story = region_story_block(offer, statements, choice, block_id="s1.b2")
    store = store_for(session)
    lookup = await store.reusable(PieceAsk(QUESTION, AJRAKH, ("GEOGRAPHY",), "EXPERT", fresh=True))
    answer_id = await answer_row(session)
    await store.keep(
        lookup, answer_id=answer_id, depth="EXPERT", sections=[BuiltSection("GEOGRAPHY", (prose, story))]
    )
    await session.execute(
        update(PieceRow)
        .where(PieceRow.createdFromAnswerId == answer_id, PieceRow.kind == "prose")
        .values(topicKey=f"water:lgd-{KACHCHH}")
    )
    return answer_id


async def piece_ids(session: AsyncSession, answer_id: uuid.UUID) -> dict[str, str]:
    rows = (await session.scalars(select(PieceRow).where(PieceRow.createdFromAnswerId == answer_id))).all()
    return {row.kind: str(row.id) for row in rows}


async def place_bagru_by_state(session: AsyncSession) -> None:
    bagru = (await session.execute(select(Craft).where(Craft.slug == BAGRU))).scalar_one()
    await session.execute(delete(CraftLocation).where(CraftLocation.craftId == bagru.id))
    session.add(
        CraftLocation(
            id=uuid.uuid4(),
            craftId=bagru.id,
            precision="STATE",
            stateLgd=24,
            sourceId=uuid.UUID(GI_JOURNAL),
            evidenceLevel="PROVISIONAL",
        )
    )
    await session.flush()


async def test_a_tapped_district_lists_located_crafts_and_only_stored_stories(session: AsyncSession) -> None:
    await store_place(session)
    await place_bagru_by_state(session)
    answer_id = await stored_story(session)
    stored = await piece_ids(session, answer_id)
    found = await district_records(session, KACHCHH)
    assert found is not None and found.district.name == "Kachchh"
    slugs = {location.craft.slug for location in found.locations}
    assert AJRAKH.slug in slugs and BAGRU not in slugs
    assert [(block.id, block.kind) for block in found.blocks] == [
        ("land.b1", "region_story"),
        ("land.b2", "prose"),
    ]
    assert [str(block.reuse.piece_id) for block in found.blocks] == [stored["region_story"], stored["prose"]]
    assert found.blocks[0].river.main_riv == OUTLET
    assert found.blocks[1].sentences[0].id == "land.b2.1"
    assert {"DR_DISTRICT_SHAPES", "SOILGRIDS_2_0"} <= set(found.datasets) | {found.boundary.code}


async def test_a_stale_piece_is_not_shown_on_the_map(session: AsyncSession) -> None:
    await store_place(session)
    answer_id = await stored_story(session)
    await session.execute(
        update(PieceRow)
        .where(PieceRow.createdFromAnswerId == answer_id, PieceRow.kind == "prose")
        .values(staleSince=datetime.now(UTC))
    )
    found = await district_records(session, KACHCHH)
    assert found is not None and [block.kind for block in found.blocks] == ["region_story"]


async def test_a_district_story_quoting_a_closed_chunk_is_left_off_for_a_reader_who_may_not_read_it(
    session: AsyncSession,
) -> None:
    await store_place(session)
    await store_closed_sources(session)
    await quote_closed(session, WATER_CLAIMS[:1])
    await stored_story(session, acls=EVERY_CHUNK_ACLS)
    every = await district_records(session, KACHCHH, acls=EVERY_CHUNK_ACLS)
    shown = await district_records(session, KACHCHH, acls=OPEN_CHUNK_ACLS)
    assert every is not None and shown is not None
    assert [block.kind for block in every.blocks] == ["region_story", "prose"]
    assert CLOSED_QUOTE in blocks_text(every.blocks)
    assert CLOSED_QUOTE not in blocks_text(shown.blocks)
    assert len(shown.blocks) < len(every.blocks)


def blocks_text(blocks: Sequence[Any]) -> str:
    return json.dumps([block.model_dump(mode="json", by_alias=True) for block in blocks])


async def test_a_district_is_on_the_map_only_with_its_register_row_and_the_shapes_row(
    session: AsyncSession,
) -> None:
    await store_place(session)
    assert await district_records(session, 99999) is None
    await session.execute(delete(EnvDataset).where(EnvDataset.code == "DR_DISTRICT_SHAPES"))
    assert await district_records(session, KACHCHH) is None
