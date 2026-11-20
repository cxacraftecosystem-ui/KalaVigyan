from collections import defaultdict
from collections.abc import AsyncIterator
from typing import Any

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_engine
from app.models import ArticleSection, Claim, CraftCategory
from app.services import knowledge_view
from app.services.category_import import import_categories
from app.services.curation_import import import_curation
from app.services.curation_keys import curated_id
from app.services.curation_sections import publish_curated_sections

from ..curation.import_support import AJRAKH, raw

pytestmark = pytest.mark.db

DHOKRA = "Bastar-Dhokra"
TEXTILES = "Textiles-Based-Craft-Category"
CATEGORY_DOSSIER = "categories/Textiles-Based-Craft-Category.json"


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


def expected_sections(slug: str, dossier: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    sections: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for claim in dossier["claims"]:
        if not claim.get("hypothesis", False):
            sections[claim["discipline"]].append(
                {"text": claim["text"], "claimIds": [str(curated_id(slug, claim["id"]))]}
            )
    return dict(sections)


async def published(session: AsyncSession, column: Any, owner: Any) -> dict[str, list[dict[str, Any]]]:
    rows = await session.scalars(
        select(ArticleSection).where(column == owner, ArticleSection.status == "PUBLISHED")
    )
    return {row.field: list(row.sentences) for row in rows.all()}


async def craft_id(session: AsyncSession, slug: str) -> Any:
    craft = await knowledge_view.resolve_craft(session, slug)
    assert craft is not None
    return craft.id


async def test_the_import_publishes_one_section_per_field_from_the_dossier_s_claims_in_order(
    session: AsyncSession,
) -> None:
    report = await import_curation(session)
    assert report.refused == []
    outcome = next(found for found in report.dossiers if found.craft_slug == DHOKRA)
    expected = expected_sections(DHOKRA, raw(DHOKRA))
    assert outcome.changed["sections"] == len(expected)
    assert await published(session, ArticleSection.craftId, await craft_id(session, DHOKRA)) == expected


async def test_a_craft_with_an_authored_monograph_keeps_the_sections_its_monograph_writes(
    session: AsyncSession,
) -> None:
    await import_curation(session)
    assert await published(session, ArticleSection.craftId, await craft_id(session, AJRAKH)) == {}


async def test_a_category_dossier_publishes_its_fields_too(session: AsyncSession) -> None:
    await import_curation(session)
    categories = await import_categories(session)
    assert categories.refused == []
    category = await session.scalar(select(CraftCategory.id).where(CraftCategory.slug == TEXTILES))
    found = await published(session, ArticleSection.categoryId, category)
    assert found == expected_sections(TEXTILES, json_dossier(CATEGORY_DOSSIER))


def json_dossier(name: str) -> dict[str, Any]:
    return raw(name.removesuffix(".json"))


async def test_publishing_again_changes_nothing_and_a_retracted_claim_supersedes_its_field(
    session: AsyncSession,
) -> None:
    await import_curation(session)
    await import_categories(session)
    again = await publish_curated_sections(session)
    assert again.written == {} and again.refused == {}
    dossier = raw(DHOKRA)
    first = next(claim for claim in dossier["claims"] if not claim.get("hypothesis", False))
    claim_id = curated_id(DHOKRA, first["id"])
    await session.execute(update(Claim).where(Claim.id == claim_id).values(status="RETRACTED"))
    after = await publish_curated_sections(session)
    assert after.written == {f"{DHOKRA}.json": 1}
    owner = await craft_id(session, DHOKRA)
    versions = await session.execute(
        select(ArticleSection.version, ArticleSection.status)
        .where(ArticleSection.craftId == owner, ArticleSection.field == first["discipline"])
        .order_by(ArticleSection.version)
    )
    assert versions.tuples().all() == [(1, "SUPERSEDED"), (2, "PUBLISHED")]
    sentences = (await published(session, ArticleSection.craftId, owner))[first["discipline"]]
    assert str(claim_id) not in {claim for sentence in sentences for claim in sentence["claimIds"]}
    total = await session.scalar(
        select(func.count()).select_from(ArticleSection).where(ArticleSection.craftId == owner)
    )
    assert total == len(expected_sections(DHOKRA, dossier)) + 1
