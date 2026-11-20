from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Claim, ClaimSource, ReviewEvent, Source
from app.research.candidate_gates import QUOTES_GATE
from app.research.knowledge_writes import FactProposal
from app.research.review_switch import Placement
from app.research.vocabulary import LABEL_LEVELS
from app.research.write_back import WRITE_BACK_ORIGIN, WriteBackSubject

from .candidate_gates import GateRun
from .candidate_sources import ReadSource
from .candidate_store import CATEGORY, FactSubject
from .claim_writer import SHARED_CONCEPT_KEYS, CraftKeys, concept_id_for
from .curation_keys import DISCIPLINE_CONCEPT_TYPES
from .live_source_store import chunk_for_quote, keep_document
from .supplied_sources_gate import keep_supplied

__all__ = [
    "PROPOSAL_CLAIM_ORIGIN",
    "PROPOSAL_PREDICATE",
    "ProposedClaim",
    "cite_proposal",
    "mark_contributed",
    "proposal_level",
    "write_proposed_claim",
]

PROPOSAL_PREDICATE = "states"
PROPOSAL_CLAIM_ORIGIN = "CONTRIBUTION"
CONTRIBUTED_SOURCE_ORIGIN = "CONTRIBUTION"
QUOTED_LEVEL = LABEL_LEVELS["QUOTED"]
UNQUOTED_LEVEL = LABEL_LEVELS["INFERRED"]
QUOTED_REASON = (
    "Proposed fact: every quote was re-found verbatim in its fetched source by the candidate gates"
)
PASSED_QUOTE_CHECK = "PASS"
DIRECT = "DIRECT"
USER_ACTOR = "USER"


@dataclass(frozen=True)
class ProposedClaim:
    proposal: FactProposal
    subject: FactSubject
    proposer_id: uuid.UUID
    placed: Placement
    run: GateRun
    note: str


def proposal_level(run: GateRun) -> str:
    quotes = next((outcome for outcome in run.outcomes if outcome.gate == QUOTES_GATE), None)
    return QUOTED_LEVEL if quotes is not None and quotes.passed else UNQUOTED_LEVEL


async def write_proposed_claim(session: AsyncSession, written: ProposedClaim) -> uuid.UUID:
    proposal = written.proposal
    concept_id = await _concept(session, written.subject, proposal.field)
    claim_id = uuid.uuid4()
    level = proposal_level(written.run)
    refused = written.run.refused_at
    session.add(
        Claim(
            id=claim_id,
            subjectType="CONCEPT",
            subjectId=concept_id,
            predicate=PROPOSAL_PREDICATE,
            text=proposal.statement,
            evidenceLevel=level,
            levelReason=QUOTED_REASON if refused is None else f"Refused at the {refused.gate} gate",
            origin=PROPOSAL_CLAIM_ORIGIN,
            status=written.placed.status,
            createdById=written.proposer_id,
            createdByKind=USER_ACTOR,
            field=proposal.field,
            fields=list(proposal.fields),
            embedding=written.run.vector,
        )
    )
    await session.flush()
    session.add(_creation_event(claim_id, written, level))
    await session.flush()
    return claim_id


async def cite_proposal(
    session: AsyncSession,
    claim_id: uuid.UUID,
    read: Sequence[ReadSource],
    *,
    found_by: str,
    proposer_id: uuid.UUID,
    checked_at: datetime,
) -> list[uuid.UUID]:
    kept: list[uuid.UUID] = []
    for source in read:
        if source.document is None:
            continue
        source_id = await (keep_supplied if source.supplied else keep_document)(session, source.document)
        if source.stored is None:
            await mark_contributed(session, source_id, proposer_id)
        for quote in source.proposed.quotes:
            chunk = await chunk_for_quote(session, source_id, quote.text)
            session.add(
                ClaimSource(
                    claimId=claim_id,
                    sourceId=source_id,
                    chunkId=chunk.chunk_id if chunk else None,
                    locator=quote.locator or (chunk.locator if chunk else None),
                    quote=quote.text,
                    quoteCheck=PASSED_QUOTE_CHECK,
                    checkedAt=checked_at,
                    relation=DIRECT,
                    foundBy=found_by,
                    retrievedAt=source.document.item.retrieved_at,
                )
            )
        kept.append(source_id)
    await session.flush()
    return kept


async def _concept(session: AsyncSession, subject: FactSubject, field: str) -> uuid.UUID:
    keys = (
        SHARED_CONCEPT_KEYS
        if subject.kind == CATEGORY
        else CraftKeys(craft_id=subject.craft_id, sub_category_id=subject.sub_category_id)
    )
    named = WriteBackSubject(concept_type=DISCIPLINE_CONCEPT_TYPES[field], concept_name=subject.name or "")
    return await concept_id_for(session, keys, named)


async def mark_contributed(session: AsyncSession, source_id: uuid.UUID, proposer_id: uuid.UUID) -> None:
    await session.execute(
        update(Source)
        .where(Source.id == source_id, Source.origin == WRITE_BACK_ORIGIN, Source.addedById.is_(None))
        .values(origin=CONTRIBUTED_SOURCE_ORIGIN, addedById=proposer_id)
    )


def _creation_event(claim_id: uuid.UUID, written: ProposedClaim, level: str) -> ReviewEvent:
    return ReviewEvent(
        claimId=claim_id,
        actorId=written.proposer_id,
        actorKind=USER_ACTOR,
        toStatus=written.placed.status,
        toLevel=level,
        note=written.note,
    )
