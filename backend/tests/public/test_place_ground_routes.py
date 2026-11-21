import uuid
from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.routes import place_ground as route
from app.core.db import get_session
from app.geo.place_ground import direct_measures, map_place_ground
from app.main import create_app
from app.research.why_here import WHY_HERE_KIND
from app.services.answering import NOT_FOUND_DETAIL
from app.services.monograph_generated_why_here import ground_hash

from ..contracts.golden import golden_json
from ..geo.ground_fixtures import GOLDEN_GROUND, ORIGIN, fixture_ground, fixture_layers
from .test_craft_monograph_route import DIGEST, PATH, served

CRAFT = SimpleNamespace(id=uuid.UUID("00000000-0000-4000-8000-0000000000c1"), slug="Ground-Fixture")
WHY = '<section class="kv-ch" id="why" data-ch="4"><p>w</p></section>'


def client(
    monkeypatch: pytest.MonkeyPatch, *, craft: Any = CRAFT, ground: Any = None, at: Any = None
) -> TestClient:
    async def resolve_craft(session: Any, slug: str) -> Any:
        return craft

    async def subject_ground(session: Any, craft_id: uuid.UUID) -> Any:
        return ground if craft_id == CRAFT.id else None

    async def map_ground_at(session: Any, point: tuple[float, float]) -> Any:
        return at if point == ORIGIN else None

    async def session() -> AsyncIterator[object]:
        yield object()

    monkeypatch.setattr(route.knowledge_view, "resolve_craft", resolve_craft)
    monkeypatch.setattr(route, "subject_ground", subject_ground)
    monkeypatch.setattr(route, "map_ground_at", map_ground_at)
    app = create_app()
    app.dependency_overrides[get_session] = session
    return TestClient(app)


def test_a_craft_s_ground_is_served_with_the_public_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    answer = client(monkeypatch, ground=fixture_ground()).get("/api/crafts/ground-fixture/ground")
    assert answer.status_code == 200
    assert answer.json() == golden_json(GOLDEN_GROUND)
    assert answer.headers["cache-control"] == "public, max-age=300"


def test_an_unknown_craft_and_a_craft_without_a_place_are_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    unknown = client(monkeypatch, craft=None).get("/api/crafts/nothing/ground")
    assert (unknown.status_code, unknown.json()["detail"]) == (404, NOT_FOUND_DETAIL)
    unplaced = client(monkeypatch).get("/api/crafts/ground-fixture/ground")
    assert (unplaced.status_code, unplaced.json()["detail"]) == (404, route.NO_PLACE_DETAIL)


def test_the_map_reads_the_ground_at_a_craft_place_and_nowhere_else(monkeypatch: pytest.MonkeyPatch) -> None:
    at = map_place_ground(ORIGIN, "Fixture district", direct_measures(fixture_layers()), ((), ()))
    http = client(monkeypatch, at=at)
    found = http.get("/api/map/ground", params={"longitude": ORIGIN[0], "latitude": ORIGIN[1]})
    assert found.status_code == 200
    assert found.json()["district"] == "Fixture district"
    assert found.json()["ground"] == golden_json(GOLDEN_GROUND)["places"][0]["ground"]
    elsewhere = http.get("/api/map/ground", params={"longitude": 78.0, "latitude": 21.0})
    assert (elsewhere.status_code, elsewhere.json()["detail"]) == (404, route.NOT_A_PLACE_DETAIL)


@pytest.mark.parametrize(("longitude", "latitude"), [(60.0, 20.0), (77.0, 40.0), (99.0, 20.0), (77.0, 4.0)])
def test_a_point_off_the_map_of_india_is_refused(
    monkeypatch: pytest.MonkeyPatch, longitude: float, latitude: float
) -> None:
    answer = client(monkeypatch).get("/api/map/ground", params={"longitude": longitude, "latitude": latitude})
    assert answer.status_code == 422


def test_a_stored_monograph_is_served_with_its_ground_and_tagged_by_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ground = fixture_ground()
    body = {
        "subjectSlug": "Kutch-Ajrakh",
        "shell": WHY,
        "specs": {},
        "content": {"components": [], "layout": []},
    }
    http, _ = served(monkeypatch, body=body, ground=ground)
    answer = http.get(PATH)
    assert answer.status_code == 200
    served_body = answer.json()
    assert [component["kind"] for component in served_body["content"]["components"]] == [WHY_HERE_KIND]
    assert 'kv-slot component="kutch-ajrakh/geography/why-here"' in served_body["shell"]
    assert answer.headers["etag"] == f'"v3-{ground_hash(DIGEST, ground)}"'
