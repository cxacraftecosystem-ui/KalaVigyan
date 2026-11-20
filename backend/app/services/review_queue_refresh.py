from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ArtisanContribution, StructureProposal
from app.research.page_revalidation import PageOwners
from app.research.review_queue import FACTS, STRUCTURE, TESTIMONY, QueueDecision
from app.research.review_switch import REFUSED_STATUS
from app.research.structure_proposals import APPROVED_STATUS

from .page_revalidation import claim_owners, craft_owners, refresh_pages

__all__ = ["OFF_PAGE_FACT_STATUSES", "refresh_after_decision"]

RETRACTED_STATUS = "RETRACTED"
OFF_PAGE_FACT_STATUSES = (REFUSED_STATUS, RETRACTED_STATUS)
REJECTED_TESTIMONY = "REJECTED"


async def refresh_after_decision(session: AsyncSession, decided: QueueDecision) -> bool:
    return await refresh_pages(await _owners(session, decided))


async def _owners(session: AsyncSession, decided: QueueDecision) -> PageOwners:
    if decided.kind == FACTS and decided.status in OFF_PAGE_FACT_STATUSES:
        return await claim_owners(session, [decided.id])
    if decided.kind == TESTIMONY and decided.status == REJECTED_TESTIMONY:
        craft = select(ArtisanContribution.craftId).where(ArtisanContribution.id == decided.id)
    elif decided.kind == STRUCTURE and decided.status == APPROVED_STATUS:
        craft = select(StructureProposal.craftId).where(StructureProposal.id == decided.id)
    else:
        return PageOwners()
    found = [craft_id for craft_id in (await session.scalars(craft)).all() if craft_id is not None]
    return await craft_owners(session, found)
