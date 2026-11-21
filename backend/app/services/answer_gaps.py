from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Answer, AnswerVerdict, ClaimSource
from app.research.open_work_gaps import FieldReading, Verdict, answer_verdict
from app.research.retrieval import ClaimHit
from app.research.vocabulary import FACT_LEVELS
from app.retrieval.fusion import RRF_K

from .answer_sections import SectionOutcome
from .claim_holds import FAILED_QUOTE

__all__ = [
    "ANSWERING_RELEVANCE",
    "SINGLE_RANKING_SCORE",
    "FieldReading",
    "answer_readings",
    "failed_claims",
    "fused_low",
    "record_verdict",
    "retrieval_low",
]

SINGLE_RANKING_SCORE = 1 / (RRF_K + 1)
ANSWERING_RELEVANCE = 0.5


def answer_readings(outcomes: Sequence[SectionOutcome]) -> tuple[FieldReading, ...]:
    return tuple(_reading(outcome) for outcome in outcomes if outcome.failure is None)


def retrieval_low(hits: Sequence[ClaimHit]) -> bool:
    relevance = [hit.relevance_score for hit in hits if hit.relevance_score is not None]
    if relevance:
        return max(relevance) < ANSWERING_RELEVANCE
    return fused_low([hit.score for hit in hits])


def fused_low(scores: Sequence[float]) -> bool:
    return not scores or max(scores) <= SINGLE_RANKING_SCORE


async def failed_claims(session: AsyncSession, claim_ids: Sequence[uuid.UUID]) -> frozenset[uuid.UUID]:
    if not claim_ids:
        return frozenset()
    rows = await session.scalars(
        select(ClaimSource.claimId)
        .where(ClaimSource.claimId.in_(list(claim_ids)), ClaimSource.quoteCheck == FAILED_QUOTE)
        .distinct()
    )
    return frozenset(rows.all())


async def record_verdict(
    session: AsyncSession, answer_id: uuid.UUID, readings: Sequence[FieldReading]
) -> Verdict | None:
    if not readings:
        return None
    cited = [claim for reading in readings for claim in reading.claim_ids]
    verdict = answer_verdict(readings, await failed_claims(session, cited))
    craft_id = await session.scalar(select(Answer.craftId).where(Answer.id == answer_id))
    session.add(
        AnswerVerdict(
            answerId=answer_id,
            craftId=craft_id,
            verdict=verdict.verdict,
            fields=list(verdict.fields),
            lacking=list(verdict.lacking),
            lacks=list(verdict.lacks),
            sentences=verdict.sentences,
        )
    )
    return verdict


def _reading(outcome: SectionOutcome) -> FieldReading:
    sentences = {
        sentence.text
        for block in outcome.blocks
        for sentence in block.cited_sentences()
        if sentence.level in FACT_LEVELS
    }
    researched = bool(outcome.packs)
    hits = [hit for pack in outcome.packs for hit in pack.stored.claims]
    return FieldReading(
        field=outcome.spec.discipline,
        sentences=len(sentences),
        retrieval_low=researched and retrieval_low(hits),
        claim_ids=tuple(outcome.claim_ids),
    )
