from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import User
from app.providers.embedding import router_embedder
from app.providers.router import Principal
from app.research.review_queue import STRUCTURE, QueueDecision
from app.research.structure_proposals import StructureProposal, StructureProposalResult
from app.services.candidate_sources import proposal_fetcher
from app.services.review_queue_refresh import refresh_after_decision
from app.services.structure_proposals import propose_structure
from app.services.written_vectors import embed_now

__all__ = ["site_origin", "structure_proposed"]


def site_origin() -> str:
    return get_settings().public_web_url.rstrip("/")


async def structure_proposed(
    session: AsyncSession, proposal: StructureProposal, user: User, *, origin: str, site: str
) -> StructureProposalResult:
    async with proposal_fetcher() as fetcher:
        try:
            result = await propose_structure(
                session, user, proposal, context=(origin, fetcher, site), now=datetime.now(UTC)
            )
        except Exception:
            await session.rollback()
            raise
    await session.commit()
    written = QueueDecision(
        kind=STRUCTURE, id=result.proposal_id, status=result.status, message=result.message
    )
    await refresh_after_decision(session, written)
    embed = router_embedder(Principal(user_id=user.id, role=user.role))
    await embed_now(session, embed, claim_ids=[result.claim_id] if result.claim_id else [])
    return result
