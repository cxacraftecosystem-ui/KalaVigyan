import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ArticleSection, Claim, ClaimSource, Concept
from app.research.monograph_document import MonographDocument
from app.services.monograph_generated import generated_document

from .closed_quotes import CLOSED_QUOTE, quote_closed, store_closed_sources
from .page_documents_seed import CRAFT, CRAFT_SLUG, seed
from .testimony_seed import rolled_back_session

pytestmark = pytest.mark.db

PAPER = uuid.UUID("9d0c0000-0000-4000-8000-000000000007")
CRAFT_CLAIM = uuid.UUID("9d0c0000-0000-4000-8000-0000000000c1")
FIELD_CHAPTERS = {
    "OVERVIEW": "glance",
    "PROCESS": "made",
    "CHEMISTRY": "chem",
    "PHYSICS": "chem",
    "MATERIALS": "made",
    "GEOGRAPHY": "why",
    "GEOLOGY": "why",
    "CLIMATE": "why",
    "ECOLOGY": "why",
    "BOTANY": "chem",
    "HISTORY": "history",
    "ECONOMICS": "market",
    "DESIGN": "people",
    "HEALTH": "made",
    "SOCIETY": "people",
    "POLICY": "market",
}
CLOSED_FIELD = "HEALTH"
WRITTEN_TEXT = "Printers sold the printed cloth at the weekly market of the town."


def key(name: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"test-curated-listed-facts/{name}")


TRADITION = key("tradition")
WRITTEN = key("written")


def fact_text(field: str) -> str:
    return f"A contributor found a {field.lower()} fact about the printed cloth."


def contributed(claim_id: uuid.UUID, text: str, field: str) -> Claim:
    return Claim(
        id=claim_id,
        subjectType="CONCEPT",
        subjectId=TRADITION,
        predicate="states",
        text=text,
        evidenceLevel="PROVISIONAL",
        origin="CONTRIBUTION",
        field=field,
    )


def cited_on_paper(claim_id: uuid.UUID) -> ClaimSource:
    return ClaimSource(claimId=claim_id, sourceId=PAPER, quote=None, locator="p. 4", quoteCheck="NA")


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in rolled_back_session():
        await seed(opened)
        await store_closed_sources(opened)
        opened.add(Concept(id=TRADITION, craftId=CRAFT, type="TRADITION", name="The printing tradition"))
        await opened.flush()
        opened.add_all([contributed(key(field), fact_text(field), field) for field in FIELD_CHAPTERS])
        opened.add(contributed(WRITTEN, WRITTEN_TEXT, "ECONOMICS"))
        await opened.flush()
        opened.add_all([cited_on_paper(key(field)) for field in FIELD_CHAPTERS if field != CLOSED_FIELD])
        opened.add(cited_on_paper(WRITTEN))
        await opened.flush()
        await quote_closed(opened, [key(CLOSED_FIELD)])
        sentences = [{"text": WRITTEN_TEXT, "claimIds": [str(WRITTEN)]}]
        opened.add(
            ArticleSection(
                field="ECONOMICS", version=1, status="PUBLISHED", sentences=sentences, craftId=CRAFT
            )
        )
        await opened.flush()
        yield opened


def citing(document: MonographDocument, claim_id: uuid.UUID) -> list[str]:
    return [ref for ref, unit in document.content.units.items() if str(claim_id) in unit.claim_ids]


def chapter_refs(document: MonographDocument, chapter: str) -> list[str]:
    return [entry.ref for entry in document.content.layout if entry.chapter == chapter]


async def curated_document(session: AsyncSession) -> MonographDocument:
    document = await generated_document(session, "craft", CRAFT_SLUG)
    assert document is not None
    return document


async def test_a_curated_craft_lists_each_contributed_fact_in_the_chapter_of_its_field(
    session: AsyncSession,
) -> None:
    document = await curated_document(session)
    units = document.content.units
    placed = {
        field: [
            (units[ref].tag, units[ref].chapter, units[ref].field) for ref in citing(document, key(field))
        ]
        for field in FIELD_CHAPTERS
    }
    assert placed == {field: [("li", chapter, field)] for field, chapter in FIELD_CHAPTERS.items()}
    for field, chapter in FIELD_CHAPTERS.items():
        (ref,) = citing(document, key(field))
        assert ref in chapter_refs(document, chapter)
    assert document.version == 4


async def test_a_listed_fact_follows_its_field_s_curated_sentences_or_its_field_s_heading(
    session: AsyncSession,
) -> None:
    document = await curated_document(session)
    units = document.content.units
    market = chapter_refs(document, "market")
    (written,) = citing(document, WRITTEN)
    (economics,) = citing(document, key("ECONOMICS"))
    assert units[written].tag == "p"
    assert market.index(written) < market.index(economics)
    chem = chapter_refs(document, "chem")
    (sentence,) = [ref for ref in chem if units[ref].claim_ids == [str(CRAFT_CLAIM)]]
    (chemistry,) = citing(document, key("CHEMISTRY"))
    assert chem.index(sentence) < chem.index(chemistry)
    made = chapter_refs(document, "made")
    heading = next(ref for ref in made if units[ref].nodes == ["Health and safety"])
    (health,) = citing(document, key(CLOSED_FIELD))
    assert made.index(heading) < made.index(health)


async def test_a_fact_a_curated_sentence_cites_is_written_once_and_a_closed_source_is_cited_unquoted(
    session: AsyncSession,
) -> None:
    document = await curated_document(session)
    units = document.content.units
    assert [units[ref].tag for ref in citing(document, WRITTEN)] == ["p"]
    (health,) = citing(document, key(CLOSED_FIELD))
    quotes = document.content.citations[health]
    assert [(document.content.sources[quote.source].title, quote.quote) for quote in quotes] == [
        ("A closed monograph on alum", None)
    ]
    assert CLOSED_QUOTE not in document.model_dump_json()
