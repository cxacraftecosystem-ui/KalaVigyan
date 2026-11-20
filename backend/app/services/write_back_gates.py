from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models import Claim
from app.research.candidate_gates import Candidate, CitedSource
from app.research.embedding import TextEmbedder
from app.research.evidence import SourceDocument
from app.research.review_switch import RESEARCH, Placement, placement
from app.research.structured import StructuredModel
from app.research.vocabulary import CONCEPT_TYPE_DISCIPLINES
from app.research.write_back import ClaimWriteBack, WriteBackCitation, WriteBackResult

from . import app_settings
from .candidate_gates import GateRun, HeldFacts, LaterGates, first_gates, gate_run, later_gates
from .candidate_store import SqlHeldFacts, craft_subject
from .candidate_writes import mark_sources_differ, record_checks
from .claim_writer import write_back_claim_id
from .write_back_plan import SkippedSentence

__all__ = ["GatedWriteBack", "gate_write_back", "record_write_back_runs", "research_placement"]

logger = logging.getLogger(__name__)

PASSED_QUOTE = "PASS"


@dataclass(frozen=True)
class GatedWriteBack:
    claims: tuple[ClaimWriteBack, ...]
    runs: Mapping[str, GateRun]
    held_instead: tuple[WriteBackResult, ...]
    skipped: tuple[SkippedSentence, ...]


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
    held = await _held_keys(session, claims)
    new = [claim for claim in claims if claim.dedupe_key not in held]
    store = SqlHeldFacts(session, await craft_subject(session, new[0].craft_slug)) if new else None
    runs = await _runs(store, new, documents, embed=embed, judge=judge)
    refused = [claim for claim in new if not runs[claim.dedupe_key].passed]
    return GatedWriteBack(
        claims=tuple(claim for claim in claims if claim.dedupe_key in held or runs[claim.dedupe_key].passed),
        runs=runs,
        held_instead=tuple(
            _instead(claim, runs[claim.dedupe_key]) for claim in refused if _instead_of(runs, claim)
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
    store: HeldFacts | None,
    claims: Sequence[ClaimWriteBack],
    documents: Mapping[str, SourceDocument],
    *,
    embed: TextEmbedder | None,
    judge: StructuredModel | None,
) -> dict[str, GateRun]:
    candidates = {claim.dedupe_key: _candidate(claim) for claim in claims}
    first = {
        claim.dedupe_key: first_gates(candidates[claim.dedupe_key], _cited(claim, documents))
        for claim in claims
    }
    passing = [candidates[key] for key, outcomes in first.items() if all(o.passed for o in outcomes)]
    later = await _later(store, passing, embed=embed, judge=judge) if store is not None else {}
    return {key: gate_run(candidates[key], first[key], later.get(key)) for key in candidates}


async def _later(
    store: HeldFacts,
    candidates: Sequence[Candidate],
    *,
    embed: TextEmbedder | None,
    judge: StructuredModel | None,
) -> dict[str, LaterGates]:
    try:
        return await later_gates(store, candidates, embed=embed, judge=judge)
    except AppError as error:
        logger.warning("write-back gates fell back to identical texts only: %s", error)
        return await later_gates(store, candidates, embed=None, judge=None)


async def _held_keys(session: AsyncSession, claims: Sequence[ClaimWriteBack]) -> set[str]:
    ids = {write_back_claim_id(claim.dedupe_key): claim.dedupe_key for claim in claims}
    if not ids:
        return set()
    found = await session.scalars(select(Claim.id).where(Claim.id.in_(list(ids))))
    return {ids[claim_id] for claim_id in found}


def _candidate(claim: ClaimWriteBack) -> Candidate:
    return Candidate(
        ref=claim.dedupe_key,
        statement=claim.text,
        field=CONCEPT_TYPE_DISCIPLINES.get(claim.subject.concept_type),
    )


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


def _instead_of(runs: Mapping[str, GateRun], claim: ClaimWriteBack) -> bool:
    return bool(runs[claim.dedupe_key].held_instead)


def _instead(claim: ClaimWriteBack, run: GateRun) -> WriteBackResult:
    return WriteBackResult(dedupe_key=claim.dedupe_key, claim_id=run.held_instead[0], created=False)


def _skipped(claim: ClaimWriteBack, run: GateRun) -> SkippedSentence:
    refused = run.refused_at
    gate = refused.gate if refused is not None else "unknown"
    reason = refused.reasons[0] if refused is not None else "no reason was recorded"
    return SkippedSentence(claim.text, f"refused at the {gate} gate: {reason}")
