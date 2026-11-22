import json
from collections.abc import AsyncIterator
from dataclasses import replace
from datetime import UTC, datetime

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_engine
from app.core.errors import InvalidInput
from app.models import Craft
from app.services.open_data import Publication, build_release, latest_release, record_release
from app.services.open_data_listing import open_data_listing
from app.services.open_data_release import ReleaseStamp
from app.services.open_data_rows import read_tables
from app.services.open_data_slice import craft_slice

from .open_data_scope_seed import (
    CATEGORY_CLAIM,
    FAMILY_CLAIM,
    OTHER_CLAIM,
    OTHER_SLUG,
    OTHER_TEXT,
    seed_neighbours,
)
from .open_data_seed import (
    ALUM_QUOTE,
    CATEGORY,
    CONTRIBUTOR,
    FAMILY,
    IDS,
    RESEARCHER_ONLY,
    SHOWN,
    SLUG,
    seed_open_data,
)

pytestmark = pytest.mark.db

SITE = "https://kalavigyan.example"
WHOLE_FIRST = ReleaseStamp("ZENODO", "2026.11.21", "10.5281/zenodo.300", "10.5281/zenodo.299", 300, 299)
CRAFT_FIRST = ReleaseStamp(
    "ZENODO", "2026.11.21", "10.5281/zenodo.400", "10.5281/zenodo.399", 400, 399, craft=SLUG
)
CRAFT_SECOND = replace(CRAFT_FIRST, version="2026.11.22", doi="10.5281/zenodo.401", record_id=401)
TITLE = "Open Data Test Craft: KalaVigyan open knowledge"


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async with get_engine().connect() as connection:
        transaction = await connection.begin()
        try:
            opened = AsyncSession(bind=connection, expire_on_commit=False, autoflush=False)
            await seed_open_data(opened)
            await seed_neighbours(opened)
            yield opened
            await opened.close()
        finally:
            await transaction.rollback()


def _ids(rows: list[dict[str, object]], column: str) -> set[object]:
    return {row[column] for row in rows}


async def _published(session: AsyncSession, stamp: ReleaseStamp) -> None:
    await build_release(session, stamp, site=SITE)
    record = f"https://zenodo.org/records/{stamp.record_id}"
    published = datetime(2026, 11, int(stamp.version[-2:]), 10, tzinfo=UTC)
    await record_release(
        session, Publication("ZENODO", stamp.version, stamp.doi, record, published, stamp.craft)
    )


async def test_a_craft_release_holds_the_facts_an_answer_about_the_craft_reads_and_its_own_rows(
    session: AsyncSession,
) -> None:
    tables = await read_tables(session, site=SITE, craft=await craft_slice(session, SLUG))
    rows = tables.rows
    expected = {str(SHOWN), str(RESEARCHER_ONLY), str(FAMILY_CLAIM), str(CATEGORY_CLAIM)}
    assert _ids(rows["claims"], "id") == expected
    assert _ids(rows["citations"], "claim_id") == expected
    assert _ids(rows["sources"], "id") == {str(IDS["paper"])}
    assert [row["slug"] for row in rows["crafts"]] == [SLUG]
    assert ([row["slug"] for row in rows["families"]], [row["slug"] for row in rows["categories"]]) == (
        [FAMILY],
        [CATEGORY],
    )
    for name in ("stages", "materials", "reactions", "native_names", "gi_records"):
        assert _ids(rows[name], "craft") == {SLUG}, name
    whole = (await read_tables(session, site=SITE)).rows
    assert str(OTHER_CLAIM) in _ids(whole["claims"], "id")
    assert OTHER_SLUG in _ids(whole["crafts"], "slug") and OTHER_SLUG in _ids(whole["gi_records"], "craft")


async def test_a_craft_release_names_its_craft_leaves_out_its_neighbour_and_builds_the_same_bytes(
    session: AsyncSession,
) -> None:
    first = await build_release(session, CRAFT_FIRST, site=SITE)
    again = await build_release(session, CRAFT_FIRST, site=SITE)
    assert first.files.files == again.files.files
    descriptor = json.loads(first.files.files["datapackage.json"])
    assert (descriptor["title"], descriptor["craft"]["slug"]) == (TITLE, SLUG)
    every = b"".join(first.files.files.values())
    assert b"Alum fixes the madder red." in every
    for left_out in (OTHER_TEXT, ALUM_QUOTE, CONTRIBUTOR, "open-data-contributor@example.com"):
        assert left_out.encode() not in every
    assert first.counts["crafts"] == 1 and first.counts["claims"] == 4


async def test_the_latest_release_and_its_changes_are_kept_per_target_and_scope(
    session: AsyncSession,
) -> None:
    await _published(session, WHOLE_FIRST)
    await _published(session, CRAFT_FIRST)
    whole = await latest_release(session, "ZENODO")
    craft = await latest_release(session, "ZENODO", craft=SLUG)
    assert (whole and whole.doi, craft and craft.doi) == (WHOLE_FIRST.doi, CRAFT_FIRST.doi)
    assert await latest_release(session, "ZENODO", craft=OTHER_SLUG) is None
    second = await build_release(session, CRAFT_SECOND, site=SITE)
    unchanged = {"added": 0, "removed": 0, "changed": 0}
    assert second.changes.previous == "2026.11.21"
    assert (second.changes.counts()["claims"], second.changes.counts()["crafts"]) == (unchanged, unchanged)
    listing = await open_data_listing(session, site=SITE)
    assert [release.doi for release in listing.releases] == [WHOLE_FIRST.doi]
    (shown,) = listing.craft_releases
    assert (shown.craft, shown.craft_name, shown.title, shown.concept_doi) == (
        SLUG,
        "Open Data Test Craft",
        TITLE,
        "10.5281/zenodo.399",
    )
    cited = f"{TITLE} (Version 2026.11.21) [Data set]. Zenodo. https://doi.org/10.5281/zenodo.400"
    assert shown.citation.endswith(cited)


async def test_a_craft_release_of_an_unknown_or_merged_craft_is_refused(session: AsyncSession) -> None:
    with pytest.raises(InvalidInput, match="No craft has the slug"):
        await craft_slice(session, "No-Such-Open-Data-Craft")
    await session.execute(
        update(Craft).where(Craft.slug == OTHER_SLUG).values(status="MERGED", mergedIntoId=IDS["craft"])
    )
    with pytest.raises(InvalidInput, match="merged"):
        await craft_slice(session, OTHER_SLUG)
