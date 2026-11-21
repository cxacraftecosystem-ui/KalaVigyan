import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_engine
from app.core.errors import InvalidInput
from app.services.open_data import Publication, build_release, record_release
from app.services.open_data_listing import open_data_listing
from app.services.open_data_release import ReleaseStamp
from app.services.open_data_rows import read_tables

from .open_data_seed import (
    ALUM_QUOTE,
    CATEGORY,
    CONTRIBUTOR,
    FAMILY,
    HELD,
    HELD_QUOTE,
    IDS,
    RESEARCHER_ONLY,
    RESTRICTED_ONLY,
    RETRACTED,
    SECRET_TITLE,
    SHOWN,
    SLUG,
    TESTIMONY_ONLY,
    add_claim,
    seed_open_data,
)

pytestmark = pytest.mark.db

SITE = "https://kalavigyan.example"
RECORD = "https://zenodo.org/records/300"
FIRST = ReleaseStamp("ZENODO", "2026.11.21", "10.5281/zenodo.300", "10.5281/zenodo.299", 300, 299)
SECOND = ReleaseStamp("ZENODO", "2026.11.22", "10.5281/zenodo.301", "10.5281/zenodo.299", 301, 299)
LATER = uuid.UUID("0da7a000-0000-4000-8000-000000000777")


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async with get_engine().connect() as connection:
        transaction = await connection.begin()
        try:
            opened = AsyncSession(bind=connection, expire_on_commit=False, autoflush=False)
            await seed_open_data(opened)
            yield opened
            await opened.close()
        finally:
            await transaction.rollback()


def _by(rows: list[dict[str, object]], column: str, value: object) -> list[dict[str, object]]:
    return [row for row in rows if row[column] == value]


async def test_only_published_facts_with_an_open_public_citation_are_released(session: AsyncSession) -> None:
    tables = await read_tables(session, site=SITE)
    claims = {row["id"]: row for row in tables.rows["claims"]}
    assert str(SHOWN) in claims
    for hidden in (RESTRICTED_ONLY, TESTIMONY_ONLY, HELD, RETRACTED, RESEARCHER_ONLY):
        assert str(hidden) not in claims
    shown = claims[str(SHOWN)]
    assert (shown["craft"], shown["family"], shown["category"]) == (SLUG, FAMILY, CATEGORY)
    assert (shown["subject_kind"], shown["subject"], shown["relation"]) == ("MATERIAL", "Alum", False)
    assert (shown["field"], shown["level"], shown["status"]) == ("CHEMISTRY", "PROVISIONAL", "APPROVED")
    (cite,) = _by(tables.rows["citations"], "claim_id", str(SHOWN))
    assert (cite["source_id"], cite["locator"], cite["quoted"], cite["quote_check"]) == (
        str(IDS["paper"]),
        "p. 4",
        True,
        "PASS",
    )
    sources = {row["id"] for row in tables.rows["sources"]}
    assert str(IDS["paper"]) in sources
    assert {str(IDS["secret"]), str(IDS["testimony"])}.isdisjoint(sources)


async def test_the_curated_structure_keeps_only_what_rests_on_released_facts(session: AsyncSession) -> None:
    tables = await read_tables(session, site=SITE)
    (stage,) = _by(tables.rows["stages"], "craft", SLUG)
    assert (stage["key"], stage["name"], stage["stage_type"], stage["order"]) == (
        "P01",
        "Mordanting",
        "MORDANT",
        1,
    )
    assert (stage["claim_ids"], stage["duration"]) == ([str(SHOWN)], None)
    assert [row["key"] for row in _by(tables.rows["materials"], "craft", SLUG)] == ["M01"]
    (reaction,) = _by(tables.rows["reactions"], "craft", SLUG)
    assert reaction["reactants"] == [{"name": "alum", "formula": "KAl(SO4)2"}]
    assert [row["text"] for row in _by(tables.rows["native_names"], "craft", SLUG)] == ["ફટકડી"]
    (gi,) = _by(tables.rows["gi_records"], "craft", SLUG)
    assert (gi["application_number"], gi["claim_ids"]) == ("999", [str(SHOWN)])
    (craft,) = _by(tables.rows["crafts"], "slug", SLUG)
    assert (craft["curated_version"], craft["page_url"]) == (3, f"{SITE}/crafts/{SLUG}")


async def test_no_file_carries_a_quote_a_contributor_or_a_restricted_source(session: AsyncSession) -> None:
    built = await build_release(session, FIRST, site=SITE)
    every = b"".join(built.files.files.values())
    for private in (ALUM_QUOTE, HELD_QUOTE, CONTRIBUTOR, SECRET_TITLE, "open-data-contributor@example.com"):
        assert private.encode() not in every
    assert b"Alum fixes the madder red." in every


async def test_the_same_database_builds_the_same_bytes(session: AsyncSession) -> None:
    first = await build_release(session, FIRST, site=SITE)
    again = await build_release(session, FIRST, site=SITE)
    assert first.files.files == again.files.files


async def test_a_published_release_is_listed_and_the_next_one_names_its_changes(
    session: AsyncSession,
) -> None:
    await build_release(session, FIRST, site=SITE)
    published = Publication(
        "ZENODO", FIRST.version, FIRST.doi, RECORD, datetime(2026, 11, 21, 10, tzinfo=UTC)
    )
    await record_release(session, published)
    listing = await open_data_listing(session, site=SITE)
    assert listing.concept_doi == "10.5281/zenodo.299"
    assert listing.citation.endswith(
        "(Version 2026.11.21) [Data set]. Zenodo. https://doi.org/10.5281/zenodo.300"
    )
    assert listing.latest is not None and listing.latest.version == "2026.11.21"
    links = {file.path: file.download_url for file in listing.latest.files}
    assert links["claims.jsonl"] == f"{RECORD}/files/claims.jsonl?download=1"
    await add_claim(session, LATER, "Alum is weighed by hand.", cite=(IDS["paper"], None, "NA", None))
    second = await build_release(session, SECOND, site=SITE)
    assert second.changes.previous == "2026.11.21"
    assert str(LATER) in second.changes.tables["claims"].added
    assert str(LATER) in second.files.files["CHANGES.md"].decode("utf-8")


async def test_a_published_version_is_never_rebuilt_and_a_record_names_the_built_doi(
    session: AsyncSession,
) -> None:
    await build_release(session, FIRST, site=SITE)
    with pytest.raises(InvalidInput, match=r"not 10.5281/zenodo.9"):
        await record_release(
            session, Publication("ZENODO", FIRST.version, "10.5281/zenodo.9", RECORD, datetime.now(UTC))
        )
    await record_release(session, Publication("ZENODO", FIRST.version, FIRST.doi, RECORD, datetime.now(UTC)))
    with pytest.raises(InvalidInput, match="published"):
        await build_release(session, FIRST, site=SITE)


async def test_the_public_route_describes_the_dataset_to_anyone(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/open-data")
    assert response.status_code == 200
    body = response.json()
    assert (body["schemaVersion"], body["licence"]["id"]) == (1, "CC-BY-4.0")
    assert len(body["tables"]) == 14
    assert "quote" not in {field["name"] for table in body["tables"] for field in table["fields"]}
