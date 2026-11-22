import gzip
import hashlib
import json
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.routes import rivers
from app.core.db import get_session
from app.core.errors import ExternalFailure, InvalidInput
from app.main import create_app
from app.models import User
from app.research.rivers import RIVER_BASIN_ROUTE
from app.services.naming import river_topology_key
from app.services.river_store import BasinFile
from app.services.river_topology import TopologyCache, TopologyFile, basin_topology

from ..contracts.golden import golden_json
from ..readers import sign_in_as

OUTLET = 41071234
TOPOLOGY = json.dumps(
    {
        "type": "Topology",
        "transform": {"scale": [1e-5, 1e-5], "translate": [69.0, 23.1]},
        "objects": {
            "reaches": {
                "type": "GeometryCollection",
                "geometries": [
                    {
                        "type": "LineString",
                        "id": OUTLET,
                        "arcs": [0],
                        "properties": {"nextDown": 0, "ordStra": 3},
                    }
                ],
            }
        },
        "arcs": [[[0, 0], [100, 200]]],
    },
    separators=(",", ":"),
).encode("utf-8")
SHA = hashlib.sha256(TOPOLOGY).hexdigest()
PATH = RIVER_BASIN_ROUTE.format(mainRiv=OUTLET)
KEY = f"media/rivers/v10/{OUTLET}/{SHA}/KalaVigyan_Dataset_HydroRIVERS-1-0_River-Topology_Basin-{OUTLET}.json"


class FakeBucket:
    def __init__(self, stored: dict[str, bytes], *, failing: bool = False) -> None:
        self.stored = stored
        self.failing = failing
        self.reads: list[str] = []

    async def get(self, key: str) -> bytes | None:
        self.reads.append(key)
        if self.failing:
            raise ExternalFailure("Could not read the media object (SlowDown)", kind="unavailable")
        return self.stored.get(key)


async def no_session() -> Any:
    yield None


@pytest.fixture
def basins(monkeypatch: pytest.MonkeyPatch) -> dict[int, BasinFile]:
    stored = {OUTLET: BasinFile(main_riv=OUTLET, edition="v10", sha256=SHA)}

    async def found(_session: Any, main_riv: int) -> BasinFile | None:
        return stored.get(main_riv)

    async def released(_session: Any) -> None:
        return None

    monkeypatch.setattr(rivers, "basin_file", found)
    monkeypatch.setattr(rivers, "release_connection", released)
    return stored


def reader_app(bucket: FakeBucket | None, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(rivers, "media_bucket", lambda: bucket)
    app = create_app()
    reader = User(id=uuid.UUID(int=7), name="Asha", email="asha@example.com", role="STUDENT")
    sign_in_as(app, lambda: reader)
    app.dependency_overrides[get_session] = no_session
    return TestClient(app)


IDENTITY = {"Accept-Encoding": "identity"}


def varied(response: Any) -> set[str]:
    return {name.strip() for name in response.headers["vary"].split(",")}


def test_the_basin_topology_is_served_with_its_hash_as_etag(basins, monkeypatch) -> None:
    bucket = FakeBucket({KEY: TOPOLOGY})
    client = reader_app(bucket, monkeypatch)
    response = client.get(PATH, headers=IDENTITY)
    assert response.status_code == 200
    assert response.content == TOPOLOGY
    assert "content-encoding" not in response.headers
    assert response.headers["content-type"] == "application/json"
    assert response.headers["etag"] == f'"{SHA}"'
    assert response.headers["cache-control"] == "private, no-cache"
    assert {"Authorization", "Accept-Encoding"} <= varied(response)
    again = client.get(PATH, headers=IDENTITY)
    assert again.content == TOPOLOGY
    assert bucket.reads == [KEY]


def test_a_reader_accepting_gzip_gets_the_compressed_file_under_its_own_etag(basins, monkeypatch) -> None:
    client = reader_app(FakeBucket({KEY: TOPOLOGY}), monkeypatch)
    response = client.get(PATH, headers={"Accept-Encoding": "gzip"})
    assert response.status_code == 200
    assert response.headers["content-encoding"] == "gzip"
    assert response.headers["etag"] == f'"{SHA}-gzip"'
    assert response.content == TOPOLOGY
    refused = client.get(PATH, headers={"Accept-Encoding": "gzip;q=0, identity"})
    assert "content-encoding" not in refused.headers and refused.headers["etag"] == f'"{SHA}"'


def test_a_matching_etag_answers_304_without_reading_the_bucket(basins, monkeypatch) -> None:
    bucket = FakeBucket({KEY: TOPOLOGY})
    client = reader_app(bucket, monkeypatch)
    response = client.get(PATH, headers={"If-None-Match": f'"{SHA}"', **IDENTITY})
    assert response.status_code == 304
    assert response.headers["etag"] == f'"{SHA}"'
    zipped = client.get(PATH, headers={"If-None-Match": f'"{SHA}-gzip"', "Accept-Encoding": "gzip"})
    assert zipped.status_code == 304 and {"Authorization", "Accept-Encoding"} <= varied(zipped)
    assert bucket.reads == []


def test_an_unknown_basin_is_not_found(basins, monkeypatch) -> None:
    response = reader_app(FakeBucket({KEY: TOPOLOGY}), monkeypatch).get("/api/rivers/41000001")
    assert (response.status_code, response.json()) == (404, {"detail": rivers.NO_RIVER_DETAIL})


@pytest.mark.parametrize("path", ["/api/rivers/0", "/api/rivers/100000000", "/api/rivers/ganga"])
def test_an_id_no_reach_can_have_is_refused(basins, monkeypatch, path: str) -> None:
    assert reader_app(FakeBucket({KEY: TOPOLOGY}), monkeypatch).get(path).status_code == 422


def test_a_stored_basin_without_its_file_is_not_found(basins, monkeypatch) -> None:
    response = reader_app(FakeBucket({}), monkeypatch).get(PATH)
    assert (response.status_code, response.json()) == (404, {"detail": rivers.NO_RIVER_DETAIL})


@pytest.mark.parametrize("bucket", [None, FakeBucket({}, failing=True)])
def test_an_unreadable_bucket_answers_unavailable(basins, monkeypatch, bucket) -> None:
    response = reader_app(bucket, monkeypatch).get(PATH)
    assert (response.status_code, response.json()) == (503, {"detail": rivers.UNAVAILABLE_DETAIL})


async def test_a_file_that_differs_from_the_load_is_not_served_or_kept() -> None:
    changed = TOPOLOGY + b" "
    bucket = FakeBucket({KEY: changed})
    cache = TopologyCache()
    found = await basin_topology(bucket, cache, BasinFile(main_riv=OUTLET, edition="v10", sha256=SHA))
    assert found is None
    assert cache.get(SHA) is None and cache.get(hashlib.sha256(changed).hexdigest()) is None


def test_a_river_whose_file_differs_from_the_load_is_not_found(basins, monkeypatch) -> None:
    response = reader_app(FakeBucket({KEY: TOPOLOGY + b" "}), monkeypatch).get(PATH)
    assert (response.status_code, response.json()) == (404, {"detail": rivers.NO_RIVER_DETAIL})


def held(sha256: str, body: bytes, zipped: bytes = b"z") -> TopologyFile:
    return TopologyFile(body=body, sha256=sha256, gzipped=zipped)


def test_the_cache_drops_the_least_recently_read_file_past_its_budget() -> None:
    cache = TopologyCache(max_bytes=10)
    cache.put(held("a", b"1234"))
    cache.put(held("b", b"5678"))
    assert cache.get("a") == held("a", b"1234")
    cache.put(held("c", b"90ab"))
    assert (cache.get("a"), cache.get("b"), cache.get("c")) == (held("a", b"1234"), None, held("c", b"90ab"))
    cache.put(held("d", b"x" * 10))
    assert cache.get("d") is None


async def test_a_stored_topology_is_kept_with_its_compressed_body() -> None:
    cache = TopologyCache()
    found = await basin_topology(FakeBucket({KEY: TOPOLOGY}), cache, BasinFile(OUTLET, "v10", SHA))
    assert found is not None and gzip.decompress(found.gzipped) == TOPOLOGY
    assert found.gzipped == gzip.compress(TOPOLOGY, 9, mtime=0)
    assert cache.get(SHA) == found


@pytest.mark.parametrize("row", golden_json("naming-golden.json")["riverTopologies"])
def test_the_topology_key_is_the_naming_golden_row(row: dict) -> None:
    assert river_topology_key(row["edition"], row["mainRiv"], row["sha256"]) == row["key"]
    assert row["key"].rsplit("/", 1)[1] == row["fileName"]


@pytest.mark.parametrize("sha256", ["", "abc", SHA.upper(), SHA[:-1] + "g"])
def test_a_topology_key_is_filed_under_a_content_digest_only(sha256: str) -> None:
    with pytest.raises(InvalidInput, match="SHA-256"):
        river_topology_key("v10", OUTLET, sha256)
