from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Claim, Craft, CuratedClaim
from app.models.enums import DISCIPLINES, EXPLAINER_DEPTHS
from app.research.retrieval import HIDDEN_CLAIM_STATUSES, VISIBLE_SENSITIVITY
from app.research.understanding import Understanding

__all__ = [
    "FIELD_CLAIMS_MIN",
    "FLOOR_DEPTH",
    "curated_field_counts",
    "every_stored_field",
    "fields_held",
    "with_stored_fields",
]

FIELD_CLAIMS_MIN = 3
FLOOR_DEPTH = EXPLAINER_DEPTHS[-1]


async def curated_field_counts(session: AsyncSession, craft: Craft) -> dict[str, int]:
    rows = await session.execute(
        select(CuratedClaim.discipline, func.count())
        .join(Claim, Claim.id == CuratedClaim.claimId)
        .where(
            CuratedClaim.craftId == craft.id,
            Claim.status.not_in(HIDDEN_CLAIM_STATUSES),
            Claim.sensitivity == VISIBLE_SENSITIVITY,
        )
        .group_by(CuratedClaim.discipline)
    )
    return {str(row[0]): int(row[1]) for row in rows.all()}


def fields_held(counts: Mapping[str, int]) -> tuple[str, ...]:
    return tuple(d for d in DISCIPLINES if counts.get(d, 0) >= FIELD_CLAIMS_MIN)


async def with_stored_fields(
    understanding: Understanding, fields: Callable[[str], Awaitable[Sequence[str]]]
) -> Understanding:
    if not _widened(understanding) or understanding.craft is None:
        return understanding
    return every_stored_field(understanding, await fields(understanding.craft.slug))


def every_stored_field(understanding: Understanding, held: Sequence[str]) -> Understanding:
    if not _widened(understanding):
        return understanding
    asked = list(understanding.disciplines)
    added = [discipline for discipline in held if discipline not in asked]
    if not added:
        return understanding
    widened = understanding.model_dump(mode="json", by_alias=True) | {"disciplines": [*asked, *added]}
    return Understanding.model_validate(widened)


def _widened(understanding: Understanding) -> bool:
    return understanding.depth == FLOOR_DEPTH and understanding.craft is not None
