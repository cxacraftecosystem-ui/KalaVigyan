import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_engine
from app.models import Claim, Concept, Craft, CuratedCraft
from app.services.craft_finder import find_crafts
from app.services.craft_resolver import CraftIndexStore

pytestmark = pytest.mark.db

SITE = "https://kalavigyan.example"
DHOKRA = "Bastar-Dhokra"
EMPTY_ROW = "Metal-Casting"
HELD = (
    "Bastar Dhokra figures are cast in bell metal by the lost-wax process in Kondagaon.",
    "Dhokra artisans melt scrap brass and bell metal in a clay crucible over a charcoal fire.",
    "The wax model of a Dhokra figure is wound from threads of beeswax and dammar resin.",
)
GOLDEN = [
    ("bell metal casting", DHOKRA),
    ("dhokra bell metal", DHOKRA),
    ("Metal Casting", EMPTY_ROW),
    ("Bastar Dhokra", DHOKRA),
]


def key(name: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"test-craft-finder/{name}")


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async with get_engine().connect() as connection:
        transaction = await connection.begin()
        try:
            opened = AsyncSession(bind=connection, expire_on_commit=False, autoflush=False)
            await _seed(opened)
            yield opened
            await opened.close()
        finally:
            await transaction.rollback()


async def _seed(session: AsyncSession) -> None:
    craft_id = await session.scalar(select(Craft.id).where(Craft.slug == DHOKRA))
    assert craft_id is not None, "the craft catalogue is seeded before the database tests"
    concept = key("concept")
    session.add(Concept(id=concept, craftId=craft_id, type="MATERIAL", name="bell metal"))
    await session.flush()
    session.add_all(
        [
            Claim(
                id=key(f"claim-{number}"),
                subjectType="CONCEPT",
                subjectId=concept,
                predicate="states",
                text=text,
                evidenceLevel="PROVISIONAL",
                origin="IMPORT",
                field="PROCESS",
            )
            for number, text in enumerate(HELD)
        ]
    )
    if await session.get(CuratedCraft, craft_id) is None:
        session.add(
            CuratedCraft(
                craftId=craft_id,
                version=1,
                curatedAt=datetime(2026, 11, 18, tzinfo=UTC),
                coverage="FULL",
                digest="0" * 64,
                page={},
            )
        )
    await session.flush()


@pytest.mark.parametrize(("query", "first"), GOLDEN)
async def test_the_golden_list(session: AsyncSession, query: str, first: str) -> None:
    found = await find_crafts(session, CraftIndexStore(), query, site=SITE)
    slugs = [item.craft.slug for item in found.crafts]
    assert slugs and slugs[0] == first, slugs
    assert found.crafts[0].page_url == f"{SITE}/crafts/{first}"


async def test_bell_metal_casting_finds_bastar_dhokra_above_the_empty_metal_casting_row(
    session: AsyncSession,
) -> None:
    found = await find_crafts(session, CraftIndexStore(), "bell metal casting", site=SITE)
    scores = {item.craft.slug: item.score for item in found.crafts}
    assert scores[DHOKRA] > scores.get(EMPTY_ROW, 0.0)
    dhokra = next(item for item in found.crafts if item.craft.slug == DHOKRA)
    assert dhokra.fields is not None and dhokra.score >= 0.45
