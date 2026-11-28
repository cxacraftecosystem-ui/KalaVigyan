import json
import uuid
from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_engine, session_scope, sessionmaker
from app.core.errors import InvalidInput
from app.data.dataset_registry import registry_rows
from app.data.kind_fixture_files import KIND_FIXTURES_DIR
from app.models import EnvDataset, PlaceLookup, WikidataPoint
from app.research.component_proposals import ComponentProposalDraft, ProposedSubject
from app.research.component_specs import checked_spec
from app.research.component_specs_general_delivery import DeliveredUnit
from app.research.component_specs_timeline_map import DeclaredTimelineMapSpec
from app.services import timeline_maps
from app.services.component_proposals_spec import checked_delivery
from app.services.entity_points import entity_points
from app.services.place_lookups import item_key
from app.services.source_lookup_models import EntityLookup, EntityRecord
from app.services.timeline_map_places import NOT_IN_REGISTER, NOT_LOOKED_UP, OUTSIDE_DISTRICTS, found_places
from app.services.timeline_maps import NO_BOUNDARY, NO_LAYER_RECORD, map_credits, placed_spec
from app.sources.reference.wikidata_places import PlaceCandidate, PlacePoint

pytestmark = pytest.mark.db

CREDITED = ("DR_DISTRICT_SHAPES", "ETOPO1_ICE", "NATURAL_EARTH_10M_PHYSICAL")
KEPT_AT = datetime(2026, 11, 24, tzinfo=UTC)
HEAD = {"title": "u0001"}


class AskedFinder:
    def __init__(self, points: dict[str, PlacePoint]) -> None:
        self.points = points
        self.asked: list[list[str]] = []

    async def place_candidates(self, name: str) -> list[PlaceCandidate]:
        return []

    async def place_points(self, item_ids: Sequence[str]) -> dict[str, PlacePoint]:
        self.asked.append(list(item_ids))
        return {item: self.points[item] for item in item_ids if item in self.points}


def _dataset(row: dict[str, Any]) -> EnvDataset:
    return EnvDataset(
        id=uuid.uuid4(),
        code=row["code"],
        title=row["title"],
        publisher=row.get("publisher"),
        edition=row.get("edition"),
        period=row.get("period"),
        nativeResolution=row.get("nativeResolution"),
        crs=row.get("crs"),
        licence=row.get("licence"),
        licenceUrl=row.get("licenceUrl"),
        attribution=row.get("attribution"),
        redistributable=bool(row.get("redistributable")),
        citation=row.get("citation"),
        url=row.get("url"),
        version=row.get("version"),
        doi=row.get("doi"),
        landingUrl=row.get("landingUrl"),
    )


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async with get_engine().connect() as connection:
        transaction = await connection.begin()
        try:
            session = AsyncSession(bind=connection, expire_on_commit=False, autoflush=False)
            await session.execute(delete(EnvDataset))
            session.add_all(_dataset(row) for row in registry_rows() if row["code"] in CREDITED)
            await session.flush()
            yield session
            await session.close()
        finally:
            await transaction.rollback()


def bidriware() -> dict[str, Any]:
    return json.loads((KIND_FIXTURES_DIR / "timeline_map.json").read_text(encoding="utf-8"))


def one_place(place: dict[str, Any]) -> DeclaredTimelineMapSpec:
    spec = {"head": HEAD, "places": [{"name": "u0002", **place}], "undated": [{"place": 0, "text": "u0003"}]}
    checked = checked_spec("timeline_map", spec)
    assert isinstance(checked, DeclaredTimelineMapSpec)
    return checked


async def test_the_bidriware_map_is_placed_at_the_register_s_district_points_and_credited(
    session: AsyncSession,
) -> None:
    fixture = bidriware()
    placed = await placed_spec(session, checked_spec("timeline_map", fixture["spec"]))
    assert placed.problems == []
    assert placed.spec is not None
    found = [place["found"] for place in placed.spec["places"]]
    assert found[0] == {"latitude": 17.766, "longitude": 77.144, "districtLgd": 529}
    assert found[1] == {"latitude": 17.379, "longitude": 78.453, "districtLgd": 507}
    assert found == fixture["placed"]["places"]
    assert [dataset["code"] for dataset in placed.spec["datasets"]] == list(CREDITED)
    assert placed.spec["places"][0]["home"] is True


async def test_a_wikidata_item_is_placed_from_the_site_s_points_then_its_lookups_then_the_finder(
    session: AsyncSession,
) -> None:
    session.add(WikidataPoint(wikidataId="Q461922", latitude=17.9104, longitude=77.5199, keptAt=KEPT_AT))
    session.add(PlaceLookup(lookupKey=item_key("Q1361"), answer={"latitude": 17.36, "longitude": 78.47}))
    await session.flush()
    finder = AskedFinder({"Q47916": PlacePoint(26.85, 80.95)})
    kept = await found_places(session, one_place({"wikidata": "Q461922"}), finder=finder)
    looked = await found_places(session, one_place({"wikidata": "Q1361"}), finder=finder)
    asked = await found_places(session, one_place({"wikidata": "Q47916"}), finder=finder)
    assert (kept.places[0].latitude, kept.places[0].longitude, kept.places[0].wikidata_id) == (
        17.9104,
        77.5199,
        "Q461922",
    )
    assert (looked.places[0].latitude, looked.places[0].longitude) == (17.36, 78.47)
    assert (asked.places[0].latitude, asked.places[0].longitude) == (26.85, 80.95)
    assert finder.asked == [["Q47916"]]


async def test_a_place_the_site_cannot_resolve_is_refused_by_name(session: AsyncSession) -> None:
    unknown = await found_places(session, one_place({"wikidata": "Q999999999"}))
    assert unknown.places == {}
    assert unknown.problems == [NOT_LOOKED_UP.format(at=0, item="Q999999999")]
    no_district = await found_places(session, one_place({"district": 99999}))
    assert no_district.problems == [NOT_IN_REGISTER.format(at=0, lgd=99999)]
    refused = await placed_spec(session, one_place({"wikidata": "Q999999999"}))
    assert refused.spec is None and refused.problems == unknown.problems


async def test_a_cited_coordinate_is_placed_as_given_and_in_the_district_that_holds_it(
    session: AsyncSession,
) -> None:
    jaipur = await found_places(session, one_place({"longitude": 75.589, "latitude": 26.817, "at": "u0004"}))
    assert jaipur.problems == []
    assert jaipur.places[0].model_dump(mode="json") == {
        "latitude": 26.817,
        "longitude": 75.589,
        "districtLgd": 102,
    }
    at_sea = one_place({"longitude": 65.0, "latitude": 15.0, "at": "u0004", "home": True})
    refused = await found_places(session, at_sea)
    assert refused.problems == [OUTSIDE_DISTRICTS.format(at=0)]
    away = await found_places(session, one_place({"longitude": 65.0, "latitude": 15.0, "at": "u0004"}))
    assert away.places[0].district_lgd is None


async def test_only_layers_the_site_holds_are_drawn_and_every_one_is_credited(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    await session.execute(delete(EnvDataset).where(EnvDataset.code.in_(CREDITED[1:])))
    physical = await map_credits(session, ["relief", "rivers", "minerals"])
    assert physical.problems == []
    assert [dataset.code for dataset in physical.datasets] == [*CREDITED, "USGS_MRDS"]
    relief = physical.datasets[1]
    assert (relief.version, relief.doi, relief.licence) == (
        "1",
        "10.7289/V5C8276M",
        "Public domain (U.S. Government work)",
    )
    assert relief.read_on is not None and relief.sha256 is not None
    monkeypatch.setattr(timeline_maps, "physical_records", lambda name: ())
    unrecorded = await map_credits(session, ["relief"])
    assert unrecorded.problems == [NO_LAYER_RECORD.format(name="relief")]
    assert [dataset.code for dataset in unrecorded.datasets] == ["DR_DISTRICT_SHAPES"]
    monkeypatch.undo()
    unheld = await map_credits(session, ["annual-precipitation"])
    assert (
        len(unheld.problems) == 1
        and "the site holds no layer named 'annual-precipitation'" in unheld.problems[0]
    )
    bare = await map_credits(session, [])
    assert [dataset.code for dataset in bare.datasets] == ["DR_DISTRICT_SHAPES"]
    await session.execute(delete(EnvDataset).where(EnvDataset.code == "DR_DISTRICT_SHAPES"))
    assert (await map_credits(session, [])).problems == [NO_BOUNDARY]


async def test_an_item_looked_up_over_mcp_keeps_its_point_so_a_map_can_name_it() -> None:
    item = "Q900002"
    record = EntityRecord(
        qid=item,
        label="A town",
        url=f"https://www.wikidata.org/wiki/{item}",
        open_licence=True,
        grade="B",
        lines=[],
    )
    finder = AskedFinder({item: PlacePoint(12.5, 76.5)})
    try:
        looked = await entity_points(EntityLookup(query=item, entities=[record]), finder, sessionmaker())
        assert (looked.entities[0].latitude, looked.entities[0].longitude) == (12.5, 76.5)
        async with session_scope() as stored:
            placed = await found_places(stored, one_place({"wikidata": item}))
        assert (placed.places[0].latitude, placed.places[0].longitude) == (12.5, 76.5)
    finally:
        async with session_scope() as stored:
            await stored.execute(delete(PlaceLookup).where(PlaceLookup.lookupKey == item_key(item)))


def _draft(spec: dict[str, Any]) -> tuple[ComponentProposalDraft, dict[uuid.UUID, list[str]]]:
    fixture = bidriware()
    ids = {key: uuid.uuid5(uuid.NAMESPACE_URL, f"{fixture['craft']}/{key}") for key in fixture["facts"]}
    units = {
        ref: DeliveredUnit(text=unit["text"], claim_ids=[ids[claim] for claim in unit["claims"]])
        for ref, unit in fixture["units"].items()
    }
    known = {
        ids[key]: [fact["text"], *(quote["quote"] for quote in fact["quotes"])]
        for key, fact in fixture["facts"].items()
    }
    draft = ComponentProposalDraft(
        label=fixture["label"],
        title=fixture["title"],
        description=fixture["description"],
        kind="timeline_map",
        field="HISTORY",
        craft_slug=fixture["craft"],
        subjects=[ProposedSubject(kind="CRAFT", key=fixture["craft"])],
        spec=spec,
        units=units,
    )
    return draft, known


async def test_a_delivered_timeline_map_is_checked_and_stored_with_its_placement(
    session: AsyncSession,
) -> None:
    fixture = bidriware()
    draft, known = _draft(fixture["spec"])
    checked = await checked_delivery(session, draft, known=known)
    assert [place["found"] for place in checked.spec["places"]] == fixture["placed"]["places"]
    assert [dataset["code"] for dataset in checked.spec["datasets"]] == list(CREDITED)
    assert checked.spec["boundaryCaption"] == fixture["placed"]["boundaryCaption"]
    unknown = {
        **fixture["spec"],
        "places": [{**fixture["spec"]["places"][0]}, *fixture["spec"]["places"][1:]],
    }
    unknown["places"][1] = {"name": "u0004", "wikidata": "Q999999999"}
    draft, known = _draft(unknown)
    with pytest.raises(InvalidInput, match="place 1 names Q999999999, which the site holds no point for"):
        await checked_delivery(session, draft, known=known)
