from __future__ import annotations

import logging
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, Refused
from app.core.roles import PROFESSOR, has_rank
from app.models import User
from app.research.candidate_gates import Candidate
from app.research.embedding import TextEmbedder
from app.research.fetcher import Fetcher
from app.research.gate_thrift import GateThrift
from app.research.knowledge_writes import FactProposal, ProposalReply, gate_reports
from app.research.review_switch import ReviewSwitch, refused_placement
from app.research.structured import StructuredModel
from app.research.trust_tiers import SWITCH, TierPlacement, drawn_for_review, tier_placement
from app.retrieval.indexing import embed_written

from . import app_settings, trust_tiers
from .candidate_gates import GateRun, HeldFacts, first_gates, gate_run, later_gates
from .candidate_sources import ReadSource, read_sources
from .candidate_store import SqlHeldFacts, proposal_subject
from .candidate_writes import mark_sources_differ, record_checks
from .fact_proposals_words import placement_message, placement_note
from .proposal_writes import ProposedClaim, cite_proposal, proposal_level, write_proposed_claim
from .task_reservations import complete_task, give_back_task

__all__ = [
    "NO_ACCOUNT",
    "ProposalAdapters",
    "ProposalRun",
    "embed_sources",
    "propose_fact",
    "propose_fact_run",
    "role_now",
]

logger = logging.getLogger(__name__)

NO_ACCOUNT = "no_account"
PROPOSAL_REF = "proposal"


@dataclass(frozen=True)
class ProposalAdapters:
    fetcher: Fetcher
    embed: TextEmbedder
    judge: StructuredModel
    escalate: tuple[StructuredModel, ...] = ()
    thrift: GateThrift | None = None


@dataclass(frozen=True)
class ProposalRun:
    reply: ProposalReply
    kept_sources: tuple[uuid.UUID, ...] = ()


async def propose_fact(
    session: AsyncSession,
    proposal: FactProposal,
    proposer: User,
    origin: str,
    *,
    adapters: ProposalAdapters,
    now: datetime,
) -> ProposalReply:
    ran = await propose_fact_run(
        session, proposal, proposer, origin, adapters=adapters, now=now, ticket=uuid.uuid4()
    )
    await embed_sources(session, adapters.embed, ran.kept_sources)
    return ran.reply


async def propose_fact_run(
    session: AsyncSession,
    proposal: FactProposal,
    proposer: User,
    origin: str,
    *,
    adapters: ProposalAdapters,
    now: datetime,
    ticket: uuid.UUID,
) -> ProposalRun:
    role = await role_now(session, proposer.id)
    standing = await trust_tiers.account_standing(session, proposer.id)
    subject = await proposal_subject(session, proposal.subject)
    read = await read_sources(session, adapters.fetcher, proposal, proposer_id=proposer.id)
    run = await _gated(proposal, read, adapters, SqlHeldFacts(session, subject))
    switch = await app_settings.review_switch(session)
    tiered = _placed(run, switch, origin, role=role, tier=standing.tier, ticket=ticket)
    note = placement_note(origin, tiered, run, role)
    written = ProposedClaim(proposal, subject, proposer.id, tiered.placed, run, note)
    claim_id = await write_proposed_claim(session, written)
    await record_checks(session, claim_id, run.outcomes, checked_at=now)
    kept = (
        await cite_proposal(session, claim_id, read, found_by=origin, proposer_id=proposer.id, checked_at=now)
        if run.passed
        else []
    )
    differ = await mark_sources_differ(session, claim_id) if tiered.placed.live else []
    if proposal.task_key is not None:
        settle = complete_task if run.passed else give_back_task
        await settle(session, proposer.id, proposal.task_key, now=now)
    return ProposalRun(reply=_reply(claim_id, written, tiered, differ), kept_sources=tuple(kept))


async def _gated(
    proposal: FactProposal, read: Sequence[ReadSource], adapters: ProposalAdapters, held: HeldFacts
) -> GateRun:
    candidate = Candidate(ref=PROPOSAL_REF, statement=proposal.statement, field=proposal.field)
    first = first_gates(candidate, [source.cited for source in read])
    if not all(outcome.passed for outcome in first):
        return gate_run(candidate, first, None)
    later = await later_gates(
        held,
        [candidate],
        embed=adapters.embed,
        judge=adapters.judge,
        thrift=adapters.thrift,
        escalate=adapters.escalate,
    )
    return gate_run(candidate, first, later[candidate.ref])


def _placed(
    run: GateRun, switch: ReviewSwitch, origin: str, *, role: str, tier: str, ticket: uuid.UUID
) -> TierPlacement:
    if not run.passed:
        return TierPlacement(refused_placement(), SWITCH)
    return tier_placement(
        switch.mode(origin),
        proposer_reviews=has_rank(role, PROFESSOR),
        tier=tier,
        drawn=drawn_for_review(ticket),
    )


async def role_now(session: AsyncSession, user_id: uuid.UUID) -> str:
    role = await session.scalar(select(User.role).where(User.id == user_id))
    if role is None:
        raise Refused(NO_ACCOUNT, "The account behind this proposal no longer exists.")
    return str(role)


async def embed_sources(session: AsyncSession, embed: TextEmbedder, source_ids: Sequence[uuid.UUID]) -> None:
    if not source_ids:
        return
    try:
        await embed_written(session, embed, claim_ids=[], source_ids=source_ids)
    except AppError as error:
        logger.warning("proposal sources stored without vectors, left for embed_knowledge: %s", error)


def _reply(
    claim_id: uuid.UUID, written: ProposedClaim, tiered: TierPlacement, differ: list[uuid.UUID]
) -> ProposalReply:
    run, placed = written.run, written.placed
    return ProposalReply(
        outcome=placed.outcome,
        claim_id=claim_id,
        status=placed.status,
        level=proposal_level(run),
        approved_at_once=placed.approved_at_once,
        in_review_queue=placed.queued,
        sources_differ=bool(differ),
        differs_from=run.differs_from,
        gates=gate_reports(list(run.outcomes)),
        message=placement_message(tiered, run),
    )
