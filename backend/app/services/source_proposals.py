from __future__ import annotations

import uuid
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput
from app.models import Claim, ClaimSource, User
from app.research.candidate_gates import Candidate, GateOutcome
from app.research.fetcher import Fetcher
from app.research.knowledge_writes import gate_reports
from app.research.open_work import OpenTask, parse_task_key
from app.research.retrieval import SHOWN_CLAIM_STATUSES, VISIBLE_SENSITIVITY
from app.research.source_proposals import ADDED, REFUSED, SourceProposal, SourceProposalReply

from . import audit
from .candidate_gates import first_gates
from .candidate_sources import ReadSource, read_source
from .claim_holds import is_held
from .open_work import open_task
from .proposal_writes import cite_proposal
from .task_reservations import complete_task, give_back_task

__all__ = ["SOURCE_ADDED", "SourceAsk", "propose_source", "task_problem"]

SOURCE_ADDED = "knowledge.source_added"
SOURCE_REF = "source"
NO_FACT = "No shown fact has the id {claim_id}; get_facts gives the facts and their ids."
NOT_OPEN = "No open task has the key {key}; list_open_work gives the open tasks."
OTHER_FACT = "{key} lists other facts than {claim_id}; claim the task that names this fact."
QUOTED_ALREADY = "The fact already cites the quote {quote!r}; give a quote it does not cite yet."


@dataclass(frozen=True)
class SourceAsk:
    proposer: User
    origin: str
    fetcher: Fetcher
    site: str
    now: datetime


async def propose_source(
    session: AsyncSession, proposal: SourceProposal, ask: SourceAsk
) -> SourceProposalReply:
    claim = await _shown_claim(session, proposal.claim_id)
    cited = await _cited(session, claim.id)
    _refuse_cited_quotes(proposal, {quote for _, quote in cited})
    if proposal.task_key is not None:
        await _check_task(
            session, proposal.task_key, claim.id, {source for source, _ in cited}, site=ask.site
        )
    was_held = await is_held(session, claim.id)
    read = tuple(
        [await read_source(session, ask.fetcher, s, proposer_id=ask.proposer.id) for s in proposal.sources]
    )
    outcomes = first_gates(
        Candidate(ref=SOURCE_REF, statement=claim.text, field=claim.field), [r.cited for r in read]
    )
    passed = all(outcome.passed for outcome in outcomes)
    added = await _added(session, claim.id, read, ask) if passed else 0
    if proposal.task_key is not None:
        settle = complete_task if passed else give_back_task
        await settle(session, ask.proposer.id, proposal.task_key, now=ask.now)
    held = await is_held(session, claim.id)
    return SourceProposalReply(
        outcome=ADDED if passed else REFUSED,
        claim_id=claim.id,
        quotes_added=added,
        held=held,
        gates=gate_reports(list(outcomes)),
        message=_message(outcomes, added=added, returned=was_held and not held),
    )


def task_problem(
    task: OpenTask | None, key: str, claim_id: uuid.UUID, cited_sources: Collection[uuid.UUID]
) -> str | None:
    if task is None:
        return NOT_OPEN.format(key=key)
    if task.fact_ids:
        listed = claim_id in task.fact_ids or task.count > len(task.fact_ids)
        return None if listed else OTHER_FACT.format(key=key, claim_id=claim_id)
    if task.source_ids:
        shown = {str(source) for source in cited_sources} & set(task.source_ids)
        listed = bool(shown) or task.count > len(task.source_ids)
        return None if listed else OTHER_FACT.format(key=key, claim_id=claim_id)
    return None


async def _shown_claim(session: AsyncSession, claim_id: uuid.UUID) -> Claim:
    claim = await session.get(Claim, claim_id)
    if claim is None or claim.status not in SHOWN_CLAIM_STATUSES or claim.sensitivity != VISIBLE_SENSITIVITY:
        raise InvalidInput(NO_FACT.format(claim_id=claim_id))
    return claim


async def _cited(session: AsyncSession, claim_id: uuid.UUID) -> list[tuple[uuid.UUID, str | None]]:
    rows = await session.execute(
        select(ClaimSource.sourceId, ClaimSource.quote).where(ClaimSource.claimId == claim_id)
    )
    return [(source_id, quote) for source_id, quote in rows.all()]


def _refuse_cited_quotes(proposal: SourceProposal, quoted: Collection[str | None]) -> None:
    for source in proposal.sources:
        for quote in source.quotes:
            if quote.text in quoted:
                raise InvalidInput(QUOTED_ALREADY.format(quote=quote.text))


async def _check_task(
    session: AsyncSession, key: str, claim_id: uuid.UUID, cited: Collection[uuid.UUID], *, site: str
) -> None:
    task = await open_task(session, parse_task_key(key), site=site)
    problem = task_problem(task, key, claim_id, cited)
    if problem is not None:
        raise InvalidInput(problem)


async def _added(
    session: AsyncSession, claim_id: uuid.UUID, read: Sequence[ReadSource], ask: SourceAsk
) -> int:
    kept = await cite_proposal(
        session, claim_id, read, found_by=ask.origin, proposer_id=ask.proposer.id, checked_at=ask.now
    )
    await audit.record(
        session,
        action=SOURCE_ADDED,
        actor=ask.proposer,
        target_type="Claim",
        target_id=claim_id,
        detail={"sources": [str(source_id) for source_id in kept], "origin": ask.origin},
    )
    return sum(len(source.proposed.quotes) for source in read if source.document is not None)


def _message(outcomes: Sequence[GateOutcome], *, added: int, returned: bool) -> str:
    refused = next((outcome for outcome in outcomes if not outcome.passed), None)
    if refused is not None:
        return f"Not added: the {refused.gate} gate refused it. {refused.reasons[0]}"
    quotes = "1 quote" if added == 1 else f"{added} quotes"
    back = " The fact shows on its page again." if returned else ""
    return f"Added: {quotes} now support the fact, each found verbatim in its fetched source.{back}"
