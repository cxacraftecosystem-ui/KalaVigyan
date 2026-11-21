from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models import Claim
from app.research.candidate_gates import Candidate, CitedSource
from app.research.embedding import TextEmbedder
from app.research.evidence import SourceDocument
from app.research.review_switch import RESEARCH, Placement, placement
from app.research.structured import StructuredModel
from app.research.write_back import ClaimWriteBack, WriteBackCitation, WriteBackResult

from . import app_settings
from .candidate_gates import (
    NOVELTY_LEFT_UNJUDGED,
    GateRun,
    HeldFacts,
    LaterGates,
    first_gates,
    gate_run,
    later_gates,
)
from .candidate_store import CLOSED_STATUSES, SqlHeldFacts, craft_subject
from .candidate_writes import mark_sources_differ, record_checks
from .write_back_closed import (
    KeptVectors,
    by_craft,
    closed_by_id,
    closed_refusals,
    kept_vectors,
    statement_vectors,
    stored_statuses,
)
from .write_back_plan import SkippedSentence

__all__ = [
    "GatedWriteBack",
    "gate_write_back",
    "record_write_back_runs",
    "research_placement",
    "write_back_later_gates",
]

logger = logging.getLogger(__name__)

PASSED_QUOTE = "PASS"


@dataclass(frozen=True)
class GatedWriteBack:
    claims: tuple[ClaimWriteBack, ...]
    runs: Mapping[str, GateRun]
    held_instead: tuple[WriteBackResult, ...]
    skipped: tuple[SkippedSentence, ...]


@dataclass(frozen=True)
class _Gating:
    documents: Mapping[str, SourceDocument]
    embed: TextEmbedder | None
    judge: StructuredModel | None


async def research_placement(session: AsyncSession) -> Placement:
    switch = await app_settings.review_switch(session)
    return placement(switch.mode(RESEARCH), proposer_reviews=False)


async def gate_write_back(
    session: AsyncSession,
    claims: Sequence[ClaimWriteBack],
    documents: Mapping[str, SourceDocument],
    *,
    embed: TextEmbedder | None,
    judge: StructuredModel | None,
) -> GatedWriteBack:
    stored = await stored_statuses(session, claims)
    reopened = {key for key, status in stored.items() if status in CLOSED_STATUSES}
    new = [claim for claim in claims if claim.dedupe_key not in stored]
    runs, closed = await _runs(session, new, _Gating(documents, embed, judge))
    runs |= {
        claim.dedupe_key: GateRun(_candidate(claim), (closed_by_id(claim, stored[claim.dedupe_key]),))
        for claim in claims
        if claim.dedupe_key in reopened
    }
    refused = [claim for claim in claims if claim.dedupe_key in runs and not runs[claim.dedupe_key].passed]
    never_instead = closed | reopened
    return GatedWriteBack(
        claims=tuple(
            claim for claim in claims if claim.dedupe_key not in runs or runs[claim.dedupe_key].passed
        ),
        runs=runs,
        held_instead=tuple(
            _instead(claim, runs[claim.dedupe_key])
            for claim in refused
            if claim.dedupe_key not in never_instead and runs[claim.dedupe_key].held_instead
        ),
        skipped=tuple(_skipped(claim, runs[claim.dedupe_key]) for claim in refused),
    )


async def record_write_back_runs(
    session: AsyncSession,
    results: Sequence[WriteBackResult],
    runs: Mapping[str, GateRun],
    *,
    live: bool,
    checked_at: datetime,
) -> int:
    vectored = 0
    for result in results:
        run = runs.get(result.dedupe_key)
        if run is None or not result.created:
            continue
        await record_checks(session, result.claim_id, run.outcomes, checked_at=checked_at)
        if run.vector is not None:
            await session.execute(
                update(Claim).where(Claim.id == result.claim_id).values(embedding=run.vector)
            )
            vectored += 1
        if live:
            await mark_sources_differ(session, result.claim_id)
    return vectored


async def _runs(
    session: AsyncSession, claims: Sequence[ClaimWriteBack], gating: _Gating
) -> tuple[dict[str, GateRun], set[str]]:
    candidates = {claim.dedupe_key: _candidate(claim) for claim in claims}
    first = {
        claim.dedupe_key: first_gates(candidates[claim.dedupe_key], _cited(claim, gating.documents))
        for claim in claims
    }
    passing = [claim for claim in claims if all(outcome.passed for outcome in first[claim.dedupe_key])]
    vectors = await _vectors(gating.embed, passing)
    closed = await closed_refusals(session, passing, vectors)
    open_claims = [claim for claim in passing if claim.dedupe_key not in closed]
    later = await _later(session, open_claims, kept_vectors(open_claims, vectors), gating.judge)
    later |= {key: LaterGates(outcomes=(outcome,), vector=None) for key, outcome in closed.items()}
    return {key: gate_run(candidates[key], first[key], later.get(key)) for key in candidates}, set(closed)


async def _vectors(embed: TextEmbedder | None, claims: Sequence[ClaimWriteBack]) -> dict[str, list[float]]:
    if embed is None:
        return {}
    try:
        return await statement_vectors(embed, claims)
    except AppError as error:
        logger.warning(
            "write-back statements were not embedded, so facts are matched by text only: %s", error
        )
        return {}


async def _later(
    session: AsyncSession,
    claims: Sequence[ClaimWriteBack],
    vectors: KeptVectors,
    judge: StructuredModel | None,
) -> dict[str, LaterGates]:
    embed = vectors if vectors.by_text else None
    found: dict[str, LaterGates] = {}
    for craft_slug, group in by_craft(claims).items():
        store = SqlHeldFacts(session, await craft_subject(session, craft_slug))
        candidates = [_candidate(claim) for claim in group]
        found |= await write_back_later_gates(store, candidates, embed=embed, judge=judge)
    return found


async def write_back_later_gates(
    store: HeldFacts,
    candidates: Sequence[Candidate],
    *,
    embed: TextEmbedder | None,
    judge: StructuredModel | None,
) -> dict[str, LaterGates]:
    try:
        return await later_gates(
            store, candidates, embed=embed, judge=judge, novelty_failure=NOVELTY_LEFT_UNJUDGED
        )
    except AppError as error:
        logger.warning("write-back gates fell back to identical texts only: %s", error)
        return await later_gates(store, candidates, embed=None, judge=None)


def _candidate(claim: ClaimWriteBack) -> Candidate:
    return Candidate(ref=claim.dedupe_key, statement=claim.text, field=claim.stored_field)


def _cited(claim: ClaimWriteBack, documents: Mapping[str, SourceDocument]) -> list[CitedSource]:
    return [_cited_source(citation, documents.get(citation.evidence.id)) for citation in claim.citations]


def _cited_source(citation: WriteBackCitation, document: SourceDocument | None) -> CitedSource:
    item = citation.evidence
    quoted = citation.quote is not None and citation.quote_check == PASSED_QUOTE
    return CitedSource(
        url=item.url,
        quotes=[citation.quote.text] if quoted and citation.quote is not None else [],
        text=document.text if document is not None else None,
        unread=None if document is not None else "the document was not kept with the research",
        grade=item.trust,
        declared_licence=item.licence,
        stated_licence=item.licence,
    )


def _instead(claim: ClaimWriteBack, run: GateRun) -> WriteBackResult:
    return WriteBackResult(dedupe_key=claim.dedupe_key, claim_id=run.held_instead[0], created=False)


def _skipped(claim: ClaimWriteBack, run: GateRun) -> SkippedSentence:
    refused = run.refused_at
    gate = refused.gate if refused is not None else "unknown"
    reason = refused.reasons[0] if refused is not None else "no reason was recorded"
    return SkippedSentence(claim.text, f"refused at the {gate} gate: {reason}")
