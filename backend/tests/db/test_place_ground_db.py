import dataclasses
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import pytest
from geoalchemy2 import WKTElement
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_engine
from app.data.river_names import NamedRiver
from app.geo.ground_layers import Deposit
from app.geo.place_ground import direct_measures
from app.models import (
    AdminDistrict,
    AdminState,
    Claim,
    ClaimSource,
    Concept,
    Craft,
    CraftLocation,
    CuratedCraft,
    EnvDataset,
    Material,
    Process,
    ProcessStage,
    RiverBasin,
    Source,
    StageMaterial,
    WikidataPoint,
)
from app.research.datasets import DatasetRef
from app.research.rivers import HYDRORIVERS_DATASET_CODE
from app.services import knowledge_view, place_ground as service

from ..geo.ground_fixtures import fixture_layers

pytestmark = pytest.mark.db

STATE, DISTRICT = 990, 990001
SPOT = (60.5, 10.5)
ELSEWHERE = (61.2, 11.2)
CRAFT = uuid.UUID("9e0d0000-0000-4000-8000-000000000001")
OPEN_SOURCE = uuid.UUID("9e0d0000-0000-4000-8000-000000000002")
HIDDEN_SOURCE = uuid.UUID("9e0d0000-0000-4000-8000-000000000003")
PROCESS = uuid.UUID("9e0d0000-0000-4000-8000-000000000004")
STAGE = uuid.UUID("9e0d0000-0000-4000-8000-000000000005")
NAMED_CLAIM = uuid.UUID("9e0d0000-0000-4000-8000-000000000021")
WITHDRAWN_CLAIM = uuid.UUID("9e0d0000-0000-4000-8000-000000000022")
NAMED_CONCEPT = uuid.UUID("9e0d0000-0000-4000-8000-000000000023")
NOW = datetime(2026, 11, 23, tzinfo=UTC)
ABROAD, FAR_AWAY, WITHDRAWN = "Q9900001", "Q9900002", "Q9900003"
ABROAD_AT = (61.4, 12.0)
OSM_NAMES = "OSM_RIVER_NAMES"
OSM_CREDIT = "© OpenStreetMap contributors"
NAMED_RIVER = NamedRiver(
    name="Test River",
    dataset_code=OSM_NAMES,
    refs=("way/1",),
    main_riv=91000004,
    reach_ids=(91000001, 91000002, 91000004),
    district_lgds=(DISTRICT,),
)
MATERIALS = (
    (uuid.UUID("9e0d0000-0000-4000-8000-000000000011"), "Ground test iron filings", "METAL", "INPUT"),
    (uuid.UUID("9e0d0000-0000-4000-8000-000000000012"), "Ground test river clay", "CLAY", "INPUT"),
    (uuid.UUID("9e0d0000-0000-4000-8000-000000000013"), "Ground test iron hammer", "METAL", "TOOL"),
)


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async with get_engine().connect() as connection:
        transaction = await connection.begin()
        try:
            session = AsyncSession(bind=connection, expire_on_commit=False, autoflush=False)
            yield session
            await session.close()
        finally:
            await transaction.rollback()


@pytest.fixture(autouse=True)
def iron_nearby(monkeypatch: pytest.MonkeyPatch) -> None:
    iron = Deposit(7, "Near iron", SPOT[0], SPOT[1] + 0.1, 0, "Occurrence", ("Iron",))
    layers = dataclasses.replace(fixture_layers(), deposits=(iron,))
    monkeypatch.setattr(service, "ground_measures", lambda: direct_measures(layers))


def point(longitude: float, latitude: float) -> WKTElement:
    return WKTElement(f"POINT({longitude} {latitude})", srid=4326)


def district_square() -> WKTElement:
    west, south, east, north = SPOT[0] - 0.5, SPOT[1] - 0.5, SPOT[0] + 0.5, SPOT[1] + 0.5
    ring = f"{west} {south}, {east} {south}, {east} {north}, {west} {north}, {west} {south}"
    return WKTElement(f"MULTIPOLYGON((({ring})))", srid=4326)


def located(role: str, source: uuid.UUID, at: tuple[float, float]) -> CraftLocation:
    return CraftLocation(
        craftId=CRAFT,
        precision="POINT",
        geom=point(*at),
        placeLabel="Test forge village",
        sourceId=source,
        role=role,
        evidenceLevel="PROVISIONAL",
    )


async def seed(session: AsyncSession) -> Craft:
    session.add(AdminState(lgd=STATE, name="Ground Test State"))
    await session.flush()
    session.add(
        AdminDistrict(lgd=DISTRICT, stateLgd=STATE, name="Ground Test District", geom=district_square())
    )
    session.add_all(
        [
            Source(id=OPEN_SOURCE, kind="PAPER", title="Where the forge is", url="https://example.org/forge"),
            Source(id=HIDDEN_SOURCE, kind="PAPER", title="A field note", sensitivity="RESTRICTED"),
        ]
    )
    craft = Craft(id=CRAFT, slug="Ground-Test-Iron-Craft", name="Ground test iron craft")
    session.add(craft)
    await session.flush()
    session.add_all(
        [
            located("PRACTISED", OPEN_SOURCE, SPOT),
            located("ORIGIN", OPEN_SOURCE, SPOT),
            located("PRACTISED", HIDDEN_SOURCE, ELSEWHERE),
        ]
    )
    await _materials(session)
    return craft


async def _materials(session: AsyncSession) -> None:
    session.add(Process(id=PROCESS, craftId=CRAFT, name="Forging"))
    await session.flush()
    session.add(ProcessStage(id=STAGE, processId=PROCESS, ordinal=1, name="Heat and hammer"))
    session.add_all(
        Material(id=key, name=name, nameNorm=name.lower(), kind=kind) for key, name, kind, _ in MATERIALS
    )
    await session.flush()
    session.add_all(StageMaterial(stageId=STAGE, materialId=key, role=role) for key, _, _, role in MATERIALS)
    await session.flush()


async def test_a_craft_s_open_places_are_measured_once_each_with_their_district_and_materials(
    session: AsyncSession,
) -> None:
    craft = await seed(session)
    ground = await service.craft_ground_of(session, craft)
    assert ground is not None
    [place] = ground.places
    assert (place.name, place.roles, place.precision) == (
        "Test forge village",
        ["PRACTISED", "ORIGIN"],
        "POINT",
    )
    assert (place.district, place.state, place.longitude, place.latitude) == (
        "Ground Test District",
        "Ground Test State",
        60.5,
        10.5,
    )
    assert [(m.material, m.count, m.nearest_km) for m in place.materials] == [
        ("Ground test iron filings", 1, 11.1)
    ]
    assert ground.soil_materials == ["Ground test river clay"]
    assert [(d.dep_id, d.matched) for d in ground.deposits] == [(7, True)]
    assert [source.id for source in ground.sources] == [str(OPEN_SOURCE)]


async def test_the_map_reads_the_ground_only_at_a_craft_place(session: AsyncSession) -> None:
    await seed(session)
    found = await service.map_ground_at(session, SPOT)
    assert found is not None
    assert (found.district, found.ground.deposit_total) == ("Ground Test District", 1)
    assert await service.map_ground_at(session, (SPOT[0] + 0.3, SPOT[1])) is None


async def test_a_craft_without_an_open_place_has_no_ground(session: AsyncSession) -> None:
    craft = await seed(session)
    await session.execute(delete(CraftLocation).where(CraftLocation.sourceId == OPEN_SOURCE))
    assert await service.craft_ground_of(session, craft) is None
    assert await service.subject_ground(session, CRAFT) is None


def dossier_place(
    key: str, name: str, kind: str, *, role: str, country: str, wikidata: str | None
) -> dict[str, Any]:
    claim = WITHDRAWN_CLAIM if wikidata == WITHDRAWN else NAMED_CLAIM
    at_home = country == "India"
    return {
        "key": key,
        "name": name,
        "kind": kind,
        "role": role,
        "district": "Ground Test District" if at_home else None,
        "district_lgd": DISTRICT if at_home else None,
        "state": None,
        "state_lgd": None,
        "country": country,
        "wikidata_id": wikidata,
        "location_id": None,
        "concept_id": str(NAMED_CONCEPT),
        "claim_ids": [str(claim)],
    }


def dossier() -> CuratedCraft:
    places = [
        dossier_place("L01", "Abroad region", "REGION", role="ORIGIN", country="Pakistan", wikidata=ABROAD),
        dossier_place(
            "L02", "Abroad region", "REGION", role="PRACTISED", country="Pakistan", wikidata=ABROAD
        ),
        dossier_place(
            "L03", "Far market", "TOWN", role="MARKET", country="United Kingdom", wikidata=FAR_AWAY
        ),
        dossier_place("L04", "Withdrawn town", "TOWN", role="ORIGIN", country="Pakistan", wikidata=WITHDRAWN),
        dossier_place("L05", "Test River", "RIVER", role="MATERIAL_SOURCE", country="India", wikidata=None),
    ]
    empty: dict[str, Any] = {key: [] for key in ("searched", "conflicts", "open_questions", "communities")}
    empty |= {
        key: []
        for key in ("stages", "materials", "tools", "reactions", "glossary", "pictures", "environment")
    }
    page = {
        "craft_slug": "Ground-Test-Iron-Craft",
        "version": 1,
        "curated_at": NOW.isoformat(),
        "coverage": "THIN",
    }
    page |= {"process_id": None, "craft_concepts": {}, "overview": {}, "places": places, **empty}
    return CuratedCraft(craftId=CRAFT, version=1, curatedAt=NOW, coverage="THIN", digest="c" * 64, page=page)


def dataset_row(code: str, title: str, attribution: str) -> EnvDataset:
    return EnvDataset(
        id=uuid.uuid4(),
        code=code,
        title=title,
        edition="1",
        period="static",
        nativeResolution="vector",
        licence="Open",
        attribution=attribution,
    )


async def seed_beyond(session: AsyncSession) -> Craft:
    craft = await seed(session)
    await session.execute(delete(RiverBasin))
    await session.execute(delete(EnvDataset))
    session.add(dossier())
    points = {ABROAD: ABROAD_AT, FAR_AWAY: (-4.25, 55.86), WITHDRAWN: (61.0, 11.5)}
    session.add_all(
        WikidataPoint(wikidataId=k, longitude=x, latitude=y, keptAt=NOW) for k, (x, y) in points.items()
    )
    session.add(dataset_row(HYDRORIVERS_DATASET_CODE, "HydroRIVERS", "WWF"))
    session.add(
        Concept(id=NAMED_CONCEPT, craftId=CRAFT, type="ENVIRONMENTAL_CONDITION", name="Abroad region")
    )
    await session.flush()
    for claim_id, status in ((NAMED_CLAIM, "APPROVED"), (WITHDRAWN_CLAIM, "RETRACTED")):
        session.add(
            Claim(
                id=claim_id,
                subjectType="CONCEPT",
                subjectId=NAMED_CONCEPT,
                predicate="states",
                text="The craft came from the region abroad and takes water from the river.",
                evidenceLevel="PROVISIONAL",
                origin="IMPORT",
                field="GEOGRAPHY",
                status=status,
            )
        )
        await session.flush()
        session.add(ClaimSource(claimId=claim_id, sourceId=OPEN_SOURCE, quoteCheck="NA", relation="DIRECT"))
    await session.flush()
    return craft


def names_row() -> DatasetRef:
    return DatasetRef(
        code=OSM_NAMES,
        title="Names",
        publisher=None,
        edition="1",
        period="static",
        native_resolution="vector",
        licence="ODbL 1.0",
        licence_url=None,
        attribution=OSM_CREDIT,
        citation=None,
        url=None,
    )


async def test_a_place_abroad_within_reach_is_pinned_and_a_named_river_is_cited_from_both_its_rows(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    named = {("Test River", DISTRICT): NAMED_RIVER}
    monkeypatch.setattr(service, "place_river", lambda name, lgd: named.get((name, lgd)))
    monkeypatch.setattr(service, "name_dataset", {OSM_NAMES: names_row()}.get)
    craft = await seed_beyond(session)
    shown, _ = await knowledge_view.claims_by_id(session, [NAMED_CLAIM, WITHDRAWN_CLAIM])
    assert list(shown) == [NAMED_CLAIM]
    ground = await service.craft_ground_of(session, craft)
    assert ground is not None
    assert [(p.key, p.name, p.roles, p.country, p.longitude, p.latitude) for p in ground.abroad] == [
        ("abroad-Q9900001", "Abroad region", ["PRACTISED", "ORIGIN"], "Pakistan", 61.4, 12.0)
    ]
    assert ground.frame.holds(*ABROAD_AT)
    [river] = ground.rivers
    assert (river.key, river.name, river.main_riv, river.reach_ids) == (
        "river-91000004-91000001-91000004",
        "Test River",
        91000004,
        [91000001, 91000002, 91000004],
    )
    assert (river.hydrorivers.code, river.names.code, river.names.attribution) == (
        HYDRORIVERS_DATASET_CODE,
        OSM_NAMES,
        OSM_CREDIT,
    )


async def test_a_river_without_its_name_s_dataset_row_is_not_drawn(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(service, "place_river", lambda name, lgd: NAMED_RIVER)
    monkeypatch.setattr(service, "name_dataset", {}.get)
    craft = await seed_beyond(session)
    ground = await service.craft_ground_of(session, craft)
    assert ground is not None
    assert (len(ground.abroad), ground.rivers) == (1, [])
