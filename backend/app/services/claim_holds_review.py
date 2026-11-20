from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ClaimSource, Source
from app.research.candidate_gates import QUOTES_GATE
from app.research.review_queue_parts import GateCheck

from .claim_holds import held_claim_ids

__all__ = ["HOLD_MODEL", "hold_evidence", "hold_reason", "with_hold_evidence"]

HOLD_MODEL = "nightly-upkeep"
UNCHECKED = "an unrecorded day"


def hold_reason(quote: str, url: str | None, checked_at: datetime | None) -> str:
    day = checked_at.date().isoformat() if checked_at is not None else UNCHECKED
    place = url or "its source"
    return f'The nightly re-check of {day} did not find the quote "{quote}" in {place}.'


def with_hold_evidence(
    checks: Mapping[uuid.UUID, Sequence[GateCheck]], evidence: Mapping[uuid.UUID, GateCheck]
) -> dict[uuid.UUID, list[GateCheck]]:
    merged = {claim_id: list(found) for claim_id, found in checks.items()}
    for claim_id, held in evidence.items():
        rest = [check for check in merged.get(claim_id, []) if check.gate != held.gate]
        merged[claim_id] = [held, *rest]
    return merged


async def hold_evidence(session: AsyncSession, claim_ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, GateCheck]:
    held = sorted(await held_claim_ids(session, claim_ids))
    if not held:
        return {}
    rows = await session.execute(
        select(ClaimSource.claimId, ClaimSource.quote, ClaimSource.checkedAt, Source.url)
        .join(Source, Source.id == ClaimSource.sourceId)
        .where(ClaimSource.claimId.in_(held), ClaimSource.quote.is_not(None))
        .order_by(ClaimSource.claimId, ClaimSource.checkedAt, ClaimSource.id)
    )
    reasons: dict[uuid.UUID, list[str]] = defaultdict(list)
    for claim_id, quote, checked_at, url in rows.all():
        reasons[claim_id].append(hold_reason(quote, url, checked_at))
    return {
        claim_id: GateCheck(gate=QUOTES_GATE, passed=False, reasons=found, model=HOLD_MODEL, related=[])
        for claim_id, found in reasons.items()
    }
