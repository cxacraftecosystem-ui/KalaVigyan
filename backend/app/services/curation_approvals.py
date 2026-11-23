from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import INDIA_TZ
from app.models import Claim, CuratedCategoryClaim, CuratedClaim, StructureProposal
from app.research.retrieval import HIDDEN_CLAIM_STATUSES
from app.research.structure_proposals import (
    APPROVED_STATUS,
    CONFLICT,
    CONFLICT_CLAIMS_MIN,
    ConflictItem,
    parsed_item,
)

from .curation_plan import PlanParts

__all__ = [
    "BEHIND_FILE",
    "ApprovalOwner",
    "ApprovedStructure",
    "HeldClaim",
    "approved_structure",
    "category_approvals",
    "craft_approvals",
    "missing_approvals",
    "unheld_approvals",
]

BEHIND_FILE = (
    "the database holds structure a reviewer approved that this file does not, so the file is not imported "
    "and the page stays as the database holds it: export the dossier with export_dossiers --out, build "
    "any new version on that export, verify it and import it"
)
UNREVIEWED = "an approved structure proposal has no review time"
ABSENT = "{claim} ({kind}, approved {day}) is held by the database and not by this file"
REWORDED = "{claim} ({kind}, approved {day}) is worded otherwise in this file than the database holds it"
CONFLICT_ABSENT = (
    "the conflict between {claims} (approved {day}) is held by the database and not by this file"
)


@dataclass(frozen=True)
class ApprovalOwner:
    proposals: Any
    marker: Any
    marker_owner: Any
    id: uuid.UUID


@dataclass(frozen=True)
class HeldClaim:
    id: uuid.UUID
    key: str
    text: str


@dataclass(frozen=True)
class ApprovedStructure:
    kind: str
    approved_on: date
    claims: tuple[HeldClaim, ...]


def craft_approvals(craft_id: uuid.UUID) -> ApprovalOwner:
    return ApprovalOwner(StructureProposal.craftId, CuratedClaim, CuratedClaim.craftId, craft_id)


def category_approvals(category_id: uuid.UUID) -> ApprovalOwner:
    return ApprovalOwner(
        StructureProposal.categoryId, CuratedCategoryClaim, CuratedCategoryClaim.categoryId, category_id
    )


async def unheld_approvals(session: AsyncSession, owner: ApprovalOwner, plan: PlanParts) -> tuple[str, ...]:
    missing = missing_approvals(await approved_structure(session, owner), plan.part("claims"))
    return (BEHIND_FILE, *missing) if missing else ()


async def approved_structure(session: AsyncSession, owner: ApprovalOwner) -> list[ApprovedStructure]:
    rows = (
        await session.execute(
            select(
                StructureProposal.kind,
                StructureProposal.item,
                StructureProposal.claimId,
                StructureProposal.reviewedAt,
            )
            .where(owner.proposals == owner.id, StructureProposal.status == APPROVED_STATUS)
            .order_by(StructureProposal.reviewedAt, StructureProposal.id)
        )
    ).tuples()
    named = [(kind, _stated_by(kind, item, claim_id), reviewed) for kind, item, claim_id, reviewed in rows]
    held = await _held_claims(session, owner, {claim for _kind, ids, _reviewed in named for claim in ids})
    found = [
        ApprovedStructure(kind, _day(reviewed), tuple(held[claim] for claim in ids if claim in held))
        for kind, ids, reviewed in named
    ]
    return [approval for approval in found if len(approval.claims) >= _still_held(approval.kind)]


def missing_approvals(
    approved: Sequence[ApprovedStructure], planned: Sequence[Mapping[str, Any]]
) -> tuple[str, ...]:
    rows = {row["id"]: row for row in planned}
    found = (_missing(approval, rows) for approval in approved)
    return tuple(problem for problem in found if problem is not None)


def _missing(approval: ApprovedStructure, rows: Mapping[uuid.UUID, Mapping[str, Any]]) -> str | None:
    day = approval.approved_on.isoformat()
    if approval.kind == CONFLICT:
        if all(rows.get(claim.id, {}).get("sourcesDiffer") is True for claim in approval.claims):
            return None
        return CONFLICT_ABSENT.format(claims=" and ".join(claim.key for claim in approval.claims), day=day)
    claim = approval.claims[0]
    row = rows.get(claim.id)
    kind = approval.kind.lower().replace("_", " ")
    if row is None:
        return ABSENT.format(claim=claim.key, kind=kind, day=day)
    if row["text"] != claim.text:
        return REWORDED.format(claim=claim.key, kind=kind, day=day)
    return None


def _stated_by(kind: str, item: Any, claim_id: uuid.UUID | None) -> tuple[uuid.UUID, ...]:
    if kind == CONFLICT:
        parsed = parsed_item(item)
        return tuple(parsed.claim_ids) if isinstance(parsed, ConflictItem) else ()
    return (claim_id,) if claim_id is not None else ()


def _day(reviewed: datetime | None) -> date:
    if reviewed is None:
        raise ValueError(UNREVIEWED)
    return reviewed.astimezone(INDIA_TZ).date()


def _still_held(kind: str) -> int:
    return CONFLICT_CLAIMS_MIN if kind == CONFLICT else 1


async def _held_claims(
    session: AsyncSession, owner: ApprovalOwner, claim_ids: set[uuid.UUID]
) -> dict[uuid.UUID, HeldClaim]:
    if not claim_ids:
        return {}
    rows = await session.execute(
        select(Claim.id, owner.marker.key, Claim.text)
        .join(owner.marker, owner.marker.claimId == Claim.id)
        .where(
            Claim.id.in_(list(claim_ids)),
            owner.marker_owner == owner.id,
            Claim.status.not_in(HIDDEN_CLAIM_STATUSES),
        )
    )
    return {claim_id: HeldClaim(claim_id, key, text) for claim_id, key, text in rows.tuples()}
