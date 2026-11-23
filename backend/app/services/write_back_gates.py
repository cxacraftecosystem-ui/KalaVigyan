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
from app.research.gate_thrift import GateThrift
from app.research.judge_ladder import JudgeLadder
from app.research.review_switch import RESEARCH, Placement, placement
from app.research.write_back import ClaimWriteBack, WriteBackCitation, WriteBackResult

from . import app_settings
from .candidate_gates import (
    NOVELTY_LEFT_UNJUDGED,
    GateRun,
    HeldFacts,
    LaterGates,
    candidate_vectors,
    first_gates,
    gate_run,
    later_gates,
)
from .candidate_store import CLOSED_STATUSES, FactSubject, SqlHeldFacts, subject_title
from .candidate_writes import mark_sources_differ, record_checks
from .write_back_closed import (
    KeptVectors,
    Owner,
    by_owner,
    closed_by_id,
    closed_refusals,
    kept_vectors,
    owner_of,
    owner_subjects,
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
    judge: JudgeLadder | None


@dataclass(frozen=True)
class _Batch:
    claims: tuple[ClaimWriteBack, ...]
    candidates: Mapping[str, Candidate]
    subjects: Mapping[Owner, FactSubject]


async def research_placement(session: AsyncSession) -> Placement:
    switch = await app_settings.review_switch(session)
    return placement(switch.mode(RESEARCH), proposer_reviews=False)


async def gate_write_back(
    session: AsyncSession,
    claims: Sequence[ClaimWriteBack],
    documents: Mapping[str, SourceDocument],
    *,
    embed: TextEmbedder | None,
    judge: JudgeLadder | None,
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
    subjects = await owner_subjects(session, claims)
    candidates = {claim.dedupe_key: _candidate(claim, subjects[owner_of(claim)]) for claim in claims}
    first = {
        claim.dedupe_key: first_gates(candidates[claim.dedupe_key], _cited(claim, gating.documents))
        for claim in claims
    }
    passing = [claim for claim in claims if all(outcome.passed for outcome in first[claim.dedupe_key])]
    vectors = await _vectors(gating.embed, [candidates[claim.dedupe_key] for claim in passing])
    closed = await closed_refusals(session, passing, vectors, subjects)
    batch = _Batch(
        claims=tuple(claim for claim in passing if claim.dedupe_key not in closed),
        candidates=candidates,
        subjects=subjects,
    )
    kept = kept_vectors([candidates[claim.dedupe_key] for claim in batch.claims], vectors)
    later = await _later(session, batch, kept, gating.judge)
    later |= {key: LaterGates(outcomes=(outcome,), vector=None) for key, outcome in closed.items()}
    return {key: gate_run(candidates[key], first[key], later.get(key)) for key in candidates}, set(closed)


async def _vectors(embed: TextEmbedder | None, candidates: Sequence[Candidate]) -> dict[str, list[float]]:
    try:
        return await candidate_vectors(embed, candidates)
    except AppError as error:
        logger.warning(
            "write-back statements were not embedded, so facts are matched by text only: %s", error
        )
        return {}


async def _later(
    session: AsyncSession, batch: _Batch, vectors: KeptVectors, judge: JudgeLadder | None
) -> dict[str, LaterGates]:
    embed = vectors if vectors.by_text else None
    found: dict[str, LaterGates] = {}
    for owner, group in by_owner(batch.claims).items():
        store = SqlHeldFacts(session, batch.subjects[owner])
        candidates = [batch.candidates[claim.dedupe_key] for claim in group]
        found |= await write_back_later_gates(store, candidates, embed=embed, judge=judge)
    return found


async def write_back_later_gates(
    store: HeldFacts,
    candidates: Sequence[Candidate],
    *,
    embed: TextEmbedder | None,
    judge: JudgeLadder | None,
) -> dict[str, LaterGates]:
    try:
        return await later_gates(
            store,
            candidates,
            embed=embed,
            judge=judge.first if judge is not None else None,
            escalate=judge.escalate if judge is not None else (),
            thrift=GateThrift(),
            novelty_failure=NOVELTY_LEFT_UNJUDGED,
        )
    except AppError as error:
        logger.warning("write-back gates fell back to identical texts only: %s", error)
        return await later_gates(store, candidates, embed=None, judge=None)


def _candidate(claim: ClaimWriteBack, subject: FactSubject | None = None) -> Candidate:
    title = subject_title(subject, claim.subject.concept_name, claim.stored_field) if subject else None
    return Candidate(ref=claim.dedupe_key, statement=claim.text, field=claim.stored_field, title=title)


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
