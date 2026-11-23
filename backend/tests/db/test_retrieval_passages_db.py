import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Chunk
from app.research.field_voices import FIELD_SOURCE_KIND
from app.research.retrieval import EVERY_CHUNK_KINDS, OPEN_CHUNK_ACLS, KnowledgeQuery
from app.retrieval.hybrid import StoredKnowledgeSearch
from app.services.claim_seed import load_seed_claims, seed_claims, seed_id
from app.services.claim_seed_passages import seed_passages, store_seed_passages

from ..craft_fixtures import FixedEmbedder
from .field_voices_rows import KeptStore, rolled_back, synced

pytestmark = pytest.mark.db

GI_JOURNAL = seed_id("source", "ie:ajrakh:S1")
WOOD_HANDBOOK = seed_id("source", "inf:f388592d6a73")
GI_PASSAGE = (
    "India C) Name of the Geographical Indication : KUTCH AJRAKH D) Types of Goods : Class 24 and 25 - "
    "Textiles and textile goods E) Specification: Kutch Ajrakh is an elaborate resist block printing "
    "technique that involves series of direct and resist printing and dyeing"
)
GI_LOCATOR = "GI Journal No. 188 copy (application 1050), PDF p. 1"
WOOD_PASSAGE = "Green wood is often defined as freshly sawn wood in which the cell walls are completely saturated with water"
WOOD_LOCATOR = "Chapter 4, Moisture Relations and Physical Properties of Wood, p. 4-1, "


async def seeded_afresh(session: AsyncSession) -> int:
    data = load_seed_claims()
    assert (await seed_claims(session, data))["unresolvedSlugs"] == []
    sources = [passages.source_id for passages in seed_passages(data)]
    await session.execute(delete(Chunk).where(Chunk.sourceId.in_(sources)))
    return await store_seed_passages(session, data)


async def test_the_seed_import_keeps_each_checked_quote_as_a_passage_of_its_source() -> None:
    async with rolled_back() as session:
        assert await seeded_afresh(session) > 0
        gi = (
            await session.execute(
                select(Chunk.text, Chunk.locator, Chunk.acl).where(Chunk.sourceId == GI_JOURNAL)
            )
        ).all()
        assert any(row.text == GI_PASSAGE and GI_LOCATOR in row.locator and row.acl == "PUBLIC" for row in gi)
        wood = (
            await session.execute(
                select(Chunk.text, Chunk.locator, Chunk.acl).where(Chunk.sourceId == WOOD_HANDBOOK)
            )
        ).all()
        assert wood and {row.acl for row in wood} == {"PUBLIC"}
        assert any(WOOD_PASSAGE in row.text and row.locator.startswith(WOOD_LOCATOR) for row in wood)
        assert await store_seed_passages(session, load_seed_claims()) == 0


async def test_seeded_passages_are_found_for_their_craft() -> None:
    async with rolled_back() as session:
        await seeded_afresh(session)
        found = await StoredKnowledgeSearch(session, embed=FixedEmbedder()).search(
            KnowledgeQuery(craft_slug="Kutch-Ajrakh", text="GI specification of Kutch Ajrakh", mode="HYBRID")
        )
        seeded = {passages.source_id for passages in seed_passages(load_seed_claims())}
        assert any(hit.source_id in seeded for hit in found.chunks)


async def test_passages_never_crowd_an_artisans_words_out_of_the_hits() -> None:
    async with rolled_back() as session:
        await synced(session, KeptStore())
        await seeded_afresh(session)
        found = await StoredKnowledgeSearch(session, embed=FixedEmbedder()).search(
            KnowledgeQuery(
                craft_slug="Kutch-Ajrakh",
                text="How is ajrakh printed and dyed?",
                mode="HYBRID",
                chunk_acls=OPEN_CHUNK_ACLS,
                chunk_kinds=EVERY_CHUNK_KINDS,
                limit=2,
            )
        )
        kinds = [hit.source_kind for hit in found.chunks]
        assert kinds.count(FIELD_SOURCE_KIND) >= 1
        assert len(kinds) - kinds.count(FIELD_SOURCE_KIND) == 2
