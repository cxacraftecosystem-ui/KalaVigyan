from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import batched

from sqlalchemy import ColumnElement, and_, exists, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Claim, Concept, ConceptEdge, CuratedClaim, CuratedCraft, Process, ReviewEvent
from app.models.science import live_process
from app.research.retrieval import HIDDEN_CLAIM_STATUSES

from .claim_seed import IMPORT_NOTE, SEED_PROCESS_VARIANT, SYSTEM_ACTOR
from .curation_claims import review_event
from .curation_keys import SUPERSEDED_STATUS
from .curation_writes import BATCH, update_rows

__all__ = [
    "SEED_RESTORED_NOTE",
    "SEED_RETIRED_NOTE",
    "SeedRetirement",
    "restore_seed_rows",
    "retire_curated_seed_rows",
    "seed_claim",
]

SEED_RETIRED_NOTE = "seed row retired, the craft has a curated dossier"
SEED_RESTORED_NOTE = "seed row restored, its craft's curated dossier no longer retires it"
CONCEPT_SUBJECT = "CONCEPT"
EDGE_SUBJECT = "EDGE"


@dataclass(frozen=True)
class SeedRetirement:
    claims: int = 0
    processes: int = 0

    def summary(self) -> dict[str, int]:
        return {"claims": self.claims, "processes": self.processes}


@dataclass(frozen=True)
class _Move:
    claim_id: uuid.UUID
    was: str
    to: str
    level: str


def seed_claim() -> ColumnElement[bool]:
    return exists().where(
        ReviewEvent.claimId == Claim.id,
        ReviewEvent.systemActor == SYSTEM_ACTOR,
        ReviewEvent.note.like(f"{IMPORT_NOTE} %"),
    )


async def retire_curated_seed_rows(session: AsyncSession) -> SeedRetirement:
    crafts = select(CuratedCraft.craftId)
    found = await session.execute(
        select(Claim.id, Claim.status, Claim.evidenceLevel).where(
            _about(Concept.craftId.in_(crafts)),
            seed_claim(),
            Claim.status.not_in(HIDDEN_CLAIM_STATUSES),
            Claim.id.not_in(select(CuratedClaim.claimId)),
        )
    )
    rows = [_Move(row.id, row.status, SUPERSEDED_STATUS, row.evidenceLevel) for row in found]
    await _moved(session, rows, note=SEED_RETIRED_NOTE)
    archived = await session.execute(
        update(Process)
        .where(Process.craftId.in_(crafts), Process.variant == SEED_PROCESS_VARIANT, live_process())
        .values(archivedAt=func.now(), updatedAt=func.now())
    )
    return SeedRetirement(claims=len(rows), processes=max(archived.rowcount or 0, 0))


async def restore_seed_rows(session: AsyncSession, craft_id: uuid.UUID) -> SeedRetirement:
    retired = (
        await session.execute(
            select(Claim.id, Claim.evidenceLevel).where(
                _about(Concept.craftId == craft_id), seed_claim(), Claim.status == SUPERSEDED_STATUS
            )
        )
    ).all()
    earlier = await _retired_from(session, [row.id for row in retired])
    rows = [
        _Move(row.id, SUPERSEDED_STATUS, earlier[row.id], row.evidenceLevel)
        for row in retired
        if row.id in earlier
    ]
    await _moved(session, rows, note=SEED_RESTORED_NOTE)
    restored = await session.execute(
        update(Process)
        .where(Process.craftId == craft_id, Process.variant == SEED_PROCESS_VARIANT, ~live_process())
        .values(archivedAt=None, updatedAt=func.now())
    )
    return SeedRetirement(claims=len(rows), processes=max(restored.rowcount or 0, 0))


def _about(owned: ColumnElement[bool]) -> ColumnElement[bool]:
    concepts = select(Concept.id).where(owned)
    edges = select(ConceptEdge.id).where(
        or_(ConceptEdge.srcId.in_(concepts), ConceptEdge.dstId.in_(concepts))
    )
    return or_(
        and_(Claim.subjectType == CONCEPT_SUBJECT, Claim.subjectId.in_(concepts)),
        and_(Claim.subjectType == EDGE_SUBJECT, Claim.subjectId.in_(edges)),
    )


async def _retired_from(session: AsyncSession, claim_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not claim_ids:
        return {}
    events = await session.execute(
        select(ReviewEvent.claimId, ReviewEvent.note, ReviewEvent.fromStatus)
        .where(ReviewEvent.claimId.in_(list(claim_ids)))
        .order_by(ReviewEvent.claimId, ReviewEvent.createdAt)
    )
    latest: dict[uuid.UUID, tuple[str | None, str | None]] = {}
    for claim_id, note, status in events.tuples():
        latest[claim_id] = (note, status)
    return {
        claim_id: status
        for claim_id, (note, status) in latest.items()
        if note == SEED_RETIRED_NOTE and status is not None
    }


async def _moved(session: AsyncSession, rows: Sequence[_Move], *, note: str) -> None:
    if not rows:
        return
    await update_rows(session, Claim, [{"id": row.claim_id, "status": row.to} for row in rows])
    events = [
        review_event(row.claim_id, note, status=(row.was, row.to), level=(row.level, row.level))
        for row in rows
    ]
    for chunk in batched(events, BATCH, strict=False):
        await session.execute(insert(ReviewEvent.__table__).values(list(chunk)))
