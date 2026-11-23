import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.public_deps import THROTTLED_DETAIL
from app.core import rate_limit
from app.core.db import get_session
from app.core.deps import SIGN_IN_DETAIL
from app.core.http_cache import PRIVATE_NO_CACHE, PUBLIC_READ_CACHE
from app.core.rate_limit import PUBLIC_READS_PER_WINDOW
from app.main import create_app
from app.models import User

from ..readers import sign_in_as
from .stored_reads import AJRAKH, BAGRU, OUTLET, RECORDING, Asked, stored_reads

SUMMARY = "/api/public/summary"
PUBLIC_READS = (
    "/api/crafts/catalogue",
    f"/api/crafts/{AJRAKH}/page",
    f"/api/crafts/{AJRAKH}/region",
    f"/api/crafts/{AJRAKH}/shared-science",
    f"/api/shared-science/alum?craft={AJRAKH}",
    f"/api/shared-science/alum/crafts?craft={AJRAKH}&offset=2",
    f"/api/compare?crafts={AJRAKH}&crafts={BAGRU}",
    "/api/map/crafts",
    "/api/map/layers",
    "/api/map/layers/soil-ph-0-5cm",
    "/api/map/districts/449",
    f"/api/rivers/{OUTLET}",
    "/api/molecules/6293/conformer",
    "/api/terms/kut",
    f"/api/crafts/{AJRAKH}/field-voices",
    f"/api/field-voices/recordings/{RECORDING}",
    SUMMARY,
)
ASSET_READS = ("/api/map/layers/soil-ph-0-5cm", f"/api/rivers/{OUTLET}", "/api/molecules/6293/conformer")
PAGE_VIEW_READS = (
    f"/api/crafts/{AJRAKH}/page",
    f"/api/crafts/{AJRAKH}/region",
    f"/api/crafts/{AJRAKH}/shared-science",
    "/api/map/layers",
    f"/api/crafts/{AJRAKH}/field-voices",
    *(["/api/terms/kut"] * 5),
)
CLAIM_READS = {
    f"/api/crafts/{AJRAKH}/page": "craft_page_records",
    f"/api/crafts/{AJRAKH}/shared-science": "craft_shared_science",
    f"/api/shared-science/alum?craft={AJRAKH}": "shared_concept_of",
    f"/api/shared-science/alum/crafts?craft={AJRAKH}&offset=2": "shared_concept_crafts",
    f"/api/compare?crafts={AJRAKH}&crafts={BAGRU}": "craft_comparison",
    "/api/map/districts/449": "district_records",
    "/api/terms/kut": "term_lookup",
}
READER_KEYS = ("email", "userId", "askedBy", "createdById", "ipHash", "passwordHash", "accessToken")
SUMMARY_CACHE = "public, max-age=86400"
ROUTE_LIMIT = 5
MOMENT = datetime(2026, 11, 22, 10, 5, tzinfo=UTC)
STUDENT = User(id=uuid.UUID(int=7), name="Asha", email="asha@example.com", role="STUDENT")
RESEARCHER = User(id=uuid.UUID(int=8), name="Ravi", email="ravi@example.com", role="RESEARCHER")


async def no_session() -> Any:
    yield None


def _keys(body: Any) -> set[str]:
    if isinstance(body, dict):
        return set(body) | {key for value in body.values() for key in _keys(value)}
    if isinstance(body, list):
        return {key for value in body for key in _keys(value)}
    return set()


@pytest.fixture
def stored(monkeypatch: pytest.MonkeyPatch) -> Asked:
    asked = Asked()
    for module, names in stored_reads(asked).items():
        for name, value in names.items():
            monkeypatch.setattr(module, name, value)
    return asked


def reader_client(reader: User | None) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_session] = no_session
    if reader is not None:
        sign_in_as(app, lambda: reader)
    return TestClient(app)


def shown(response: httpx.Response) -> Any:
    return (
        response.json() if response.headers["content-type"].startswith("application/json") else response.text
    )


@pytest.mark.usefixtures("stored")
@pytest.mark.parametrize("path", PUBLIC_READS)
def test_an_anonymous_reader_gets_exactly_what_a_student_gets(path: str) -> None:
    anonymous = reader_client(None).get(path)
    student = reader_client(STUDENT).get(path)
    assert (anonymous.status_code, student.status_code) == (200, 200), path
    assert shown(anonymous) == shown(student)
    assert not set(READER_KEYS) & _keys(shown(anonymous))


@pytest.mark.usefixtures("stored")
@pytest.mark.parametrize("path", PUBLIC_READS)
def test_anonymous_reads_are_public_short_lived_and_revalidated(path: str) -> None:
    client = reader_client(None)
    first = client.get(path)
    assert first.headers["cache-control"] == (SUMMARY_CACHE if path == SUMMARY else PUBLIC_READ_CACHE)
    if path != SUMMARY:
        assert "Authorization" in first.headers["vary"]
    again = client.get(path, headers={"If-None-Match": first.headers["etag"]})
    assert (again.status_code, again.content) == (304, b"")


@pytest.mark.usefixtures("stored")
@pytest.mark.parametrize("path", [path for path in PUBLIC_READS if path != SUMMARY])
def test_signed_in_reads_stay_private(path: str) -> None:
    response = reader_client(STUDENT).get(path)
    assert response.headers["cache-control"] == PRIVATE_NO_CACHE
    assert "Authorization" in response.headers["vary"]


@pytest.mark.parametrize(
    ("reader", "acls"),
    [
        (None, ("PUBLIC", "SIGNED_IN")),
        (STUDENT, ("PUBLIC", "SIGNED_IN")),
        (RESEARCHER, ("PUBLIC", "RESEARCHER", "SIGNED_IN")),
    ],
    ids=["anonymous", "student", "researcher"],
)
def test_every_public_read_of_claims_is_built_for_the_chunks_its_reader_may_quote(
    stored: Asked, reader: User | None, acls: tuple[str, ...]
) -> None:
    client = reader_client(reader)
    for path in CLAIM_READS:
        assert client.get(path).status_code == 200, path
    assert stored.acls == {name: {acls} for name in CLAIM_READS.values()}


@pytest.mark.usefixtures("stored")
def test_an_anonymous_craft_page_holds_all_the_evidence_a_researcher_sees() -> None:
    path = f"/api/crafts/{AJRAKH}/page"
    anonymous = reader_client(None).get(path).json()
    researcher = reader_client(RESEARCHER).get(path).json()
    assert anonymous["evidence"] is not None
    assert anonymous["evidence"] == researcher["evidence"]


@pytest.mark.usefixtures("stored")
def test_the_full_craft_list_is_refused_to_an_anonymous_reader() -> None:
    response = reader_client(None).get("/api/crafts/catalogue", params={"includeInactive": "true"})
    assert (response.status_code, response.json()) == (401, {"detail": SIGN_IN_DETAIL})
    listed = reader_client(None).get("/api/crafts/catalogue").json()["crafts"]
    assert not {"status", "mergedIntoId", "referenceCount"} & {key for row in listed for key in row}


@pytest.mark.usefixtures("stored")
def test_anonymous_reads_are_limited_per_address_and_signed_in_reads_are_not(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(rate_limit, "PUBLIC_READS_PER_WINDOW", ROUTE_LIMIT)
    anonymous = reader_client(None)
    answered = [anonymous.get("/api/map/crafts").status_code for _ in range(ROUTE_LIMIT)]
    assert set(answered) == {200}
    refused = anonymous.get("/api/map/crafts")
    assert (refused.status_code, refused.json()) == (429, {"detail": THROTTLED_DETAIL})
    assert int(refused.headers["retry-after"]) >= 1
    assert reader_client(STUDENT).get("/api/map/crafts").status_code == 200


async def test_the_limit_counts_each_address_on_its_own() -> None:
    def visitor(address: str) -> Any:
        return SimpleNamespace(client=SimpleNamespace(host=address), headers={})

    async def read(connection: Any) -> bool:
        return (await rate_limit.public_read_attempt(connection, now=MOMENT))[0]

    first, second = visitor("203.0.113.5"), visitor("198.51.100.7")
    assert [await read(first) for _ in range(PUBLIC_READS_PER_WINDOW)] == [True] * PUBLIC_READS_PER_WINDOW
    assert await read(first) is False
    assert await read(second) is True


@pytest.mark.usefixtures("stored")
def test_one_address_reads_a_campus_worth_of_kutch_ajrakh_pages_in_a_window() -> None:
    assert len(PAGE_VIEW_READS) <= rate_limit.COUNTED_READS_PER_PAGE_VIEW
    client = reader_client(None)
    for _ in range(rate_limit.CAMPUS_PAGE_VIEWS_PER_WINDOW):
        for path in (*PAGE_VIEW_READS, *ASSET_READS):
            assert client.get(path).status_code == 200, path


@pytest.mark.usefixtures("stored")
def test_long_cached_reads_are_answered_after_the_page_allowance_is_spent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(rate_limit, "PUBLIC_READS_PER_WINDOW", ROUTE_LIMIT)
    client = reader_client(None)
    for _ in range(ROUTE_LIMIT):
        client.get("/api/map/crafts")
    assert client.get("/api/map/crafts").status_code == 429
    assert [client.get(path).status_code for path in ASSET_READS] == [200] * len(ASSET_READS)


@pytest.mark.usefixtures("stored")
def test_long_cached_reads_are_limited_per_address_in_a_bucket_of_their_own(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(rate_limit, "PUBLIC_ASSET_READS_PER_WINDOW", len(ASSET_READS))
    client = reader_client(None)
    assert [client.get(path).status_code for path in ASSET_READS] == [200] * len(ASSET_READS)
    refused = client.get(ASSET_READS[0])
    assert (refused.status_code, refused.json()) == (429, {"detail": THROTTLED_DETAIL})
    assert int(refused.headers["retry-after"]) >= 1
    assert client.get("/api/map/crafts").status_code == 200
    assert reader_client(STUDENT).get(ASSET_READS[0]).status_code == 200


def test_an_address_reads_ten_long_cached_assets_for_every_counted_read() -> None:
    assert rate_limit.PUBLIC_ASSET_READS_PER_WINDOW == 9000
    assert rate_limit.SERVER_ASSET_READS_PER_WINDOW == 90_000
