import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Answer, Claim, ClaimSource, Concept
from app.research.composition import ComposedSentence, QuotedSpan
from app.services.research_write_back import compared_crafts, sentence_claim_ids

from ..craft_fixtures import unit
from .write_back_seed import (
    ABSTRACT_ID,
    ALUM_CONCEPT,
    FIGURE_KEY,
    FIGURE_QUOTE,
    FIGURE_TEXT,
    IMPORTED,
    PAGE_ID,
    QUIET,
    WASH_QUOTE,
    answer,
    expected_claim_id,
    key,
    said,
    seeded_session,
    write,
)

pytestmark = pytest.mark.db

CLOSED_REASON = "says the same and review closed it as {status}; research never writes a closed fact back"


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in seeded_session():
        yield opened


async def closed_fact(
    session: AsyncSession, name: str, text: str, status: str, *, field: str, vector: list[float] | None = None
) -> uuid.UUID:
    claim_id = key(name)
    session.add(
        Claim(
            id=claim_id,
            subjectType="CONCEPT",
            subjectId=ALUM_CONCEPT,
            predicate="states",
            text=text,
            evidenceLevel="PROVISIONAL",
            origin="LIVE_RESEARCH",
            status=status,
            field=field,
            embedding=vector,
        )
    )
    await session.flush()
    return claim_id


@pytest.mark.parametrize("status", ["REJECTED", "RETRACTED", "SUPERSEDED", "WITHDRAWN"])
async def test_research_never_writes_back_a_fact_review_closed_whatever_its_field(
    session: AsyncSession, status: str
) -> None:
    closed = await closed_fact(session, f"closed-{status}", FIGURE_TEXT, status, field="PROCESS")
    composed = answer(said(FIGURE_TEXT, ABSTRACT_ID, FIGURE_QUOTE))
    stored = await write(session, composed)
    assert stored.results == ()
    (skipped,) = stored.skipped
    reason = CLOSED_REASON.format(status=status.lower())
    assert skipped.reason == f"refused at the DUPLICATE gate: fact {closed} {reason}"
    assert sentence_claim_ids(composed, stored) == ((),)
    assert await session.get(Claim, expected_claim_id(FIGURE_KEY)) is None


async def test_a_closed_fact_in_nearly_the_same_words_is_refused_by_its_vector(session: AsyncSession) -> None:
    close = "Zelvar mordant baths held 8 g/L of alum and were heated to 60 °C."
    rejected = await closed_fact(session, "near-twin", close, "REJECTED", field="MATERIALS", vector=unit(1.0))
    other = "Zelvar mordant baths held 8 g/L alum and were heated to 90 °C."
    await closed_fact(session, "other-figure", other, "RETRACTED", field="MATERIALS", vector=unit(1.0))
    stored = await write(session, answer(said(FIGURE_TEXT, ABSTRACT_ID, FIGURE_QUOTE)))
    assert stored.results == ()
    (skipped,) = stored.skipped
    assert skipped.reason.endswith(f"fact {rejected} {CLOSED_REASON.format(status='rejected')}")


async def test_a_write_back_review_rejected_gains_no_citation_when_research_meets_it_again(
    session: AsyncSession,
) -> None:
    first = await write(session, answer(said(FIGURE_TEXT, ABSTRACT_ID, FIGURE_QUOTE)))
    (written,) = first.results
    await session.execute(update(Claim).where(Claim.id == written.claim_id).values(status="REJECTED"))
    again = ComposedSentence(
        text=FIGURE_TEXT,
        evidence_ids=[ABSTRACT_ID, PAGE_ID],
        spans=[QuotedSpan(ref=ABSTRACT_ID, text=FIGURE_QUOTE), QuotedSpan(ref=PAGE_ID, text=WASH_QUOTE)],
    )
    stored = await write(session, answer(again), found_by="BACKGROUND", answer_id=None)
    assert stored.results == ()
    reason = CLOSED_REASON.format(status="rejected")
    assert [s.reason for s in stored.skipped] == [
        f"refused at the DUPLICATE gate: fact {written.claim_id} {reason}"
    ]
    sources = await session.scalars(
        select(ClaimSource.sourceId).where(ClaimSource.claimId == written.claim_id)
    )
    assert list(sources) == [IMPORTED]


async def test_a_sentence_naming_the_compared_craft_is_filed_under_it(session: AsyncSession) -> None:
    compared = {"slug": "Zelvar-Quiet", "name": "Zelvar Quiet", "path": "/crafts/Zelvar-Quiet"}
    asked = key("compared-answer")
    session.add(
        Answer(
            id=asked,
            question="How do Zelvar Dye and Zelvar Quiet differ?",
            mode="HYBRID",
            understanding={
                "craft": {"slug": "Zelvar-Dye", "name": "Zelvar Dye", "path": "/crafts/Zelvar-Dye"},
                "compared": [compared],
            },
        )
    )
    await session.flush()
    assert [craft.slug for craft in await compared_crafts(session, asked)] == ["Zelvar-Quiet"]
    text = "Zelvar Quiet printers saw the red withstand 20 washes."
    stored = await write(session, answer(said(text, PAGE_ID, WASH_QUOTE)), answer_id=asked)
    claim_id = expected_claim_id(text.casefold().rstrip("."), craft_slug="Zelvar-Quiet")
    assert [(result.claim_id, result.created) for result in stored.results] == [(claim_id, True)]
    claim = await session.get(Claim, claim_id)
    concept = await session.get(Concept, claim.subjectId)
    assert (concept.craftId, concept.type, concept.name) == (QUIET, "MATERIAL", "alum")
