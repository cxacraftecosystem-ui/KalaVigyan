import json
import re
import uuid
from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Any

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_engine
from app.models import DistrictEnvValue, EnvDataset, Term
from app.research.blocks_place import DistrictRef
from app.research.planning import PlanRequest
from app.research.sections import SectionSpec
from app.research.structured import StructuredReply
from app.services import knowledge_view
from app.services.answer_events import cited_claims
from app.services.builder_interface import BuildAsk, BuilderTools
from app.services.claim_seed import seed_id
from app.services.season_supply_builders import SeasonsBuilder, SupplyMapBuilder
from app.sources.reference.wikidata_places import PlaceCandidate, PlacePoint

from ..geo.test_rainfall import KACHCHH, KACHCHH_MM
from .test_knowledge_pieces_db import AJRAKH, prose_of
from .test_place_db import locate_in_kachchh

pytestmark = pytest.mark.db

HUMIDITY = seed_id("claim", "seed-bb7d49316e331a60841f")
OILED_BLOCKS = seed_id("claim", "seed-56bfce3b2f648b7e6a49")
INDIGO = seed_id("claim", "seed-0811cee9d456bc5ca7a1")
BLOCK_MAKERS = seed_id("claim", "seed-a29075bbe3b9adbc4f53")
INDIGO_MATERIAL = uuid.UUID("e3302885-722e-57cf-ad15-6f0c41b1a678")
CHIRPS = "CHIRPS_3_0"
PERIOD = "2016-2025"
MATERIAL_BLOCK = re.compile(r'<untrusted_source ref="(m\d+)" label="material">\nMaterial: ([^\n]+)')
STATEMENT_BLOCK = re.compile(r'<untrusted_source ref="(c\d+)" label="statement">\n([^\n]+)')


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async with get_engine().connect() as connection:
        transaction = await connection.begin()
        try:
            session = AsyncSession(bind=connection, expire_on_commit=False, autoflush=False)
            await session.execute(delete(EnvDataset).where(EnvDataset.code == CHIRPS))
            yield session
            await session.close()
        finally:
            await transaction.rollback()


class IndigoModel:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def __call__(self, *, system: str, user: str, schema: Mapping[str, Any]) -> StructuredReply:
        self.calls.append(user)
        materials = {name: ref for ref, name in MATERIAL_BLOCK.findall(user)}
        statements = {text: ref for ref, text in STATEMENT_BLOCK.findall(user)}
        indigo = next(ref for name, ref in materials.items() if name.casefold().startswith("indigo"))
        came = next(ref for text, ref in statements.items() if text.startswith("Indigo came from"))
        carved = next(ref for text, ref in statements.items() if text.startswith("Blocks are carved"))
        links = [
            {"statement": came, "material": indigo, "materialWords": "", "origin": "Shikarpur"},
            {"statement": came, "material": indigo, "materialWords": "", "origin": "Dhamadka"},
            {"statement": carved, "material": "none", "materialWords": "Blocks", "origin": "Pethapur"},
        ]
        return StructuredReply(text=json.dumps({"links": links}), degraded=False)


class NoPlaces:
    async def place_candidates(self, name: str) -> list[PlaceCandidate]:
        return []

    async def place_points(self, item_ids: Sequence[str]) -> dict[str, PlacePoint]:
        return {}


def tools(session: AsyncSession, model: Any = None) -> BuilderTools:
    def sessions() -> AsyncSession:
        return AsyncSession(bind=session.bind, expire_on_commit=False, autoflush=False)

    return BuilderTools(sessions=sessions, live=None, plan_model=model, compose_model=None)


async def ask_for(session: AsyncSession, claim_ids: Sequence[uuid.UUID], discipline: str) -> BuildAsk:
    prose = await prose_of(session, claim_ids)
    views, sources = await knowledge_view.claims_by_id(session, claim_ids)
    request = PlanRequest(
        question="When and from where does Ajrakh get its colours?", mode="HYBRID", craft=AJRAKH
    )
    spec = SectionSpec(id="s3", discipline=discipline, title="Climate", order=3)
    return BuildAsk(uuid.uuid4(), spec, request, (prose,), cited_claims(list(views.values()), sources))


async def store_rainfall(session: AsyncSession, millimetres: Sequence[float]) -> None:
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
            variable="monthly_precipitation",
            depthOrPeriod=f"{PERIOD}-{month:02d}",
            stat="NORMAL",
            value=value,
            unit="mm/month",
            resolution="0.05 degree",
        )
        for month, value in enumerate(millimetres, start=1)
    )
    await session.flush()


async def test_seasons_read_subjects_and_kachchh_rainfall_from_the_stored_rows(session: AsyncSession) -> None:
    await locate_in_kachchh(session)
    await store_rainfall(session, KACHCHH_MM)
    ask = await ask_for(session, [HUMIDITY, OILED_BLOCKS], "CLIMATE")
    built = await SeasonsBuilder(tools(session)).build(ask)
    (block,) = built.blocks
    rows = [(row.label, row.stage_id, row.season, row.months) for row in block.rows]
    assert rows == [("Monsoon humidity", None, "MONSOON", [])]
    assert [row.sentence.citations[0].claim_id for row in block.rows] == [str(HUMIDITY)]
    assert (block.rainfall.district, block.rainfall.period, block.rainfall.millimetres) == (
        DistrictRef(district_lgd=KACHCHH, name="Kachchh", state_name="Gujarat", other_names=["Kutch"]),
        PERIOD,
        KACHCHH_MM,
    )
    assert [(row.code, row.period, row.native_resolution) for row in block.datasets] == [
        (CHIRPS, PERIOD, "0.05 degree")
    ]


async def test_eleven_stored_months_leave_the_seasons_without_rainfall(session: AsyncSession) -> None:
    await locate_in_kachchh(session)
    await store_rainfall(session, KACHCHH_MM[:11])
    ask = await ask_for(session, [HUMIDITY], "CLIMATE")
    (block,) = (await SeasonsBuilder(tools(session)).build(ask)).blocks
    assert (block.rainfall, block.datasets) == (None, [])


async def test_supply_links_name_the_stored_indigo_and_list_unplaced_origins(session: AsyncSession) -> None:
    model = IndigoModel()
    ask = await ask_for(session, [INDIGO, BLOCK_MAKERS], "MATERIALS")
    builder = SupplyMapBuilder(tools(session, model), places=_no_places)
    (block,) = (await builder.build(ask)).blocks
    shown = [(link.material_id, link.origin, link.latitude) for link in block.links]
    assert shown == [
        (INDIGO_MATERIAL, "Shikarpur", None),
        (INDIGO_MATERIAL, "Dhamadka", None),
        (None, "Pethapur", None),
    ]
    indigo = block.links[0]
    assert indigo.material == await session.scalar(select(Term.label).where(Term.key == indigo.term_key))
    assert (block.links[2].material, block.links[2].term_key) == ("Blocks", None)
    assert [link.sentence.citations[0].claim_id for link in block.links] == [
        str(INDIGO),
        str(INDIGO),
        str(BLOCK_MAKERS),
    ]


async def _no_places() -> NoPlaces:
    return NoPlaces()
