import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_engine
from app.core.errors import InvalidInput
from app.models import Chunk, Claim, ClaimSource, Concept, Craft, CraftCategory, CraftSubCategory, Source
from app.research.retrieval import KnowledgeQuery
from app.retrieval.hybrid import StoredKnowledgeSearch
from app.retrieval.indexing import embed_pending, replace_source_chunks

from ..craft_fixtures import HALF, FixedEmbedder, unit

pytestmark = pytest.mark.db


def key(name: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"test-retrieval/{name}")


CATEGORY, FAMILY = key("category"), key("family")
CRAFT, OTHER = key("Zelvar-Print"), key("Zelvar-Weave")
OWN, SHARED, ELSEWHERE, HIDDEN = key("own"), key("shared"), key("elsewhere"), key("hidden")
OPEN_SOURCE, FAMILY_SOURCE, OTHER_SOURCE = key("open-source"), key("family-source"), key("other-source")
RESTRICTED_SOURCE, RESEARCHER_SOURCE = key("restricted-source"), key("researcher-source")
ALUM, IRON, OTHER_ALUM, RETRACTED, RESTRICTED_ONLY, HIDDEN_CONCEPT, GUESS = (
    key(f"claim-{n}") for n in range(7)
)
QUESTION = "alum mordant"


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async with get_engine().connect() as connection:
        transaction = await connection.begin()
        try:
            session = AsyncSession(bind=connection, expire_on_commit=False, autoflush=False)
            await _seed(session)
            yield session
            await session.close()
        finally:
            await transaction.rollback()


async def _seed(session: AsyncSession) -> None:
    session.add(CraftCategory(id=CATEGORY, slug="test-zelvar", name="Test Zelvar", sortOrder=999))
    await session.flush()
    session.add(
        CraftSubCategory(
            id=FAMILY, slug="test-zelvar-family", name="Zelvar", categoryId=CATEGORY, sortOrder=1
        )
    )
    await session.flush()
    session.add_all(
        [
            Craft(id=CRAFT, slug="Zelvar-Print", name="Zelvar Print", subCategoryId=FAMILY),
            Craft(id=OTHER, slug="Zelvar-Weave", name="Zelvar Weave"),
        ]
    )
    await session.flush()
    session.add_all(
        [
            Concept(id=OWN, craftId=CRAFT, type="MATERIAL", name="Alum"),
            Concept(id=SHARED, subCategoryId=FAMILY, type="MECHANISM", name="Iron tannate"),
            Concept(id=ELSEWHERE, craftId=OTHER, type="MATERIAL", name="Alum"),
            Concept(id=HIDDEN, craftId=CRAFT, type="MATERIAL", name="Sacred alum", sensitivity="RESTRICTED"),
            *_sources(),
        ]
    )
    await session.flush()
    session.add_all(_claims())
    await session.flush()
    session.add_all(_citations())
    await session.flush()


def _sources() -> list[Source]:
    return [
        Source(id=OPEN_SOURCE, kind="BOOK", title="Dyeing with Alum"),
        Source(id=FAMILY_SOURCE, kind="BOOK", title="Iron and Tannin"),
        Source(id=OTHER_SOURCE, kind="BOOK", title="Weaving Alum"),
        Source(id=RESTRICTED_SOURCE, kind="BOOK", title="Closed notes", sensitivity="RESTRICTED"),
        Source(id=RESEARCHER_SOURCE, kind="BOOK", title="Field notes"),
    ]


def _claim(claim_id: uuid.UUID, subject: uuid.UUID, text: str, vector: list[float], **extra: str) -> Claim:
    fields = {"evidenceLevel": "PROVISIONAL", "origin": "IMPORT", **extra}
    return Claim(
        id=claim_id,
        subjectType="CONCEPT",
        subjectId=subject,
        predicate="explains",
        text=text,
        embedding=vector,
        **fields,
    )


def _claims() -> list[Claim]:
    return [
        _claim(ALUM, OWN, "Alum mordant fixes madder dye on cotton.", unit(1.0)),
        _claim(IRON, SHARED, "Iron darkens tannin to black.", unit(HALF, HALF), evidenceLevel="REVIEWED"),
        _claim(OTHER_ALUM, ELSEWHERE, "Alum mordant fixes madder dye on wool.", unit(1.0)),
        _claim(RETRACTED, OWN, "Alum mordant was once thought harmful.", unit(1.0), status="RETRACTED"),
        _claim(RESTRICTED_ONLY, OWN, "Alum mordant from closed notes.", unit(1.0)),
        _claim(HIDDEN_CONCEPT, HIDDEN, "Alum mordant in the sacred rite.", unit(1.0)),
        _claim(GUESS, OWN, "Alum may also brighten the colour.", unit(0.0, 1.0), evidenceLevel="HYPOTHESIS"),
    ]


def _citations() -> list[ClaimSource]:
    pairs = [
        (ALUM, OPEN_SOURCE),
        (ALUM, RESEARCHER_SOURCE),
        (IRON, FAMILY_SOURCE),
        (OTHER_ALUM, OTHER_SOURCE),
        (RETRACTED, OPEN_SOURCE),
        (RESTRICTED_ONLY, RESTRICTED_SOURCE),
        (HIDDEN_CONCEPT, OPEN_SOURCE),
        (GUESS, OPEN_SOURCE),
    ]
    return [ClaimSource(claimId=claim, sourceId=source) for claim, source in pairs]


async def _index_chunks(session: AsyncSession) -> None:
    await replace_source_chunks(
        session, OPEN_SOURCE, "Alum is the mordant that fixes madder.\n\nIt is rinsed out."
    )
    await replace_source_chunks(session, FAMILY_SOURCE, "Myrobalan tannin binds iron.")
    await replace_source_chunks(session, OTHER_SOURCE, "Alum mordant for wool.")
    await replace_source_chunks(session, RESTRICTED_SOURCE, "Alum mordant, closed.")
    await replace_source_chunks(session, RESEARCHER_SOURCE, "Alum mordant field notes.", acl="RESEARCHER")
    await embed_pending(session, FixedEmbedder(), batch_size=500)
    await session.execute(
        update(Chunk).where(Chunk.sourceId == FAMILY_SOURCE).values(embedding=unit(0.0, 1.0))
    )


async def _chunk_id(session: AsyncSession, source_id: uuid.UUID) -> uuid.UUID:
    return (await session.scalars(select(Chunk.id).where(Chunk.sourceId == source_id))).one()


async def test_hybrid_mode_fuses_the_text_and_vector_rankings_of_the_crafts_claims(
    session: AsyncSession,
) -> None:
    embed = FixedEmbedder()
    found = await StoredKnowledgeSearch(session, embed=embed).search(
        KnowledgeQuery(craft_slug="Zelvar-Print", text=QUESTION, mode="HYBRID")
    )
    assert embed.calls == [["task: search result | query: alum mordant"]]
    assert [(h.claim_id, h.lexical_rank, h.vector_rank, h.entity_rank) for h in found.claims] == [
        (ALUM, 1, 1, 1),
        (GUESS, 2, 3, 2),
        (IRON, None, 2, None),
    ]
    assert [h.score for h in found.claims] == [
        pytest.approx(0.5 / 21 + 5 / 21 + 0.25 / 21, abs=1e-9),
        pytest.approx(0.5 / 22 + 5 / 23 + 0.25 / 22, abs=1e-9),
        pytest.approx(5 / 22, abs=1e-9),
    ]
    assert [h.level for h in found.claims] == ["PROVISIONAL", "HYPOTHESIS", "REVIEWED"]
    assert found.chunks == ()


async def test_verified_mode_reads_reviewed_claims_and_no_chunks(session: AsyncSession) -> None:
    await _index_chunks(session)
    found = await StoredKnowledgeSearch(session, embed=FixedEmbedder()).search(
        KnowledgeQuery(craft_slug="Zelvar-Print", text=QUESTION, mode="VERIFIED")
    )
    assert [(h.claim_id, h.lexical_rank, h.vector_rank) for h in found.claims] == [(IRON, None, 1)]
    assert found.claims[0].score == pytest.approx(5 / 21, abs=1e-9)
    assert found.chunks == ()


async def test_chunks_come_from_the_crafts_cited_sources_within_the_acl(session: AsyncSession) -> None:
    await _index_chunks(session)
    search = StoredKnowledgeSearch(session, embed=FixedEmbedder())
    found = await search.search(
        KnowledgeQuery(craft_slug="Zelvar-Print", text=QUESTION, mode="HYBRID", limit=5)
    )
    open_chunk, family_chunk = await _chunk_id(session, OPEN_SOURCE), await _chunk_id(session, FAMILY_SOURCE)
    assert [(h.chunk_id, h.lexical_rank, h.vector_rank) for h in found.chunks] == [
        (open_chunk, 1, 1),
        (family_chunk, None, 2),
    ]
    assert found.chunks[0].locator == "paras 1-2" and found.chunks[0].source_id == OPEN_SOURCE
    assert [h.score for h in found.chunks] == [
        pytest.approx(0.032786885, abs=1e-9),
        pytest.approx(0.016129032, abs=1e-9),
    ]
    wider = await search.search(
        KnowledgeQuery(
            craft_slug="Zelvar-Print", text=QUESTION, mode="HYBRID", chunk_acls=("PUBLIC", "RESEARCHER")
        )
    )
    assert {h.source_id for h in wider.chunks} == {OPEN_SOURCE, FAMILY_SOURCE, RESEARCHER_SOURCE}


async def test_facets_narrow_claims_and_chunks_to_those_concept_types(session: AsyncSession) -> None:
    await _index_chunks(session)
    found = await StoredKnowledgeSearch(session, embed=FixedEmbedder()).search(
        KnowledgeQuery(craft_slug="Zelvar-Print", text=QUESTION, mode="HYBRID", facets=("MECHANISM",))
    )
    assert [h.claim_id for h in found.claims] == [IRON]
    assert {h.source_id for h in found.chunks} == {FAMILY_SOURCE}


async def test_fields_keep_the_fields_claims_their_secondary_ones_and_the_unfielded(
    session: AsyncSession,
) -> None:
    await session.execute(update(Claim).where(Claim.id == ALUM).values(field="CHEMISTRY"))
    await session.execute(update(Claim).where(Claim.id == GUESS).values(field="HISTORY"))
    search = StoredKnowledgeSearch(session, embed=FixedEmbedder())

    async def found(*fields: str) -> set[uuid.UUID]:
        query = KnowledgeQuery(craft_slug="Zelvar-Print", text=QUESTION, mode="HYBRID", fields=fields)
        return {hit.claim_id for hit in (await search.search(query)).claims}

    assert await found("CHEMISTRY") == {ALUM, IRON}
    assert await found("HISTORY") == {GUESS, IRON}
    await session.execute(update(Claim).where(Claim.id == GUESS).values(fields=["CHEMISTRY"]))
    assert await found("CHEMISTRY") == {ALUM, IRON, GUESS}
    assert await found() == {ALUM, IRON, GUESS}


async def test_a_concept_the_question_names_ranks_its_claims_and_a_longer_name_ranks_first(
    session: AsyncSession,
) -> None:
    search = StoredKnowledgeSearch(session, embed=FixedEmbedder())
    named = await search.search(
        KnowledgeQuery(craft_slug="Zelvar-Print", text="Why does iron tannate need alum?", mode="HYBRID")
    )
    ranked = sorted((h.entity_rank, h.claim_id) for h in named.claims if h.entity_rank is not None)
    assert ranked == [(1, IRON), (2, ALUM), (3, GUESS)]
    unnamed = await search.search(
        KnowledgeQuery(craft_slug="Zelvar-Print", text="Why is the cloth washed?", mode="HYBRID")
    )
    assert all(hit.entity_rank is None for hit in unnamed.claims)


async def test_restricted_text_is_stored_but_never_embedded(session: AsyncSession) -> None:
    await _index_chunks(session)
    restricted = (await session.scalars(select(Chunk).where(Chunk.sourceId == RESTRICTED_SOURCE))).one()
    assert restricted.sensitivity == "RESTRICTED" and restricted.embedding is None
    researcher = (await session.scalars(select(Chunk).where(Chunk.sourceId == RESEARCHER_SOURCE))).one()
    assert researcher.acl == "RESEARCHER" and researcher.embedding is not None


async def test_rechunking_keeps_unchanged_vectors_and_drops_extra_chunks(session: AsyncSession) -> None:
    long_text = "\n\n".join(["a" * 999 + ".", "b" * 999 + "."])
    assert await replace_source_chunks(session, OPEN_SOURCE, long_text) == 2
    await embed_pending(session, FixedEmbedder(), batch_size=500)
    assert await replace_source_chunks(session, OPEN_SOURCE, long_text) == 2
    await session.flush()
    session.expire_all()
    kept = (
        await session.scalars(select(Chunk).where(Chunk.sourceId == OPEN_SOURCE).order_by(Chunk.ordinal))
    ).all()
    assert [c.embedding is not None for c in kept] == [True, True]
    assert await replace_source_chunks(session, OPEN_SOURCE, "Alum is the mordant.") == 1
    await session.flush()
    session.expire_all()
    left = (await session.scalars(select(Chunk).where(Chunk.sourceId == OPEN_SOURCE))).all()
    assert [(c.ordinal, c.text, c.embedding) for c in left] == [(0, "Alum is the mordant.", None)]


async def test_an_unknown_craft_is_refused(session: AsyncSession) -> None:
    with pytest.raises(InvalidInput, match="Nowhere-Craft"):
        await StoredKnowledgeSearch(session, embed=FixedEmbedder()).search(
            KnowledgeQuery(craft_slug="Nowhere-Craft", text=QUESTION, mode="HYBRID")
        )


async def test_any_craft_searches_every_crafts_visible_claims(session: AsyncSession) -> None:
    found = await StoredKnowledgeSearch(session, embed=FixedEmbedder()).search(
        KnowledgeQuery(craft_slug=None, text=QUESTION, mode="HYBRID", limit=50)
    )
    ids = {hit.claim_id for hit in found.claims}
    assert found.craft_slug is None
    assert {ALUM, OTHER_ALUM} <= ids
    assert ids.isdisjoint({RETRACTED, RESTRICTED_ONLY, HIDDEN_CONCEPT})
