import uuid
from collections.abc import AsyncIterator, Callable

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Chunk, Claim, ClaimSource, Source
from app.research.composition import ComposedAnswer, ComposedSection, ComposedSentence, QuotedSpan
from app.research.evidence_pack import EvidencePack
from app.research.retrieval import RESEARCHER_CHUNK_ACL, SIGNED_IN_CHUNK_ACLS, ChunkHit, KnowledgeHits
from app.retrieval.hybrid import StoredKnowledgeSearch
from app.retrieval.indexing import replace_source_chunks
from app.services.craft_resolver import CraftIndexStore
from app.services.research_write_back import store_live_research
from app.voice.passage_store import SqlTurnPassages
from app.voice.passages import PassageTurn, stored_query

from ..composer.fixtures import PLAN
from ..craft_fixtures import FixedEmbedder
from ..research.fixtures import RETRIEVED
from .write_back_seed import ALUM_CONCEPT, ANSWER, ZELVAR, expected_claim_id, key, seeded_session

pytestmark = pytest.mark.db

OPEN_BOOK, CLOSED_PAGE = key("stored-open-book"), key("stored-closed-page")
OPEN_FACT, CLOSED_FACT = key("stored-open-fact"), key("stored-closed-fact")
OPEN_URL = "https://notes.example.org/zelvar-dyeing"
OPEN_TEXT = "Zelvar dyers fix the red dye with alum in a hot mordant bath before printing."
CLOSED_TEXT = "Zelvar dye houses keep the madder bath hot with alum through the whole red dyeing day."
QUOTE = "fix the red dye with alum in a hot mordant bath"
SENTENCE = "Zelvar dyers fix the red dye with alum in a hot mordant bath."
FOLDED = "zelvar dyers fix the red dye with alum in a hot mordant bath"
ASKED = "How do Zelvar dyers keep the red with alum?"


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in seeded_session():
        opened.add_all(
            [
                _source(OPEN_BOOK, "BOOK", "Zelvar dyeing notes", OPEN_URL, "CC BY 4.0"),
                _source(
                    CLOSED_PAGE, "WEB_PAGE", "A Zelvar dye house", "https://dyehouse.example.org/zelvar", None
                ),
            ]
        )
        await opened.flush()
        await replace_source_chunks(opened, OPEN_BOOK, OPEN_TEXT)
        await replace_source_chunks(opened, CLOSED_PAGE, CLOSED_TEXT, acl=RESEARCHER_CHUNK_ACL)
        for fact, source in ((OPEN_FACT, OPEN_BOOK), (CLOSED_FACT, CLOSED_PAGE)):
            opened.add(
                Claim(
                    id=fact,
                    subjectType="CONCEPT",
                    subjectId=ALUM_CONCEPT,
                    predicate="states",
                    text=f"Alum keeps the Zelvar red, says fact {fact.hex[:8]}.",
                    evidenceLevel="PROVISIONAL",
                    origin="IMPORT",
                )
            )
            await opened.flush()
            opened.add(ClaimSource(claimId=fact, sourceId=source, quoteCheck="NA"))
        await opened.flush()
        yield opened


def _source(source_id: uuid.UUID, kind: str, title: str, url: str, licence: str | None) -> Source:
    return Source(
        id=source_id,
        kind=kind,
        title=title,
        authors=["S. Writer"],
        year=2015,
        doi=None,
        url=url,
        publisher=None,
        licence=licence,
        attribution=None,
        reliability="B",
        retrievedAt=RETRIEVED,
    )


def sessions_of(session: AsyncSession) -> Callable[[], AsyncSession]:
    def opened() -> AsyncSession:
        return AsyncSession(bind=session.bind, expire_on_commit=False, autoflush=False)

    return opened


async def chunk_of(session: AsyncSession, source_id: uuid.UUID) -> Chunk:
    return (await session.scalars(select(Chunk).where(Chunk.sourceId == source_id))).one()


def hit_of(chunk: Chunk) -> ChunkHit:
    return ChunkHit(
        chunk_id=chunk.id,
        source_id=chunk.sourceId,
        ordinal=chunk.ordinal,
        locator=chunk.locator,
        text=chunk.text,
        score=0.03,
        source_kind="BOOK",
        source_title="Zelvar dyeing notes",
    )


def said(chunk: Chunk, heading: str) -> ComposedAnswer:
    ref = f"stored_passages:{chunk.id}"
    sentence = ComposedSentence(text=SENTENCE, evidence_ids=[ref], spans=[QuotedSpan(ref=ref, text=QUOTE)])
    return ComposedAnswer(sections=[ComposedSection(heading=heading, sentences=[sentence])])


async def citations_of(session: AsyncSession, claim_id: uuid.UUID) -> list[ClaimSource]:
    return list(await session.scalars(select(ClaimSource).where(ClaimSource.claimId == claim_id)))


def stored_pack(chunk: Chunk) -> EvidencePack:
    return EvidencePack(
        plan=PLAN.model_copy(update={"craft": ZELVAR}),
        degraded=False,
        stored=KnowledgeHits(craft_slug=ZELVAR.slug, chunks=(hit_of(chunk),)),
        coverage=({"facetIndex": 0},),
    )


async def test_an_answer_keeps_a_sentence_citing_a_stored_passage_as_a_claim_of_its_source(
    session: AsyncSession,
) -> None:
    chunk = await chunk_of(session, OPEN_BOOK)
    async with sessions_of(session)() as fresh:
        stored = await store_live_research(
            fresh,
            stored_pack(chunk),
            said(chunk, "Mordant"),
            embed=FixedEmbedder(),
            found_by="ANSWER",
            index=CraftIndexStore(),
            answer_id=ANSWER,
        )
    claim_id = expected_claim_id(FOLDED)
    assert [(result.claim_id, result.created) for result in stored.results] == [(claim_id, True)]
    claim = await session.get(Claim, claim_id)
    assert claim is not None
    assert (claim.subjectId, claim.status, claim.evidenceLevel, claim.field) == (
        ALUM_CONCEPT,
        "IN_REVIEW",
        "PROVISIONAL",
        "MATERIALS",
    )
    (cite,) = await citations_of(session, claim_id)
    assert (cite.sourceId, cite.chunkId, cite.quote, cite.quoteCheck, cite.relation) == (
        OPEN_BOOK,
        chunk.id,
        QUOTE,
        "PASS",
        "DIRECT",
    )
    assert (cite.foundBy, cite.answerId) == ("ANSWER", ANSWER)
    sources = await session.scalar(select(func.count()).select_from(Source).where(Source.url == OPEN_URL))
    assert sources == 1


async def test_a_voice_turn_writes_its_passage_back_before_it_is_cited(session: AsyncSession) -> None:
    chunk = await chunk_of(session, OPEN_BOOK)
    passages = SqlTurnPassages(
        sessions_of(session), index=CraftIndexStore(), embed=FixedEmbedder(), acls=SIGNED_IN_CHUNK_ACLS
    )
    turn = PassageTurn(craft=ZELVAR, mode="HYBRID", concept_id=ALUM_CONCEPT, passages=(hit_of(chunk),))
    written = await passages.written(turn, said(chunk, "Answer"))
    claim_id = expected_claim_id(FOLDED)
    assert written.claims_of == ((claim_id,),)
    view = written.cited.views[claim_id]
    assert [(c["sourceId"], c["quote"]) for c in view.citations] == [(str(OPEN_BOOK), QUOTE)]
    assert str(OPEN_BOOK) in written.cited.sources
    (cite,) = await citations_of(session, claim_id)
    assert (cite.foundBy, cite.answerId, cite.chunkId) == ("VOICE", None, chunk.id)


async def test_a_researcher_only_passage_is_searched_for_a_researcher_and_never_for_a_student(
    session: AsyncSession,
) -> None:
    opened, closed = await chunk_of(session, OPEN_BOOK), await chunk_of(session, CLOSED_PAGE)
    search = StoredKnowledgeSearch(session, embed=FixedEmbedder())
    student = await search.search(stored_query(ZELVAR, ASKED, mode="HYBRID", role="STUDENT"))
    researcher = await search.search(stored_query(ZELVAR, ASKED, mode="HYBRID", role="RESEARCHER"))
    student_chunks = {hit.chunk_id for hit in student.chunks}
    assert opened.id in student_chunks and closed.id not in student_chunks
    assert {opened.id, closed.id} <= {hit.chunk_id for hit in researcher.chunks}
