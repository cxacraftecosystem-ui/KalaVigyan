from __future__ import annotations

import logging
import uuid
from collections.abc import Collection, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models import StructureProposal
from app.research.embedding import TextEmbedder
from app.research.review_queue import STRUCTURE, QueueDecision
from app.retrieval.indexing import EmbeddedCounts, embed_written

__all__ = ["NOTHING_EMBEDDED", "embed_decided", "embed_now", "embed_structure_claims"]

logger = logging.getLogger(__name__)

NOTHING_EMBEDDED = EmbeddedCounts(claims=0, chunks=0)


async def embed_now(
    session: AsyncSession,
    embed: TextEmbedder,
    *,
    claim_ids: Collection[uuid.UUID] = (),
    source_ids: Collection[uuid.UUID] = (),
) -> EmbeddedCounts:
    if not claim_ids and not source_ids:
        return NOTHING_EMBEDDED
    try:
        return await embed_written(session, embed, claim_ids=claim_ids, source_ids=source_ids)
    except AppError as error:
        logger.warning("written facts stored without vectors, left for embed_knowledge: %s", error)
        return NOTHING_EMBEDDED


async def embed_structure_claims(
    session: AsyncSession, embed: TextEmbedder, proposal_ids: Sequence[uuid.UUID]
) -> EmbeddedCounts:
    if not proposal_ids:
        return NOTHING_EMBEDDED
    claims = await session.scalars(
        select(StructureProposal.claimId).where(
            StructureProposal.id.in_(list(proposal_ids)), StructureProposal.claimId.is_not(None)
        )
    )
    return await embed_now(session, embed, claim_ids=[claim for claim in claims.all() if claim is not None])


async def embed_decided(
    session: AsyncSession, embed: TextEmbedder, decision: QueueDecision
) -> EmbeddedCounts:
    if decision.kind != STRUCTURE:
        return NOTHING_EMBEDDED
    return await embed_structure_claims(session, embed, [decision.id])
