from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models import CandidateCheck, Claim
from app.research.candidate_gates import DUPLICATE_GATE, Candidate, HeldFact
from app.research.candidate_judge import JudgeAsk, comparison_request, parsed_comparisons
from app.research.structured import StructuredModel

from .candidate_gates import asked_judges

__all__ = ["FlaggedPair", "flagged_pairs", "rejudged_pairs"]

DIFFERS = "DIFFERS"
PAIR_SIMILARITY = 1.0


@dataclass(frozen=True)
class FlaggedPair:
    claim_id: uuid.UUID
    claim_text: str
    field: str | None
    held_id: uuid.UUID
    held_text: str


async def flagged_pairs(session: AsyncSession) -> list[FlaggedPair]:
    held = aliased(Claim, name="held")
    rows = await session.execute(
        select(Claim.id, Claim.text, Claim.field, held.id, held.text)
        .join(CandidateCheck, CandidateCheck.claimId == Claim.id)
        .join(held, held.id == CandidateCheck.relatedClaimIds.any_())
        .where(
            Claim.sourcesDiffer.is_(True),
            CandidateCheck.gate == DUPLICATE_GATE,
            CandidateCheck.passed.is_(True),
        )
        .order_by(Claim.id, held.id)
        .distinct()
    )
    return [FlaggedPair(*row) for row in rows.tuples().all()]


async def rejudged_pairs(
    pairs: Sequence[FlaggedPair], ladder: Sequence[StructuredModel]
) -> list[dict[str, Any]]:
    by_claim: dict[uuid.UUID, list[FlaggedPair]] = defaultdict(list)
    for pair in pairs:
        by_claim[pair.claim_id].append(pair)
    asks = [
        JudgeAsk(
            Candidate(ref=str(claim_id), statement=found[0].claim_text, field=found[0].field),
            tuple(
                HeldFact(id=pair.held_id, text=pair.held_text, similarity=PAIR_SIMILARITY) for pair in found
            ),
        )
        for claim_id, found in by_claim.items()
    ]
    if not asks:
        return []
    compared, model = await asked_judges(
        ladder, comparison_request(asks), lambda reply: parsed_comparisons(reply, asks)
    )
    return [
        {
            "claim": ref,
            "model": model,
            "wouldClear": all(item.relation != DIFFERS for item in items),
            "pairs": [
                {"held": str(item.held), "relation": item.relation, "reason": item.reason} for item in items
            ],
        }
        for ref, items in compared.items()
    ]
