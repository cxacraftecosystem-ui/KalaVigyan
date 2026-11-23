from __future__ import annotations

import uuid
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from itertools import batched
from typing import Any

from sqlalchemy import ColumnElement, Select, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Claim, CuratedClaim, ReviewEvent
from app.research.retrieval import HIDDEN_CLAIM_STATUSES

from .curation_keys import (
    CURATED_STATUS,
    CURATION_ACTOR,
    CURATION_LEVELS,
    SUPERSEDED_STATUS,
    WITHDRAWN_STATUS,
)
from .curation_writes import BATCH, update_rows
from .differ_clearances import cleared_claims
from .sources_differ import differing_claims, settle_sources_differ

__all__ = [
    "EDGE_WITHDRAWN_NOTE",
    "ClaimWrites",
    "StoredClaim",
    "claim_writes",
    "craft_curated_claims",
    "kept_differences",
    "review_event",
    "stored_curated_claims",
    "superseded_claims",
    "withdraw_seed_edges",
    "write_claims",
]

EDGE_WITHDRAWN_NOTE = "seed edge sentence withdrawn from display; its relationship stays as structure"
SEED_EDGE = "EDGE"
SEED_ORIGIN = "IMPORT"
CLAIM_UPDATE_COLUMNS = (
    "id",
    "subjectId",
    "text",
    "evidenceLevel",
    "levelReason",
    "status",
    "version",
    "sensitivity",
    "sourcesDiffer",
    "differsOn",
    "field",
)
COMPARED = (
    "subjectId",
    "text",
    "evidenceLevel",
    "status",
    "sensitivity",
    "sourcesDiffer",
    "differsOn",
    "field",
)


@dataclass(frozen=True)
class StoredClaim:
    id: uuid.UUID
    subject_id: uuid.UUID
    text: str
    level: str
    level_reason: str | None
    status: str
    sensitivity: str
    sources_differ: bool
    field: str | None
    differs_on: str | None = None

    def compared(self) -> dict[str, Any]:
        return {
            "subjectId": self.subject_id,
            "text": self.text,
            "evidenceLevel": self.level,
            "status": self.status,
            "sensitivity": self.sensitivity,
            "sourcesDiffer": self.sources_differ,
            "differsOn": self.differs_on,
            "field": self.field,
        }


@dataclass(frozen=True)
class ClaimWrites:
    inserts: tuple[dict[str, Any], ...] = ()
    updates: tuple[dict[str, Any], ...] = ()
    events: tuple[dict[str, Any], ...] = ()


def review_event(
    claim_id: uuid.UUID,
    note: str,
    *,
    status: tuple[str | None, str | None],
    level: tuple[str | None, str | None],
) -> dict[str, Any]:
    return {
        "claimId": claim_id,
        "actorId": None,
        "actorKind": "SYSTEM",
        "systemActor": CURATION_ACTOR,
        "fromStatus": status[0],
        "toStatus": status[1],
        "fromLevel": level[0],
        "toLevel": level[1],
        "note": note,
    }


def claim_writes(
    planned: Sequence[dict[str, Any]], stored: Mapping[uuid.UUID, StoredClaim], note: str
) -> ClaimWrites:
    inserts, updates, events = [], [], []
    for row in planned:
        current = stored.get(row["id"])
        if current is None:
            inserts.append(row)
            events.append(
                review_event(
                    row["id"], note, status=(None, row["status"]), level=(None, row["evidenceLevel"])
                )
            )
            continue
        wanted = _respecting_people(row, current)
        if any(wanted[column] != current.compared()[column] for column in COMPARED):
            updates.append({column: wanted[column] for column in CLAIM_UPDATE_COLUMNS})
            events.append(
                review_event(
                    row["id"],
                    note,
                    status=(current.status, wanted["status"]),
                    level=(current.level, wanted["evidenceLevel"]),
                )
            )
    return ClaimWrites(tuple(inserts), tuple(updates), tuple(events))


def kept_differences(
    planned: Sequence[dict[str, Any]],
    stored: Mapping[uuid.UUID, StoredClaim],
    differing: Collection[uuid.UUID],
    cleared: Collection[uuid.UUID],
) -> list[dict[str, Any]]:
    return [_kept_difference(row, stored.get(row["id"]), differing, cleared) for row in planned]


def _kept_difference(
    row: dict[str, Any],
    current: StoredClaim | None,
    differing: Collection[uuid.UUID],
    cleared: Collection[uuid.UUID],
) -> dict[str, Any]:
    if row["id"] in differing and not row["sourcesDiffer"]:
        return {**row, "sourcesDiffer": True, "differsOn": current.differs_on if current else None}
    if row["id"] in cleared and row["id"] not in differing:
        return {**row, "sourcesDiffer": False, "differsOn": None}
    return row


def _respecting_people(row: dict[str, Any], current: StoredClaim) -> dict[str, Any]:
    curated_level = current.level in CURATION_LEVELS
    status = CURATED_STATUS if current.status == SUPERSEDED_STATUS else current.status
    return {
        **row,
        "evidenceLevel": row["evidenceLevel"] if curated_level else current.level,
        "levelReason": row["levelReason"] if curated_level else current.level_reason,
        "status": status,
    }


def superseded_claims(
    stored: Mapping[uuid.UUID, StoredClaim], planned_ids: set[uuid.UUID], note: str
) -> ClaimWrites:
    dropped = [
        claim
        for claim_id, claim in stored.items()
        if claim_id not in planned_ids and claim.status not in HIDDEN_CLAIM_STATUSES
    ]
    return ClaimWrites(
        updates=tuple({"id": claim.id, "status": SUPERSEDED_STATUS} for claim in dropped),
        events=tuple(
            review_event(
                claim.id, note, status=(claim.status, SUPERSEDED_STATUS), level=(claim.level, claim.level)
            )
            for claim in dropped
        ),
    )


def craft_curated_claims(craft_id: uuid.UUID) -> Select[tuple[uuid.UUID]]:
    return select(CuratedClaim.claimId).where(CuratedClaim.craftId == craft_id)


async def stored_curated_claims(
    session: AsyncSession, marked: Select[tuple[uuid.UUID]]
) -> dict[uuid.UUID, StoredClaim]:
    return await _stored_where(session, Claim.id.in_(marked))


async def write_claims(
    session: AsyncSession, marked: Select[tuple[uuid.UUID]], planned: Sequence[dict[str, Any]], note: str
) -> int:
    stored = await stored_curated_claims(session, marked)
    planned_ids = {row["id"] for row in planned}
    stored.update(await _stored_by_id(session, planned_ids - set(stored)))
    differing = await differing_claims(session, planned_ids)
    cleared = await cleared_claims(session, planned_ids)
    written = claim_writes(kept_differences(planned, stored, differing, cleared), stored, note)
    dropped = superseded_claims(stored, planned_ids, note)
    for chunk in batched(written.inserts, BATCH, strict=False):
        await session.execute(insert(Claim.__table__).values(list(chunk)))
    await update_rows(session, Claim, written.updates)
    await update_rows(session, Claim, dropped.updates)
    events = [*written.events, *dropped.events]
    for chunk in batched(events, BATCH, strict=False):
        await session.execute(insert(ReviewEvent.__table__).values(list(chunk)))
    await settle_sources_differ(session, [row["id"] for row in dropped.updates])
    return len(written.inserts) + len(written.updates) + len(dropped.updates)


async def _stored_by_id(session: AsyncSession, claim_ids: set[uuid.UUID]) -> dict[uuid.UUID, StoredClaim]:
    if not claim_ids:
        return {}
    return await _stored_where(session, Claim.id.in_(list(claim_ids)))


async def _stored_where(session: AsyncSession, chosen: ColumnElement[bool]) -> dict[uuid.UUID, StoredClaim]:
    statement = select(
        Claim.id,
        Claim.subjectId,
        Claim.text,
        Claim.evidenceLevel,
        Claim.levelReason,
        Claim.status,
        Claim.sensitivity,
        Claim.sourcesDiffer,
        Claim.field,
        Claim.differsOn,
    ).where(chosen)
    return {row[0]: StoredClaim(*row) for row in (await session.execute(statement)).tuples()}


async def withdraw_seed_edges(session: AsyncSession) -> int:
    rows = (
        await session.execute(
            select(Claim.id, Claim.status, Claim.evidenceLevel).where(
                Claim.subjectType == SEED_EDGE,
                Claim.origin == SEED_ORIGIN,
                Claim.status.not_in(HIDDEN_CLAIM_STATUSES),
            )
        )
    ).all()
    table = Claim.__table__
    for chunk in batched([row.id for row in rows], BATCH, strict=False):
        await session.execute(
            update(table).where(table.c.id.in_(chunk)).values(status=WITHDRAWN_STATUS, updatedAt=func.now())
        )
    events = [
        review_event(
            row.id,
            EDGE_WITHDRAWN_NOTE,
            status=(row.status, WITHDRAWN_STATUS),
            level=(row.evidenceLevel, row.evidenceLevel),
        )
        for row in rows
    ]
    for chunk in batched(events, BATCH, strict=False):
        await session.execute(insert(ReviewEvent.__table__).values(list(chunk)))
    return len(rows)
