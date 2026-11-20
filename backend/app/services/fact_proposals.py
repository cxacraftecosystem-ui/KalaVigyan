from __future__ import annotations

import logging
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, Refused
from app.core.roles import PROFESSOR, ROLE_LABELS, has_rank
from app.models import User
from app.research.candidate_gates import Candidate
from app.research.embedding import TextEmbedder
from app.research.fetcher import Fetcher
from app.research.knowledge_writes import FactProposal, ProposalReply, gate_reports
from app.research.review_switch import Placement, ReviewSwitch, placement, refused_placement
from app.research.structured import StructuredModel
from app.retrieval.indexing import embed_written

from . import app_settings
from .candidate_gates import GateRun, HeldFacts, first_gates, gate_run, later_gates
from .candidate_sources import ReadSource, read_sources
from .candidate_store import SqlHeldFacts, proposal_subject
from .candidate_writes import mark_sources_differ, record_checks
from .proposal_writes import ProposedClaim, cite_proposal, proposal_level, write_proposed_claim
from .task_reservations import complete_task, give_back_task

__all__ = ["NO_ACCOUNT", "ProposalAdapters", "propose_fact", "role_now"]

logger = logging.getLogger(__name__)

NO_ACCOUNT = "no_account"
PROPOSAL_REF = "proposal"
PUBLISHED_APPROVED = "Published, and approved at once because your account reviews contributions."
PUBLISHED_UNREVIEWED = "Published as unreviewed; a Professor or Admin will review it."
WAITING_MESSAGE = "Received. It stays hidden until a Professor or Admin approves it."


@dataclass(frozen=True)
class ProposalAdapters:
    fetcher: Fetcher
    embed: TextEmbedder
    judge: StructuredModel


async def propose_fact(
    session: AsyncSession,
    proposal: FactProposal,
    proposer: User,
    origin: str,
    *,
    adapters: ProposalAdapters,
    now: datetime,
) -> ProposalReply:
    role = await role_now(session, proposer.id)
    subject = await proposal_subject(session, proposal.subject)
    read = await read_sources(session, adapters.fetcher, proposal)
    run = await _gated(proposal, read, adapters, SqlHeldFacts(session, subject))
    placed = _placed(run, await app_settings.review_switch(session), origin, role)
    written = ProposedClaim(proposal, subject, proposer.id, placed, run, _note(origin, placed, run, role))
    claim_id = await write_proposed_claim(session, written)
    await record_checks(session, claim_id, run.outcomes, checked_at=now)
    if run.passed:
        kept = await cite_proposal(
            session, claim_id, read, found_by=origin, proposer_id=proposer.id, checked_at=now
        )
        await _embed_chunks(session, adapters.embed, kept)
    differ = await mark_sources_differ(session, claim_id) if placed.live else []
    if proposal.task_key is not None:
        settle = complete_task if run.passed else give_back_task
        await settle(session, proposer.id, proposal.task_key, now=now)
    return _reply(claim_id, written, differ)


async def _gated(
    proposal: FactProposal, read: Sequence[ReadSource], adapters: ProposalAdapters, held: HeldFacts
) -> GateRun:
    candidate = Candidate(ref=PROPOSAL_REF, statement=proposal.statement, field=proposal.field)
    first = first_gates(candidate, [source.cited for source in read])
    if not all(outcome.passed for outcome in first):
        return gate_run(candidate, first, None)
    later = await later_gates(held, [candidate], embed=adapters.embed, judge=adapters.judge)
    return gate_run(candidate, first, later[candidate.ref])


def _placed(run: GateRun, switch: ReviewSwitch, origin: str, role: str) -> Placement:
    if not run.passed:
        return refused_placement()
    return placement(switch.mode(origin), proposer_reviews=has_rank(role, PROFESSOR))


async def role_now(session: AsyncSession, user_id: uuid.UUID) -> str:
    role = await session.scalar(select(User.role).where(User.id == user_id))
    if role is None:
        raise Refused(NO_ACCOUNT, "The account behind this proposal no longer exists.")
    return str(role)


async def _embed_chunks(session: AsyncSession, embed: TextEmbedder, source_ids: list[uuid.UUID]) -> None:
    try:
        await embed_written(session, embed, claim_ids=[], source_ids=source_ids)
    except AppError as error:
        logger.warning("proposal sources stored without vectors, left for embed_knowledge: %s", error)


def _note(origin: str, placed: Placement, run: GateRun, role: str) -> str:
    refused = run.refused_at
    if refused is not None:
        return f"{origin} proposal refused at the {refused.gate} gate"
    if placed.approved_at_once:
        return f"{origin} proposal approved at once: proposed by a {ROLE_LABELS.get(role, role)} account"
    if placed.live:
        return f"{origin} proposal published unreviewed by the review switch (AUTO); it waits in the review queue"
    return f"{origin} proposal waits hidden for a Professor's or Admin's approval (review switch APPROVAL)"


def _reply(claim_id: uuid.UUID, written: ProposedClaim, differ: list[uuid.UUID]) -> ProposalReply:
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
        message=_message(placed, run),
    )


def _message(placed: Placement, run: GateRun) -> str:
    refused = run.refused_at
    if refused is not None:
        return f"Not added: the {refused.gate} gate refused it. {refused.reasons[0]}"
    if placed.approved_at_once:
        return PUBLISHED_APPROVED
    return PUBLISHED_UNREVIEWED if placed.live else WAITING_MESSAGE
