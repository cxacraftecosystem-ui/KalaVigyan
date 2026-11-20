from __future__ import annotations

import uuid
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import ColumnElement, and_, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Claim, ClaimSource
from app.research.retrieval import SHOWN_CLAIM_STATUSES

from .knowledge_view import ClaimView

__all__ = [
    "FAILED_QUOTE",
    "corroborated_claim",
    "held_claim",
    "held_claim_ids",
    "held_in_queue",
    "is_held",
    "kept_verdict",
    "shown_held_ids",
    "unheld_by_id",
    "unheld_views",
    "with_kept_verdicts",
]

FAILED_QUOTE = "FAIL"
VERDICT_COLUMNS = ("quoteCheck", "checkedAt")


def held_claim() -> ColumnElement[bool]:
    quoted = ClaimSource.quote.is_not(None)
    cited = exists().where(ClaimSource.claimId == Claim.id, quoted)
    standing = exists().where(ClaimSource.claimId == Claim.id, quoted, ClaimSource.quoteCheck != FAILED_QUOTE)
    return and_(cited, ~standing)


def corroborated_claim() -> ColumnElement[bool]:
    failing = exists().where(
        ClaimSource.claimId == Claim.id,
        ClaimSource.quote.is_not(None),
        ClaimSource.quoteCheck == FAILED_QUOTE,
    )
    return and_(failing, ~held_claim())


def held_in_queue() -> ColumnElement[bool]:
    return and_(Claim.status.in_(SHOWN_CLAIM_STATUSES), held_claim())


async def held_claim_ids(session: AsyncSession, claim_ids: Iterable[uuid.UUID]) -> frozenset[uuid.UUID]:
    wanted = list(dict.fromkeys(claim_ids))
    if not wanted:
        return frozenset()
    rows = await session.scalars(
        select(ClaimSource.claimId)
        .where(ClaimSource.claimId.in_(wanted), ClaimSource.quote.is_not(None))
        .group_by(ClaimSource.claimId)
        .having(func.bool_and(ClaimSource.quoteCheck == FAILED_QUOTE))
    )
    return frozenset(rows.all())


async def shown_held_ids(session: AsyncSession) -> frozenset[uuid.UUID]:
    rows = await session.scalars(select(Claim.id).where(held_in_queue()))
    return frozenset(rows.all())


async def is_held(session: AsyncSession, claim_id: uuid.UUID) -> bool:
    return claim_id in await held_claim_ids(session, [claim_id])


async def unheld_views(session: AsyncSession, views: Sequence[ClaimView]) -> list[ClaimView]:
    held = await held_claim_ids(session, (view.id for view in views))
    return [view for view in views if view.id not in held]


async def unheld_by_id[Found](
    session: AsyncSession, found: Mapping[uuid.UUID, Found]
) -> dict[uuid.UUID, Found]:
    held = await held_claim_ids(session, found)
    return {claim_id: view for claim_id, view in found.items() if claim_id not in held}


def kept_verdict(planned: Mapping[str, Any], stored: Mapping[str, Any] | None) -> dict[str, Any]:
    if stored is None or not _later(stored.get("checkedAt"), planned.get("checkedAt")):
        return dict(planned)
    return {**planned, **{column: stored[column] for column in VERDICT_COLUMNS}}


async def with_kept_verdicts(
    session: AsyncSession, planned: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    ids = [row["id"] for row in planned]
    if not ids:
        return []
    rows = await session.execute(
        select(ClaimSource.id, ClaimSource.quoteCheck, ClaimSource.checkedAt).where(ClaimSource.id.in_(ids))
    )
    stored = {row.id: {"quoteCheck": row.quoteCheck, "checkedAt": row.checkedAt} for row in rows.all()}
    return [kept_verdict(row, stored.get(row["id"])) for row in planned]


def _later(stored: datetime | None, planned: datetime | None) -> bool:
    if stored is None:
        return False
    return planned is None or stored > planned
