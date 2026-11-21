import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
from sqlalchemy import text, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.expression import ClauseElement, Executable

from app.core.db import get_engine
from app.models import Claim, ClaimSource, Concept, Craft, CraftCategory, CraftSubCategory, Source, Term
from app.research.retrieval import KnowledgeHits, KnowledgeQuery
from app.retrieval.hybrid import StoredKnowledgeSearch
from app.retrieval.indexing import embed_written
from app.retrieval.nearest import EF_SEARCH, ITERATIVE_SCAN
from app.retrieval.statements import EVERY_CRAFT, CraftScope, claim_conditions, claim_vector_ranking

from ..craft_fixtures import FixedEmbedder, unit

pytestmark = pytest.mark.db

SLUG = "Quillon-Print"


def key(name: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"test-first-stage/{name}")


CATEGORY, FAMILY, CRAFT, SOURCE = key("category"), key("family"), key("craft"), key("source")
REGISTRY, PASTE, MARK, WASHING = key("registry"), key("paste"), key("mark"), key("washing")
SHARED, FAMILY_SCIENCE = key("shared"), key("family-science")
GI_FACT, SIYAHI_FACT, XY_FACT = key("gi-fact"), key("siyahi-fact"), key("xy-fact")
WASH_FACT, SHARED_FACT, FAMILY_FACT, SPELT = (
    key("wash-fact"),
    key("shared-fact"),
    key("family-fact"),
    key("spelt"),
)


class Explain(Executable, ClauseElement):
    inherit_cache = False

    def __init__(self, statement: Any) -> None:
        self.statement = statement


@compiles(Explain)
def _explain(element: Explain, compiler: Any, **kw: Any) -> str:
    return "EXPLAIN " + compiler.process(element.statement, **kw)


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
    session.add(CraftCategory(id=CATEGORY, slug="test-quillon", name="Test Quillon", sortOrder=997))
    await session.flush()
    session.add(
        CraftSubCategory(
            id=FAMILY, slug="test-quillon-family", name="Quillon", categoryId=CATEGORY, sortOrder=1
        )
    )
    await session.flush()
    session.add(Craft(id=CRAFT, slug=SLUG, name="Quillon Print", subCategoryId=FAMILY))
    session.add(Source(id=SOURCE, kind="BOOK", title="Quillon printing"))
    await session.flush()
    session.add_all(
        [
            Concept(id=REGISTRY, craftId=CRAFT, type="HISTORICAL_CONTEXT", name="Registration"),
            Concept(id=PASTE, craftId=CRAFT, type="MATERIAL", name="Black paste"),
            Concept(id=MARK, craftId=CRAFT, type="MATERIAL", name="Maker's stamp"),
            Concept(id=WASHING, craftId=CRAFT, type="PROCESS_STAGE", name="Washing"),
            Concept(id=SHARED, subCategoryId=FAMILY, type="MATERIAL", name="River water"),
            Concept(id=FAMILY_SCIENCE, type="MATERIAL", name="Test Quillon"),
        ]
    )
    session.add(
        Term(id=key("term-gi"), key="test-first-stage-gi", label="GI", aliases=["geographical indication"])
    )
    session.add(Term(id=key("term-syahi"), key="test-first-stage-syahi", label="Syahi", aliases=["siyahi"]))
    await session.flush()
    await _cited(session, _claims())


async def _cited(session: AsyncSession, claims: list[Claim]) -> None:
    session.add_all(claims)
    await session.flush()
    session.add_all([ClaimSource(claimId=claim.id, sourceId=SOURCE) for claim in claims])
    await session.flush()


def _claim(claim_id: uuid.UUID, subject: uuid.UUID, words: str, field: str | None = None) -> Claim:
    return Claim(
        id=claim_id,
        subjectType="CONCEPT",
        subjectId=subject,
        predicate="explains",
        text=words,
        field=field,
        embedding=unit(1.0),
        evidenceLevel="PROVISIONAL",
        origin="IMPORT",
    )


def _claims() -> list[Claim]:
    return [
        _claim(
            GI_FACT,
            REGISTRY,
            "The geographical indication registry lists the print under number 165.",
            "POLICY",
        ),
        _claim(SIYAHI_FACT, PASTE, "Siyahi is fermented from scrap iron and jaggery."),
        _claim(XY_FACT, MARK, "An xy mark is stamped on every finished piece."),
        _claim(WASH_FACT, WASHING, "It is then washed in the river.", "PROCESS"),
        _claim(SHARED_FACT, SHARED, "Hard water dulls the red.", "GEOGRAPHY"),
        _claim(FAMILY_FACT, FAMILY_SCIENCE, "Alum fixes the dye to the fibre.", "CHEMISTRY"),
    ]


async def searched(session: AsyncSession, question: str, slug: str | None = SLUG) -> KnowledgeHits:
    search = StoredKnowledgeSearch(session, embed=FixedEmbedder())
    return await search.search(KnowledgeQuery(craft_slug=slug, text=question, mode="HYBRID"))


def lexical(found: KnowledgeHits) -> list[tuple[int, uuid.UUID]]:
    return sorted((hit.lexical_rank, hit.claim_id) for hit in found.claims if hit.lexical_rank is not None)


async def test_a_short_glossary_word_reaches_the_words_search_with_the_terms_other_names(
    session: AsyncSession,
) -> None:
    assert lexical(await searched(session, "Who holds the GI?")) == [(1, GI_FACT)]


async def test_either_spelling_of_a_transliteration_finds_the_other(session: AsyncSession) -> None:
    assert lexical(await searched(session, "How long is syahi left?")) == [(1, SIYAHI_FACT)]
    await _cited(session, [_claim(SPELT, PASTE, "Syahi darkens as it ages.")])
    later = lexical(await searched(session, "How long is siyahi left?"))
    assert {claim for _, claim in later} == {SIYAHI_FACT, SPELT}


async def test_a_short_word_that_names_no_term_is_left_out_until_the_glossary_names_it(
    session: AsyncSession,
) -> None:
    assert lexical(await searched(session, "Who made the xy?")) == []
    session.add(Term(id=key("term-xy"), key="test-first-stage-xy", label="XY"))
    await session.flush()
    assert lexical(await searched(session, "Who made the xy?")) == [(1, XY_FACT)]


async def test_a_question_about_no_single_craft_is_ordered_by_the_vector_index(session: AsyncSession) -> None:
    await session.execute(text("SET LOCAL enable_seqscan = off"))
    await session.execute(text("SET LOCAL enable_sort = off"))
    vector = unit(1.0)
    every = claim_vector_ranking(claim_conditions(EVERY_CRAFT, mode="HYBRID"), vector)
    plan = "\n".join(row[0] for row in (await session.execute(Explain(every))).all())
    assert "Claim_embedding_hnsw_idx" in plan, plan
    scope = CraftScope(craft_id=CRAFT, sub_category_id=FAMILY)
    exact = claim_vector_ranking(claim_conditions(scope, mode="HYBRID"), vector)
    plan = "\n".join(row[0] for row in (await session.execute(Explain(exact))).all())
    assert "hnsw" not in plan, plan


async def test_the_index_scan_runs_with_its_settings_and_finds_the_claims(session: AsyncSession) -> None:
    found = await searched(session, "Who holds the GI?", slug=None)
    ranked = {hit.claim_id: hit.vector_rank for hit in found.claims}
    assert ranked.get(GI_FACT) is not None
    settings = (
        await session.execute(
            text("SELECT current_setting('hnsw.iterative_scan'), current_setting('hnsw.ef_search')")
        )
    ).one()
    assert tuple(settings) == (ITERATIVE_SCAN, str(EF_SEARCH))


async def test_each_written_claim_is_embedded_with_its_craft_concept_and_field(session: AsyncSession) -> None:
    titled = [WASH_FACT, SHARED_FACT, FAMILY_FACT]
    await session.execute(update(Claim).where(Claim.id.in_(titled)).values(embedding=None))
    embed = FixedEmbedder()
    counts = await embed_written(session, embed, claim_ids=titled, source_ids=[])
    assert counts.claims == 3
    assert sorted(words for call in embed.calls for words in call) == [
        "title: Quillon Print · Washing · Process | text: It is then washed in the river.",
        "title: Quillon · River water · Geography | text: Hard water dulls the red.",
        "title: Test Quillon · Chemistry | text: Alum fixes the dye to the fibre.",
    ]
