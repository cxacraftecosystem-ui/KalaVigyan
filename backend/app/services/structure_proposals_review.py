from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import StructureProposal, User
from app.research.structure_proposals import APPROVED_STATUS, PENDING_STATUS, REJECTED_STATUS

from . import audit
from .structure_proposals_write import write_structure

__all__ = ["approve_structure", "reject_structure"]

TARGET = "StructureProposal"


async def approve_structure(
    session: AsyncSession, row: StructureProposal, reviewer: User, *, note: str | None, now: datetime
) -> uuid.UUID | None:
    claim_id = await write_structure(session, row, reviewer)
    row.claimId = claim_id
    await _decided(session, row, reviewer, (APPROVED_STATUS, note, now))
    return claim_id


async def reject_structure(
    session: AsyncSession, row: StructureProposal, reviewer: User, *, reason: str, now: datetime
) -> None:
    await _decided(session, row, reviewer, (REJECTED_STATUS, reason, now))


async def _decided(
    session: AsyncSession, row: StructureProposal, reviewer: User, decision: tuple[str, str | None, datetime]
) -> None:
    status, note, now = decision
    row.status, row.reviewedById, row.reviewedAt, row.reviewNote = status, reviewer.id, now, note
    await audit.record(
        session,
        action=f"review.structure_{status.lower()}",
        actor=reviewer,
        target_type=TARGET,
        target_id=row.id,
        detail={
            "from": PENDING_STATUS,
            "to": status,
            "kind": row.kind,
            "claim": None if row.claimId is None else str(row.claimId),
        },
    )
    await session.flush()
