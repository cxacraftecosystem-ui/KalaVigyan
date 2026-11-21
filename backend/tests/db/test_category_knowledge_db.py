import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.mcp_tools import ToolContext, answer
from app.models import (
    ArticleSection,
    Claim,
    ClaimSource,
    Concept,
    Craft,
    CraftCategory,
    CuratedCategoryClaim,
    Source,
)
from app.services.category_knowledge import category_facts, category_sections
from app.services.craft_resolver import CraftIndexStore
from app.services.open_work_subjects import WorkSubject, subject_by_key

from .testimony_seed import rolled_back_session

pytestmark = pytest.mark.db

SITE = "https://kalavigyan.example"
SLUG = "Category-Facts-Test-Category"
NAME = "Category Facts Test"
CATEGORY = uuid.UUID("7c470000-0000-4000-8000-000000000001")
ALUM = uuid.UUID("7c470000-0000-4000-8000-000000000002")
NAMED = uuid.UUID("7c470000-0000-4000-8000-000000000003")
CRAFT = uuid.UUID("7c470000-0000-4000-8000-000000000004")
CRAFT_CONCEPT = uuid.UUID("7c470000-0000-4000-8000-000000000005")
OPEN_PAPER = uuid.UUID("7c470000-0000-4000-8000-000000000010")
SECRET_LETTER = uuid.UUID("7c470000-0000-4000-8000-000000000011")
CURATED = uuid.UUID("7c470000-0000-4000-8000-0000000000c1")
PROPOSED = uuid.UUID("7c470000-0000-4000-8000-0000000000c2")
SECRET = uuid.UUID("7c470000-0000-4000-8000-0000000000c3")
ELSEWHERE = uuid.UUID("7c470000-0000-4000-8000-0000000000c4")
ALUM_QUOTE = "alum fixes the madder red on the cotton"
CONTEXT_INDEX = CraftIndexStore()


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in rolled_back_session():
        await _seed(opened)
        yield opened


async def _seed(session: AsyncSession) -> None:
    session.add(CraftCategory(id=CATEGORY, slug=SLUG, name=NAME, sortOrder=993))
    session.add(Craft(id=CRAFT, name="Category Facts Test Craft", slug="Category-Facts-Test-Craft"))
    session.add(
        Source(id=OPEN_PAPER, kind="PAPER", title="Mordants on cotton", licence="CC-BY-4.0", year=2018)
    )
    session.add(Source(id=SECRET_LETTER, kind="PAPER", title="A restricted letter", sensitivity="RESTRICTED"))
    await session.flush()
    session.add(Concept(id=ALUM, type="MATERIAL", name="Category facts test alum"))
    session.add(Concept(id=NAMED, type="TRADITION", name=NAME))
    session.add(Concept(id=CRAFT_CONCEPT, craftId=CRAFT, type="MATERIAL", name="Category facts test lac"))
    await session.flush()
    session.add_all(
        [
            _claim(CURATED, ALUM, "Alum fixes the madder red on cotton.", field="CHEMISTRY"),
            _claim(
                PROPOSED,
                NAMED,
                "Printers carried the carved blocks east.",
                field="HISTORY",
                fields=["SOCIETY"],
            ),
            _claim(SECRET, ALUM, "A secret measure of the alum.", field="CHEMISTRY"),
            _claim(ELSEWHERE, CRAFT_CONCEPT, "Lac is pressed onto the turning wood.", field="CHEMISTRY"),
        ]
    )
    await session.flush()
    session.add_all(
        [
            _cite(CURATED, OPEN_PAPER, ALUM_QUOTE),
            _cite(PROPOSED, OPEN_PAPER, None),
            _cite(SECRET, SECRET_LETTER, "weighed by the dyer's own measure"),
            _cite(ELSEWHERE, OPEN_PAPER, None),
            CuratedCategoryClaim(claimId=CURATED, categoryId=CATEGORY, key="C001", discipline="CHEMISTRY"),
            CuratedCategoryClaim(claimId=SECRET, categoryId=CATEGORY, key="C002", discipline="CHEMISTRY"),
        ]
    )
    await session.flush()


def _claim(claim_id: uuid.UUID, concept: uuid.UUID, text: str, **changes: Any) -> Claim:
    return Claim(
        id=claim_id,
        subjectType="CONCEPT",
        subjectId=concept,
        predicate="states",
        text=text,
        evidenceLevel="PROVISIONAL",
        origin="IMPORT",
        **changes,
    )


def _cite(claim_id: uuid.UUID, source_id: uuid.UUID, quote: str | None) -> ClaimSource:
    return ClaimSource(
        claimId=claim_id,
        sourceId=source_id,
        quote=quote,
        locator="p. 7" if quote else None,
        quoteCheck="PASS" if quote else "NA",
        relation="DIRECT",
    )


async def _page(session: AsyncSession) -> WorkSubject:
    return await subject_by_key(session, "category", SLUG)


async def _tool(session: AsyncSession, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    context = ToolContext(session=session, index=CONTEXT_INDEX, site=SITE)
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }
    reply = await answer(request, context)
    assert reply is not None and reply["result"]["isError"] is False, reply
    return reply["result"]["structuredContent"]


async def test_a_category_s_facts_of_one_field_carry_their_quotes_and_open_sources(
    session: AsyncSession,
) -> None:
    found = await category_facts(session, await _page(session), site=SITE, field="CHEMISTRY")
    assert [fact.id for fact in found.facts] == [CURATED]
    (fact,) = found.facts
    assert [(c.source_id, c.quote, c.locator) for c in fact.citations] == [
        (str(OPEN_PAPER), ALUM_QUOTE, "p. 7")
    ]
    assert [(source.id, source.licence) for source in found.sources] == [(str(OPEN_PAPER), "CC-BY-4.0")]
    assert found.craft is None and found.subject is not None
    assert (found.subject.kind, found.subject.slug, found.subject.name) == ("category", SLUG, NAME)
    assert found.page_url == f"{SITE}/categories/{SLUG}"
    assert [task.key for task in found.open_work] == [f"THIN_FIELD:category:{SLUG}:CHEMISTRY"]


async def test_a_category_holds_its_page_s_facts_and_those_proposed_for_it_in_field_order(
    session: AsyncSession,
) -> None:
    every = await category_facts(session, await _page(session), site=SITE)
    assert [fact.id for fact in every.facts] == [CURATED, PROPOSED]
    assert [(entry.field, entry.count) for entry in every.by_field] == [
        ("CHEMISTRY", 1),
        ("HISTORY", 1),
        ("SOCIETY", 1),
    ]
    society = await category_facts(session, await _page(session), site=SITE, field="SOCIETY")
    assert [(fact.id, fact.field, fact.fields) for fact in society.facts] == [
        (PROPOSED, "HISTORY", ["SOCIETY"])
    ]
    assert ELSEWHERE not in {fact.id for fact in every.facts}
    assert str(SECRET_LETTER) not in {source.id for source in every.sources}


async def test_words_rank_a_category_s_facts(session: AsyncSession) -> None:
    ranked = await category_facts(session, await _page(session), site=SITE, query="printers blocks")
    assert [fact.id for fact in ranked.facts] == [PROPOSED, CURATED]
    assert ranked.query == "printers blocks"


async def test_a_category_s_sections_are_its_published_versions(session: AsyncSession) -> None:
    sentences = [{"text": "Alum fixes the madder red on cotton.", "claimIds": [str(CURATED)]}]
    session.add_all(
        [
            ArticleSection(
                categoryId=CATEGORY, field="CHEMISTRY", version=1, status="PUBLISHED", sentences=sentences
            ),
            ArticleSection(
                categoryId=CATEGORY, field="CHEMISTRY", version=2, status="PROPOSED", sentences=sentences
            ),
        ]
    )
    await session.flush()
    one = await category_sections(session, await _page(session), "CHEMISTRY", site=SITE)
    assert one.section is not None and (one.section.subject_kind, one.section.version) == ("category", 1)
    assert one.sections == [] and one.by_field == []
    history = await category_sections(session, await _page(session), "HISTORY", site=SITE)
    assert history.section is None
    every = await category_sections(session, await _page(session), None, site=SITE)
    assert [(section.field, section.version) for section in every.sections] == [("CHEMISTRY", 1)]
    assert [(entry.field, entry.sentences, entry.claims) for entry in every.by_field] == [("CHEMISTRY", 1, 1)]


async def test_get_facts_and_get_page_read_a_category_page_over_mcp(session: AsyncSession) -> None:
    sentences = [{"text": "Alum fixes the madder red on cotton.", "claimIds": [str(CURATED)]}]
    session.add(
        ArticleSection(
            categoryId=CATEGORY, field="CHEMISTRY", version=1, status="PUBLISHED", sentences=sentences
        )
    )
    await session.flush()
    page = {"kind": "category", "slug": SLUG}
    facts = await _tool(session, "get_facts", {"subject": page, "field": "CHEMISTRY"})
    assert [fact["id"] for fact in facts["facts"]] == [str(CURATED)]
    assert facts["subject"]["slug"] == SLUG and "craft" not in facts
    read = await _tool(session, "get_page", {"subject": page, "parts": ["sections"]})
    assert [(section["subjectKind"], section["field"]) for section in read["sections"]] == [
        ("category", "CHEMISTRY")
    ]
    assert read["sections"][0]["sentences"][0]["claimIds"] == [str(CURATED)]
