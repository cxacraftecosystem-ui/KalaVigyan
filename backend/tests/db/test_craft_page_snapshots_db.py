from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_engine
from app.models import Claim, Concept, Craft, CraftLocation, CraftPageSnapshot, CuratedCraft
from app.services import knowledge_view
from app.services.craft_page_snapshots import rebuild_snapshots, served_page
from app.services.craft_page_stamp import page_stamp
from app.services.curation_import import import_curation

pytestmark = pytest.mark.db

AJRAKH = "Kutch-Ajrakh"
LATER = timedelta(minutes=5)


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


async def ajrakh(session: AsyncSession) -> Craft:
    report = await import_curation(session)
    assert report.refused == []
    craft = await knowledge_view.resolve_craft(session, AJRAKH)
    assert craft is not None
    return craft


async def test_a_second_read_is_answered_from_the_snapshot(session: AsyncSession) -> None:
    craft = await ajrakh(session)
    first = await served_page(session, craft, "OPEN")
    stored = await session.get(CraftPageSnapshot, (craft.id, "OPEN"))
    assert stored is not None and stored.etag == first.etag
    built = stored.builtAt
    again = await served_page(session, craft, "OPEN")
    assert (again.etag, again.body) == (first.etag, first.body)
    await session.refresh(stored)
    assert stored.builtAt == built


async def test_each_variant_keeps_its_own_snapshot_and_stamp(session: AsyncSession) -> None:
    craft = await ajrakh(session)
    shown = await served_page(session, craft, "OPEN")
    quoted = await served_page(session, craft, "RESEARCHER")
    assert shown.stamp != quoted.stamp
    rows = (
        await session.scalars(select(CraftPageSnapshot.variant).where(CraftPageSnapshot.craftId == craft.id))
    ).all()
    assert sorted(rows) == ["OPEN", "RESEARCHER"]


async def test_the_stamp_moves_when_a_claim_of_the_craft_changes(session: AsyncSession) -> None:
    craft = await ajrakh(session)
    before = await page_stamp(session, craft, "OPEN")
    concepts = select(Concept.id).where(Concept.craftId == craft.id)
    claim_id = await session.scalar(select(Claim.id).where(Claim.subjectId.in_(concepts)).limit(1))
    await session.execute(
        update(Claim).where(Claim.id == claim_id).values(updatedAt=datetime.now(UTC) + LATER)
    )
    assert await page_stamp(session, craft, "OPEN") != before


async def test_the_stamp_moves_when_a_place_of_the_craft_changes(session: AsyncSession) -> None:
    craft = await ajrakh(session)
    before = await page_stamp(session, craft, "OPEN")
    await session.execute(
        update(CraftLocation)
        .where(CraftLocation.craftId == craft.id)
        .values(updatedAt=datetime.now(UTC) + LATER)
    )
    assert await page_stamp(session, craft, "OPEN") != before


async def test_a_page_of_an_earlier_curation_version_is_rebuilt_and_never_archived(
    session: AsyncSession,
) -> None:
    craft = await ajrakh(session)
    first = await served_page(session, craft, "OPEN")
    version = first.body["curation"]["version"]
    stored = await session.get(CraftPageSnapshot, (craft.id, "OPEN"))
    assert stored is not None
    stored.body = {**first.body, "curation": {**first.body["curation"], "version": version - 1}}
    stored.stamp = "an older stamp"
    await session.flush()
    again = await served_page(session, craft, "OPEN")
    assert again.body["curation"]["version"] == version
    assert await session.scalar(text("SELECT to_regclass('\"CraftPageArchive\"')")) is None


async def test_a_nightly_rebuild_under_the_same_stamp_changes_nothing(session: AsyncSession) -> None:
    craft = await ajrakh(session)
    await served_page(session, craft, "OPEN")
    await served_page(session, craft, "RESEARCHER")
    assert await rebuild_snapshots(session, craft) is False
    version = await session.scalar(select(CuratedCraft.version).where(CuratedCraft.craftId == craft.id))
    assert version is not None
