from __future__ import annotations

import uuid
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import and_, exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CandidateCheck, Chunk, Claim, ClaimSource, Concept, Craft, Source
from app.models.enums import DISCIPLINES
from app.research.candidate_gates import SOURCE_GATE, Candidate, CitedSource, GateOutcome, duplicate_outcome
from app.research.write_back import WRITE_BACK_ORIGIN

from .candidate_gates import first_gates
from .candidate_store import SqlHeldFacts, craft_subject
from .write_back_report import ReportWindow, report_window

__all__ = ["AUDITED_MAX", "LISTED_MAX", "AuditedClaim", "gate_less_write_backs"]

AUDITED_MAX = 500
LISTED_MAX = 50
STATEMENT_MAX_CHARS = 1000
TEXT_SHOWN_CHARS = 160
PASSED_QUOTE = "PASS"
CONCEPT_SUBJECT = "CONCEPT"
UNKEPT = "the source's text was not kept with the research"
UNCITED = "it cites no source"


@dataclass(frozen=True)
class AuditedClaim:
    claim_id: uuid.UUID
    created_at: datetime
    status: str
    text: str
    outcomes: tuple[GateOutcome, ...]

    @property
    def refused_at(self) -> GateOutcome | None:
        return next((outcome for outcome in self.outcomes if not outcome.passed), None)

    def as_dict(self) -> dict[str, Any]:
        refused = self.refused_at
        return {
            "claimId": str(self.claim_id),
            "createdAt": self.created_at.isoformat(),
            "status": self.status,
            "text": self.text[:TEXT_SHOWN_CHARS],
            "wouldPass": refused is None,
            "refusedAt": None if refused is None else refused.gate,
            "reason": None if refused is None else refused.reasons[0],
        }


async def gate_less_write_backs(session: AsyncSession, *, now: datetime, days: int) -> dict[str, Any]:
    window = report_window(now, days)
    audited = [await _audited(session, claim, slug) for claim, slug in await _gate_less(session, window)]
    refused = Counter(claim.refused_at.gate for claim in audited if claim.refused_at is not None)
    return {
        "window": {**window.as_dict(), "days": days},
        "claims": len(audited),
        "byStatus": dict(sorted(Counter(claim.status for claim in audited).items())),
        "wouldPass": sum(1 for claim in audited if claim.refused_at is None),
        "wouldBeRefusedAt": dict(sorted(refused.items())),
        "listed": [claim.as_dict() for claim in audited[:LISTED_MAX]],
    }


async def _gate_less(session: AsyncSession, window: ReportWindow) -> list[tuple[Claim, str | None]]:
    checked = exists(select(CandidateCheck.id).where(CandidateCheck.claimId == Claim.id))
    rows = await session.execute(
        select(Claim, Craft.slug)
        .outerjoin(Concept, and_(Claim.subjectType == CONCEPT_SUBJECT, Claim.subjectId == Concept.id))
        .outerjoin(Craft, Craft.id == Concept.craftId)
        .where(Claim.origin == WRITE_BACK_ORIGIN, window.holds(Claim.createdAt), ~checked)
        .order_by(Claim.createdAt.desc(), Claim.id)
        .limit(AUDITED_MAX)
    )
    return [(claim, slug) for claim, slug in rows.all()]


async def _audited(session: AsyncSession, claim: Claim, craft_slug: str | None) -> AuditedClaim:
    field = claim.field if claim.field in DISCIPLINES else None
    candidate = Candidate(ref=str(claim.id), statement=claim.text[:STATEMENT_MAX_CHARS], field=field)
    sources = await _cited_sources(session, claim.id)
    outcomes = list(first_gates(candidate, sources)) if sources else [_uncited()]
    if all(outcome.passed for outcome in outcomes):
        outcomes.append(await _duplicate(session, candidate, claim.id, craft_slug))
    return AuditedClaim(
        claim_id=claim.id,
        created_at=claim.createdAt,
        status=claim.status,
        text=claim.text,
        outcomes=tuple(outcomes),
    )


async def _cited_sources(session: AsyncSession, claim_id: uuid.UUID) -> list[CitedSource]:
    rows = (
        await session.execute(
            select(ClaimSource.quote, ClaimSource.quoteCheck, Source)
            .join(Source, Source.id == ClaimSource.sourceId)
            .where(ClaimSource.claimId == claim_id)
            .order_by(ClaimSource.createdAt, ClaimSource.id)
        )
    ).all()
    sources: dict[uuid.UUID, Source] = {}
    quotes: dict[uuid.UUID, list[str]] = {}
    for quote, check, source in rows:
        sources[source.id] = source
        quotes.setdefault(source.id, [])
        if quote and check == PASSED_QUOTE and quote not in quotes[source.id]:
            quotes[source.id].append(quote)
    texts = await _kept_texts(session, list(sources))
    return [_cited(source, quotes[source_id], texts.get(source_id)) for source_id, source in sources.items()]


async def _kept_texts(session: AsyncSession, source_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not source_ids:
        return {}
    rows = await session.execute(
        select(Chunk.sourceId, Chunk.text).where(Chunk.sourceId.in_(source_ids)).order_by(Chunk.ordinal)
    )
    parts: dict[uuid.UUID, list[str]] = {}
    for source_id, text in rows.all():
        parts.setdefault(source_id, []).append(text)
    return {source_id: " ".join(found) for source_id, found in parts.items()}


def _uncited() -> GateOutcome:
    return GateOutcome(gate=SOURCE_GATE, passed=False, reasons=[UNCITED])


def _cited(source: Source, quotes: list[str], text: str | None) -> CitedSource:
    return CitedSource(
        url=source.url or f"source:{source.id}",
        quotes=quotes,
        text=text,
        unread=None if text is not None else UNKEPT,
        grade=source.reliability,
        declared_licence=source.licence,
    )


async def _duplicate(
    session: AsyncSession, candidate: Candidate, claim_id: uuid.UUID, craft_slug: str | None
) -> GateOutcome:
    held = SqlHeldFacts(session, await craft_subject(session, craft_slug))
    twins = [fact for fact in await held.twins(candidate.field, candidate.statement) if fact.id != claim_id]
    return duplicate_outcome(
        candidate, twin=twins[0] if twins else None, close=(), comparisons=None, vectored=False
    )
