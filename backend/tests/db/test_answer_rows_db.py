import json
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import request_id_scope
from app.models import Answer, AnswerCitation, AnswerSentence, AnswerTrace, Claim
from app.research.explainer import Explainer
from app.research.sections import AnswerPlans
from app.services.answer_steps import TracedStep
from app.services.answering import AnswerAsk

from .write_back_seed import UNDERSTOOD, answer_store, seeded_session

pytestmark = pytest.mark.db

REPO = Path(__file__).resolve().parents[3]
REQUEST = "answer-rows-request-0001"
PLANNED = TracedStep(step="status", ms=12, detail={"step": "PLANNING", "message": "Planning the research"})


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in seeded_session():
        yield opened


def golden(answer_id: Any) -> Explainer:
    data = json.loads((REPO / "shared" / "explainer.document.golden.json").read_text(encoding="utf-8"))
    return Explainer.model_validate({**data, "answerId": str(answer_id)})


async def counted(session: AsyncSession, model: Any, column: Any, answer_id: Any) -> int:
    return int(await session.scalar(select(func.count()).select_from(model).where(column == answer_id)) or 0)


async def kept_claims(session: AsyncSession, explainer: Explainer) -> list[str]:
    cited = [
        citation.claim_id
        for section in explainer.sections
        for each in section.blocks
        for sentence in each.shown_sentences()
        for citation in sentence.citations
    ]
    ids = {uuid.UUID(claim) for claim in cited}
    stored = {str(claim) for claim in await session.scalars(select(Claim.id).where(Claim.id.in_(ids)))}
    return sorted(claim if claim in stored else "None" for claim in cited)


async def test_a_finished_answer_keeps_its_sentences_citations_steps_and_request(
    session: AsyncSession,
) -> None:
    store = answer_store(session)
    ask = AnswerAsk(question="Why does alum keep Zelvar red?", depth="DETAILED")
    with request_id_scope(REQUEST):
        answer_id = await store.begin(ask, UNDERSTOOD)
        await store.finish(
            answer_id,
            asked_at=ask.asked_at,
            plans=AnswerPlans(sections=[]),
            claim_ids=[],
            explainer=golden(answer_id),
            steps=[PLANNED],
        )
    row = await session.get(Answer, answer_id)
    await session.refresh(row)
    assert row.requestId == REQUEST
    assert await counted(session, AnswerSentence, AnswerSentence.answerId, answer_id) == 12
    cited = (
        select(func.count())
        .select_from(AnswerCitation)
        .join(AnswerSentence)
        .where(AnswerSentence.answerId == answer_id)
    )
    assert await session.scalar(cited) == 16
    stored = (
        await session.scalars(
            select(AnswerCitation.claimId).join(AnswerSentence).where(AnswerSentence.answerId == answer_id)
        )
    ).all()
    assert sorted(str(claim) for claim in stored) == await kept_claims(session, golden(answer_id))
    (trace,) = (await session.scalars(select(AnswerTrace).where(AnswerTrace.answerId == answer_id))).all()
    assert (trace.step, trace.ordinal, trace.ms, trace.detail) == ("status", 0, 12, dict(PLANNED.detail))
