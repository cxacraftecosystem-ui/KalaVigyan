from collections.abc import AsyncIterator

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Chunk, Claim, ClaimSource, Source
from app.research.evidence import Quote
from app.research.retrieval import EVERY_CHUNK_ACLS, OPEN_CHUNK_ACLS, RESEARCHER_CHUNK_ACL
from app.research.write_back import ClaimWriteBack
from app.retrieval.indexing import embed_written, replace_source_chunks
from app.services.claim_writer import SqlClaimWriter
from app.services.knowledge_view import claims_by_id
from app.services.live_source_store import QuoteChunk, chunk_for_quote, keep_document
from app.sources.adapter import build_document

from ..craft_fixtures import unit
from ..research.fixtures import evidence_item
from .quote_visibility_seed import SLUG, Cite, fact, key, seeded_session

pytestmark = pytest.mark.db

FIRST_PARAGRAPH = " ".join(f"first{n:03d}" for n in range(110))
SECOND_PARAGRAPH = " ".join(f"second{n:03d}" for n in range(100))
SPANNING_QUOTE = " ".join(
    [*(f"first{n:03d}" for n in range(95, 110)), *(f"second{n:03d}" for n in range(10))]
)
CLOSED_URL = "https://dyehouse.example.org/alum-weights"
CLOSED_ITEM = evidence_item(
    id=f"searxng:{CLOSED_URL}",
    adapter="searxng",
    tier="T4",
    sourceType="WEB_PAGE",
    url=CLOSED_URL,
    title="Alum weights at the dye house",
    published=None,
    doi=None,
    licence="All rights reserved",
    trust="C",
    quotes=[Quote(text=SPANNING_QUOTE)],
)
ABSTRACT_TEXT = "Alum mordant baths were heated before dyeing the cotton red."
ABSTRACT_QUOTE = "Alum mordant baths were heated before dyeing"
FULL_TEXT = f"The dye works of Kutch.\n\n{ABSTRACT_TEXT}\n\nThe cloth was then washed in the river."
FIRST_EDITION = "Alum is ground on a stone.\n\nThe dyer boils the alum in water before printing."
EDITED_QUOTE = "The dyer boils the alum in water"
HISTORY = " ".join(f"history{n:03d}" for n in range(108))
MUSEUM_URL = "https://museum.example.org/ajrakh-notes"
CURATED_QUOTE = "Ajrakh cloth is printed on both sides with the same blocks."
NEW_QUOTE = "The printers of Ajrakhpur rinse the cloth in running water."
MUSEUM_TEXT = f"Notes from the museum gallery.\n\n{CURATED_QUOTE}\n\n{NEW_QUOTE}"
MUSEUM_ITEM = evidence_item(
    id=f"searxng:{MUSEUM_URL}",
    adapter="searxng",
    tier="T4",
    sourceType="WEB_PAGE",
    url=MUSEUM_URL,
    title="Museum notes on Ajrakh",
    published=None,
    doi=None,
    licence=None,
    trust="C",
    quotes=[],
)
PAPER, WIKI, MUSEUM = key("paper"), key("wiki"), key("museum")
ABSTRACT_FACT, EDITED_FACT = key("abstract-fact"), key("edited-fact")
CURATED_FACT, NEW_FACT, CHANGED = key("curated-fact"), key("new-fact"), key("changed")


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in seeded_session():
        yield opened


async def chunk_at(session: AsyncSession, source_id: object, ordinal: int) -> object:
    return await session.scalar(select(Chunk.id).where(Chunk.sourceId == source_id, Chunk.ordinal == ordinal))


async def stored_source(session: AsyncSession, source: Source, text: str, **changes: str) -> None:
    session.add(source)
    await session.flush()
    await replace_source_chunks(session, source.id, text, **changes)


def written_claim() -> ClaimWriteBack:
    return ClaimWriteBack.model_validate(
        {
            "craftSlug": SLUG,
            "subject": {"conceptType": "MATERIAL", "conceptName": "Alum"},
            "predicate": "states",
            "text": "The master dyer weighs the alum for each bath.",
            "label": "QUOTED",
            "levelReason": "test",
            "citations": [
                {
                    "evidence": CLOSED_ITEM,
                    "quote": CLOSED_ITEM.quotes[0],
                    "quoteCheck": "PASS",
                    "relation": "DIRECT",
                }
            ],
            "foundBy": "BACKGROUND",
        }
    )


async def test_a_quote_spanning_two_long_paragraphs_rests_on_both_closed_passages(
    session: AsyncSession,
) -> None:
    await keep_document(
        session, build_document(CLOSED_ITEM, f"{FIRST_PARAGRAPH}\n\n{SECOND_PARAGRAPH}", "FULL_TEXT")
    )
    (result,) = await SqlClaimWriter(session).write([written_claim()])
    (cite,) = (await session.scalars(select(ClaimSource).where(ClaimSource.claimId == result.claim_id))).all()
    first = await chunk_at(session, cite.sourceId, 0)
    assert (cite.chunkId, cite.locator) == (first, "paras 1-2")
    assert await chunk_for_quote(session, cite.sourceId, SPANNING_QUOTE) == QuoteChunk(first, "paras 1-2")
    public, _ = await claims_by_id(session, [result.claim_id], acls=OPEN_CHUNK_ACLS)
    researcher, _ = await claims_by_id(session, [result.claim_id], acls=EVERY_CHUNK_ACLS)
    assert (set(public), set(researcher)) == (set(), {result.claim_id})


async def test_a_hyphen_broken_at_a_line_end_is_found_as_one_word(session: AsyncSession) -> None:
    page = Source(id=key("hyphen-page"), kind="WEB_PAGE", title="Iron black")
    await stored_source(session, page, "Iron black is a mor-\ndant print on cotton.")
    found = await chunk_for_quote(session, page.id, "Iron black is a mordant print")
    assert found == QuoteChunk(await chunk_at(session, page.id, 0), "para 1")


async def test_reading_a_closed_full_text_keeps_an_abstract_quote_public_and_the_text_closed(
    session: AsyncSession,
) -> None:
    paper = Source(id=PAPER, kind="PAPER", title="Alum baths", origin="LIVE_RESEARCH")
    await stored_source(session, paper, ABSTRACT_TEXT)
    found = await chunk_for_quote(session, PAPER, ABSTRACT_QUOTE)
    assert found is not None
    await fact(
        session, ABSTRACT_FACT, Cite(PAPER, ABSTRACT_QUOTE, chunk_id=found.chunk_id, locator=found.locator)
    )
    await replace_source_chunks(session, PAPER, FULL_TEXT, acl=RESEARCHER_CHUNK_ACL)
    views, _ = await claims_by_id(session, [ABSTRACT_FACT], acls=OPEN_CHUNK_ACLS)
    assert [(c["quote"], c["locator"]) for c in views[ABSTRACT_FACT].citations] == [
        (ABSTRACT_QUOTE, "paras 1-3")
    ]
    rows = await session.execute(
        select(Chunk.ordinal, Chunk.text, Chunk.acl).where(Chunk.sourceId == PAPER).order_by(Chunk.ordinal)
    )
    assert [tuple(row) for row in rows] == [(0, FULL_TEXT, "RESEARCHER"), (1, ABSTRACT_QUOTE, "PUBLIC")]


async def test_an_edited_page_moves_each_citation_to_the_passage_that_holds_its_quote(
    session: AsyncSession,
) -> None:
    wiki = Source(id=WIKI, kind="ENCYCLOPEDIA", title="Alum", origin="LIVE_RESEARCH")
    await stored_source(session, wiki, FIRST_EDITION)
    found = await chunk_for_quote(session, WIKI, EDITED_QUOTE)
    assert found == QuoteChunk(await chunk_at(session, WIKI, 0), "paras 1-2")
    await fact(session, EDITED_FACT, Cite(WIKI, EDITED_QUOTE, chunk_id=found.chunk_id, locator=found.locator))
    await replace_source_chunks(session, WIKI, f"{HISTORY}\n\n{FIRST_EDITION}")
    row = (
        await session.execute(
            select(ClaimSource.chunkId, ClaimSource.locator).where(ClaimSource.claimId == EDITED_FACT)
        )
    ).one()
    assert (row.chunkId, row.locator) == (await chunk_at(session, WIKI, 1), "paras 2-3")
    assert await chunk_at(session, WIKI, 2) is None


async def test_a_curated_source_read_in_full_keeps_its_curated_quote_public_and_new_quotes_closed(
    session: AsyncSession,
) -> None:
    museum = Source(
        id=MUSEUM, kind="WEB_PAGE", title="Museum notes on Ajrakh", url=MUSEUM_URL, origin="IMPORT"
    )
    await stored_source(session, museum, CURATED_QUOTE)
    await fact(session, CURATED_FACT, Cite(MUSEUM, CURATED_QUOTE))
    await keep_document(session, build_document(MUSEUM_ITEM, MUSEUM_TEXT, "FULL_TEXT"))
    new = await chunk_for_quote(session, MUSEUM, NEW_QUOTE)
    assert new is not None
    await fact(session, NEW_FACT, Cite(MUSEUM, NEW_QUOTE, chunk_id=new.chunk_id, locator=new.locator))
    public, _ = await claims_by_id(session, [CURATED_FACT, NEW_FACT], acls=OPEN_CHUNK_ACLS)
    assert set(public) == {CURATED_FACT}
    assert [c["quote"] for c in public[CURATED_FACT].citations] == [CURATED_QUOTE]
    researcher, _ = await claims_by_id(session, [CURATED_FACT, NEW_FACT], acls=EVERY_CHUNK_ACLS)
    assert set(researcher) == {CURATED_FACT, NEW_FACT}


async def test_a_vector_is_never_stored_for_a_text_that_changed_while_it_was_made(
    session: AsyncSession,
) -> None:
    await fact(session, CHANGED)
    rewritten = "Alum is weighed by eye, a later reading says."

    async def rewriting(texts: list[str]) -> list[list[float]]:
        await session.execute(update(Claim).where(Claim.id == CHANGED).values(text=rewritten))
        return [unit(1.0) for _ in texts]

    counts = await embed_written(session, rewriting, claim_ids=[CHANGED], source_ids=[])
    row = (await session.execute(select(Claim.text, Claim.embedding).where(Claim.id == CHANGED))).one()
    assert (counts.claims, row.text, row.embedding) == (0, rewritten, None)
