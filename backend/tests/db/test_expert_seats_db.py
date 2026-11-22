import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass, field, replace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Answer, Chunk, Claim, ClaimSource, Concept, Craft, Source
from app.research.expert_panel import EXPERT_PANEL
from app.research.retrieval import ChunkHit, ClaimHit, KnowledgeHits, KnowledgeQuery
from app.services.artisan_seat import HeardQuote, artisan_take, attributed, stored_voices
from app.services.builder_interface import BuildAsk, BuilderTools
from app.services.seat_search import stored_seat_search
from tests.db.field_voices_rows import (
    KeptStore,
    ajrakh,
    cited_claim,
    count,
    public_chunk,
    rolled_back,
    stored_recording,
    synced,
)
from tests.experts.fixtures import QUESTION, build_ask

pytestmark = pytest.mark.db

KEPT_QUOTE = "We grind the alum with tamarind seed"
ARTISAN = "Asha Demo"
RECORDED_CRAFT = "Ajrakh Print of Kutch"
DISTRICT = "Kachchh"
PAPER_CLAIM = "Alum fixes the red of the madder dye on Ajrakh cloth."


@dataclass
class FakeRetriever:
    hits: KnowledgeHits
    queries: list[KnowledgeQuery] = field(default_factory=list)

    async def search(self, query: KnowledgeQuery) -> KnowledgeHits:
        self.queries.append(query)
        return self.hits


def same_session(session: AsyncSession) -> Callable[[], AbstractAsyncContextManager[AsyncSession]]:
    @asynccontextmanager
    async def opened() -> AsyncIterator[AsyncSession]:
        yield session

    return opened


def tools_for(session: AsyncSession, hits: KnowledgeHits) -> BuilderTools:
    return BuilderTools(
        sessions=same_session(session),
        live=None,
        plan_model=None,
        compose_model=None,
        retriever=FakeRetriever(hits),
    )


def chunk_hit(chunk: Chunk) -> ChunkHit:
    return ChunkHit(
        chunk_id=chunk.id,
        source_id=chunk.sourceId,
        ordinal=chunk.ordinal,
        locator=chunk.locator,
        text=chunk.text,
        score=1.0,
        source_kind="FIELD_TESTIMONY",
    )


async def heard_chunk(session: AsyncSession) -> tuple[Craft, Source, Chunk]:
    await synced(session, KeptStore())
    craft = await ajrakh(session)
    recording = await stored_recording(session)
    source = await session.get(Source, recording.sourceId)
    assert source is not None
    return craft, source, await public_chunk(session, recording.sourceId, KEPT_QUOTE)


async def stored_answer(session: AsyncSession, craft: Craft) -> uuid.UUID:
    answer = Answer(id=uuid.uuid4(), question=QUESTION, mode="HYBRID", craftId=craft.id)
    session.add(answer)
    await session.flush()
    return answer.id


async def test_the_artisan_seat_reads_the_speaker_craft_and_district_of_a_quoted_turn() -> None:
    async with rolled_back() as session:
        craft, source, chunk = await heard_chunk(session)
        claim = await cited_claim(session, craft, source.id, KEPT_QUOTE)
        voices = stored_voices(
            tools_for(session, KnowledgeHits(craft_slug=craft.slug, chunks=(chunk_hit(chunk),))),
            enabled=lambda: True,
        )
        heard = await voices(build_ask(("HISTORIAN",), depth="EXPERT"))
        assert heard.quotes == (HeardQuote(claim, KEPT_QUOTE, ARTISAN, RECORDED_CRAFT, DISTRICT),)
        assert heard.cited.views[claim].text == f"The artisan says: {KEPT_QUOTE}."
        assert heard.cited.sources[str(source.id)]["kind"] == "FIELD_TESTIMONY"
        (sentence,) = artisan_take(heard, set())
        assert (
            sentence.text
            == attributed(heard.quotes[0])
            == (
                f"In one artisan's account, {ARTISAN}, who practises {RECORDED_CRAFT} in {DISTRICT} district, "
                f"said: “{KEPT_QUOTE}”"
            )
        )
        assert sentence.claim_ids == (claim,)


async def test_an_uncited_artisan_turn_becomes_a_quoted_claim_the_seat_quotes_once() -> None:
    async with rolled_back() as session:
        craft, source, chunk = await heard_chunk(session)
        assert chunk.text.startswith(KEPT_QUOTE) and len(chunk.text) <= 300
        hits = KnowledgeHits(craft_slug=craft.slug, chunks=(chunk_hit(chunk),))
        voices = stored_voices(tools_for(session, hits), enabled=lambda: True)
        ask = build_ask(("CHEMIST",), discipline="PROCESS", depth="EXPERT")
        ask = replace(ask, answer_id=await stored_answer(session, craft))
        whole = " ".join(chunk.text.split())
        assert await count(session, ClaimSource, ClaimSource.sourceId == source.id) == 0
        heard = await voices(ask)
        (quote,) = heard.quotes
        assert quote == HeardQuote(quote.claim_id, whole, ARTISAN, RECORDED_CRAFT, DISTRICT)
        assert quote.claim_id in heard.cited.views
        stored = await session.get(Claim, quote.claim_id)
        assert stored is not None
        assert stored.text == f"An artisan who practises {craft.name} says: “{whole}”"
        assert (stored.evidenceLevel, stored.field, stored.origin) == (
            "PROVISIONAL",
            "PROCESS",
            "LIVE_RESEARCH",
        )
        cite = await session.scalar(select(ClaimSource).where(ClaimSource.claimId == quote.claim_id))
        assert cite is not None
        assert (cite.sourceId, cite.quote, cite.quoteCheck, cite.answerId) == (
            source.id,
            whole,
            "PASS",
            ask.answer_id,
        )
        again = await voices(ask)
        assert [one.claim_id for one in again.quotes] == [quote.claim_id]
        assert await count(session, ClaimSource, ClaimSource.sourceId == source.id) == 1


async def test_a_history_section_writes_no_artisan_turn_back() -> None:
    async with rolled_back() as session:
        craft, source, chunk = await heard_chunk(session)
        hits = KnowledgeHits(craft_slug=craft.slug, chunks=(chunk_hit(chunk),))
        ask = build_ask(("HISTORIAN",), discipline="HISTORY", depth="EXPERT")
        ask = replace(ask, answer_id=await stored_answer(session, craft))
        heard = await stored_voices(tools_for(session, hits), enabled=lambda: True)(ask)
        assert heard.quotes == ()
        assert await count(session, ClaimSource, ClaimSource.sourceId == source.id) == 0


async def paper_claim(session: AsyncSession, craft: Craft) -> tuple[uuid.UUID, Source]:
    paper = Source(
        kind="PAPER", title="Mordants of Kachchh prints", url="https://example.org/mordants", reliability="B"
    )
    concept = Concept(craftId=craft.id, type="PROPERTY", name=f"Alum mordant {uuid.uuid4().hex[:8]}")
    session.add_all([paper, concept])
    await session.flush()
    claim = Claim(
        subjectType="CONCEPT",
        subjectId=concept.id,
        predicate="states",
        text=PAPER_CLAIM,
        evidenceLevel="PROVISIONAL",
        origin="LIVE_RESEARCH",
        status="APPROVED",
    )
    session.add(claim)
    await session.flush()
    session.add(ClaimSource(claimId=claim.id, sourceId=paper.id, quoteCheck="NA", relation="DIRECT"))
    await session.flush()
    return claim.id, paper


def claim_hit(claim_id: uuid.UUID, text: str, rank: int) -> ClaimHit:
    return ClaimHit(
        claim_id=claim_id,
        text=text,
        level="PROVISIONAL",
        subject_type="CONCEPT",
        subject_id=uuid.uuid4(),
        score=1.0 / rank,
    )


async def test_a_seat_keeps_only_found_claims_of_its_own_source_kinds_read_from_the_database() -> None:
    async with rolled_back() as session:
        craft, field_source, _chunk = await heard_chunk(session)
        spoken = await cited_claim(session, craft, field_source.id, KEPT_QUOTE)
        printed, paper = await paper_claim(session, craft)
        hits = KnowledgeHits(
            craft_slug=craft.slug,
            claims=(claim_hit(spoken, KEPT_QUOTE, 1), claim_hit(printed, PAPER_CLAIM, 2)),
        )
        search = stored_seat_search(tools_for(session, hits))
        ask: BuildAsk = build_ask(("CHEMIST",), discipline="CHEMISTRY", depth="EXPERT")
        evidence = await search(ask, (EXPERT_PANEL["CHEMIST"],), set())
        assert [view.id for view in evidence.found["CHEMIST"]] == [printed]
        assert evidence.cited.views[printed].text == PAPER_CLAIM
        assert evidence.cited.views[spoken].text == f"The artisan says: {KEPT_QUOTE}."
        kinds = {source_id: ref["kind"] for source_id, ref in evidence.cited.sources.items()}
        assert kinds == {str(paper.id): "PAPER", str(field_source.id): "FIELD_TESTIMONY"}
