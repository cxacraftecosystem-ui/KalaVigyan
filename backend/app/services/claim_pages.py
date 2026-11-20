from __future__ import annotations

import uuid
from collections.abc import Iterable

from sqlalchemy.ext.asyncio import AsyncSession

from app.research.knowledge_writes import ProposalReply
from app.research.review_switch import PUBLISHED

from .page_revalidation import claim_owners, refresh_pages

__all__ = ["published_claims", "refresh_claim_pages"]


async def refresh_claim_pages(session: AsyncSession, claim_ids: Iterable[uuid.UUID]) -> bool:
    wanted = list(dict.fromkeys(claim_ids))
    if not wanted:
        return False
    return await refresh_pages(await claim_owners(session, wanted))


def published_claims(reply: ProposalReply) -> list[uuid.UUID]:
    if reply.outcome != PUBLISHED:
        return []
    return [reply.claim_id, *reply.differs_from]
