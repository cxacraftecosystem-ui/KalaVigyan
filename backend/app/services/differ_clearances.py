from __future__ import annotations

import uuid
from collections.abc import Collection
from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, CuratedCategoryClaim, CuratedClaim, StructureProposal
from app.research.structure_proposals import APPROVED_STATUS, CONFLICT, ConflictItem, parsed_item

from .source_corrections import DIFFER_CLEARED

__all__ = ["clearances", "cleared_claims"]

CLAIM_TARGET = "Claim"


async def clearances(session: AsyncSession, claim_ids: Collection[uuid.UUID]) -> dict[uuid.UUID, datetime]:
    named = [str(claim) for claim in claim_ids]
    if not named:
        return {}
    rows = await session.execute(
        select(AuditLog.targetId, func.max(AuditLog.createdAt))
        .where(
            AuditLog.action == DIFFER_CLEARED,
            AuditLog.targetType == CLAIM_TARGET,
            AuditLog.targetId.in_(named),
        )
        .group_by(AuditLog.targetId)
    )
    return {uuid.UUID(target): at for target, at in rows.tuples() if target is not None}


async def cleared_claims(session: AsyncSession, claim_ids: Collection[uuid.UUID]) -> frozenset[uuid.UUID]:
    cleared = await clearances(session, claim_ids)
    if not cleared:
        return frozenset()
    approved = await _conflicts_approved(session, set(cleared))
    return frozenset(claim for claim, at in cleared.items() if at >= approved.get(claim, at))


async def _conflicts_approved(session: AsyncSession, claim_ids: set[uuid.UUID]) -> dict[uuid.UUID, datetime]:
    ids = list(claim_ids)
    crafts = select(CuratedClaim.craftId).where(CuratedClaim.claimId.in_(ids))
    categories = select(CuratedCategoryClaim.categoryId).where(CuratedCategoryClaim.claimId.in_(ids))
    rows = await session.execute(
        select(StructureProposal.item, StructureProposal.reviewedAt).where(
            StructureProposal.kind == CONFLICT,
            StructureProposal.status == APPROVED_STATUS,
            or_(StructureProposal.craftId.in_(crafts), StructureProposal.categoryId.in_(categories)),
        )
    )
    latest: dict[uuid.UUID, datetime] = {}
    for item, reviewed in rows.tuples():
        parsed = parsed_item(item)
        if reviewed is None or not isinstance(parsed, ConflictItem):
            continue
        for claim in claim_ids.intersection(parsed.claim_ids):
            latest[claim] = max(reviewed, latest.get(claim, reviewed))
    return latest
