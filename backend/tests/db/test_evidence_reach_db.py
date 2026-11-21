import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_engine
from app.models import (
    Claim,
    ClaimSource,
    Concept,
    Craft,
    CraftCategory,
    CraftSubCategory,
    CuratedCategoryClaim,
    Source,
)
from app.research.retrieval import KnowledgeHits, KnowledgeQuery
from app.retrieval.hybrid import StoredKnowledgeSearch, merged_into
from app.retrieval.indexing import embed_pending, replace_source_chunks

from ..craft_fixtures import FixedEmbedder

pytestmark = pytest.mark.db

SLUG = "Kelvar-Print"


def key(name: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"test-evidence-reach/{name}")


CATEGORY, METAL, FAMILY = key("category"), key("metal"), key("family")
CRAFT, OLD, OLDER, WEAVE = key("craft"), key("old"), key("older"), key("weave")
BOOK, GI = key("book"), key("gi")
ALUM, TEXTILES, TIN, DABU, BLOCK, WEAVE_ALUM, VAT = (
    key(f"concept-{name}") for name in ("alum", "textiles", "tin", "dabu", "block", "weave-alum", "vat")
)
FAMILY_ALUM, CONTRIBUTED, METAL_TIN, OLD_DABU, OLDER_BLOCK, ELSEWHERE, REGISTERED = (
    key(f"claim-{name}") for name in ("alum", "contributed", "tin", "dabu", "block", "elsewhere", "gi")
)
PRINTED = tuple(key(f"claim-printed-{n}") for n in range(12))


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
    await _crafts(session)
    session.add_all(_concepts())
    await session.flush()
    session.add_all(_claims())
    await session.flush()
    session.add_all(
        [ClaimSource(claimId=claim.id, sourceId=BOOK) for claim in _claims() if claim.id != REGISTERED]
    )
    session.add(ClaimSource(claimId=REGISTERED, sourceId=GI))
    session.add_all(
        [
            CuratedCategoryClaim(
                claimId=FAMILY_ALUM, categoryId=CATEGORY, key="C001", discipline="CHEMISTRY"
            ),
            CuratedCategoryClaim(claimId=METAL_TIN, categoryId=METAL, key="C001", discipline="CHEMISTRY"),
        ]
    )
    await session.flush()


async def _crafts(session: AsyncSession) -> None:
    session.add_all(
        [
            CraftCategory(id=CATEGORY, slug="test-kelvar", name="Test Kelvar Textiles", sortOrder=997),
            CraftCategory(id=METAL, slug="test-kelvar-metal", name="Test Kelvar Metal", sortOrder=996),
        ]
    )
    await session.flush()
    session.add(
        CraftSubCategory(
            id=FAMILY, slug="test-kelvar-family", name="Kelvar", categoryId=CATEGORY, sortOrder=1
        )
    )
    await session.flush()
    session.add_all(
        [
            Craft(id=CRAFT, slug=SLUG, name="Kelvar Print", subCategoryId=FAMILY),
            Craft(id=WEAVE, slug="Kelvar-Weave", name="Kelvar Weave"),
            Source(id=BOOK, kind="BOOK", title="Kelvar printing"),
            Source(id=GI, kind="GI_JOURNAL", title="Kelvar Print, GI Journal"),
        ]
    )
    await session.flush()
    session.add(
        Craft(id=OLD, slug="Kelvar-Old-Print", name="Kelvar Old Print", status="MERGED", mergedIntoId=CRAFT)
    )
    await session.flush()
    session.add(
        Craft(
            id=OLDER, slug="Kelvar-Older-Print", name="Kelvar Older Print", status="MERGED", mergedIntoId=OLD
        )
    )
    await session.flush()


def _concepts() -> list[Concept]:
    return [
        Concept(id=ALUM, type="MATERIAL", name="Alum"),
        Concept(id=TEXTILES, type="MECHANISM", name="Test Kelvar Textiles"),
        Concept(id=TIN, type="MATERIAL", name="Tin"),
        Concept(id=DABU, craftId=OLD, type="MATERIAL", name="Dabu"),
        Concept(id=BLOCK, craftId=OLDER, type="TOOL", name="Wooden block"),
        Concept(id=WEAVE_ALUM, craftId=WEAVE, type="MATERIAL", name="Alum"),
        Concept(id=VAT, craftId=CRAFT, type="PROCESS_STAGE", name="Kelvar vat"),
    ]


def _claim(claim_id: uuid.UUID, subject: uuid.UUID, text: str) -> Claim:
    return Claim(
        id=claim_id,
        subjectType="CONCEPT",
        subjectId=subject,
        predicate="explains",
        text=text,
        evidenceLevel="PROVISIONAL",
        origin="IMPORT",
    )


def _claims() -> list[Claim]:
    return [
        _claim(FAMILY_ALUM, ALUM, "Alum binds the red dye to cotton in a hot bath."),
        _claim(CONTRIBUTED, TEXTILES, "Printers of the family rinse the alum bath in running water."),
        _claim(METAL_TIN, TIN, "Tin coats brass vessels under an alum flux."),
        _claim(OLD_DABU, DABU, "Dabu mud paste resists the alum bath."),
        _claim(OLDER_BLOCK, BLOCK, "The wooden block carries the alum paste to the cloth."),
        _claim(ELSEWHERE, WEAVE_ALUM, "Alum fixes the red of the weave."),
        _claim(
            REGISTERED,
            VAT,
            "Among the salts, gums, earths and roots of the dye bath there is also some indigo.",
        ),
        *(
            _claim(claim, VAT, f"Indigo, indigo and more indigo fill vat {n}.")
            for n, claim in enumerate(PRINTED)
        ),
    ]


async def searched(session: AsyncSession, question: str, **extra: object) -> KnowledgeHits:
    query = KnowledgeQuery.model_validate({"craftSlug": SLUG, "text": question, "mode": "HYBRID", **extra})
    return await StoredKnowledgeSearch(session, embed=FixedEmbedder()).search(query)


def ids(found: KnowledgeHits) -> set[uuid.UUID]:
    return {hit.claim_id for hit in found.claims}


async def test_a_craft_reads_its_family_science_by_the_link_its_page_uses(session: AsyncSession) -> None:
    found = await searched(session, "Why does Kelvar Print use alum?", limit=50)
    assert {FAMILY_ALUM, CONTRIBUTED} <= ids(found)
    assert ids(found).isdisjoint({METAL_TIN, ELSEWHERE})
    named = {hit.claim_id for hit in found.claims if hit.entity_rank is not None}
    assert FAMILY_ALUM in named and ELSEWHERE not in named


async def test_a_craft_reads_the_knowledge_of_the_crafts_merged_into_it(session: AsyncSession) -> None:
    assert await merged_into(session, CRAFT) == (OLD, OLDER)
    assert await merged_into(session, WEAVE) == ()
    found = await searched(session, "What do the dabu paste and the wooden block do?", limit=50)
    assert {OLD_DABU, OLDER_BLOCK} <= ids(found)
    named = {hit.claim_id for hit in found.claims if hit.entity_rank is not None}
    assert {OLD_DABU, OLDER_BLOCK} <= named


async def test_a_search_kept_to_source_kinds_fills_its_limit_with_them(session: AsyncSession) -> None:
    unkept = await searched(session, "What goes into the indigo vat?", limit=12)
    assert ids(unkept) == set(PRINTED)
    kept = await searched(session, "What goes into the indigo vat?", limit=12, sourceKinds=["GI_JOURNAL"])
    assert [hit.claim_id for hit in kept.claims] == [REGISTERED]


async def test_a_search_told_to_skip_passages_runs_no_passage_ranking(session: AsyncSession) -> None:
    await replace_source_chunks(session, BOOK, "Indigo is reduced in the vat.\n\nThe cloth is dipped.")
    await embed_pending(session, FixedEmbedder(), batch_size=500)
    read = await searched(session, "Where does the indigo go?")
    assert {hit.source_id for hit in read.chunks} == {BOOK}
    skipped = await searched(session, "Where does the indigo go?", passages=False)
    assert skipped.chunks == () and ids(skipped) == ids(read)
