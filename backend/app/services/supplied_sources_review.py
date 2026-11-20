from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Claim, SuppliedSource
from app.research.supplied_sources import READY, SuppliedProvenance, cite_key

__all__ = ["CitedBy", "supplied_provenance"]

CitedBy = tuple[uuid.UUID, str | None]


async def supplied_provenance(
    session: AsyncSession, cited: Sequence[CitedBy]
) -> dict[CitedBy, SuppliedProvenance]:
    urls = {cite_key(url) for _, url in cited if url}
    if not urls:
        return {}
    creators = {
        claim_id: creator
        for claim_id, creator in (
            await session.execute(
                select(Claim.id, Claim.createdById).where(Claim.id.in_({claim for claim, _ in cited}))
            )
        ).tuples()
        if creator is not None
    }
    if not creators:
        return {}
    rows = await session.scalars(
        select(SuppliedSource)
        .where(
            SuppliedSource.userId.in_(set(creators.values())),
            SuppliedSource.citeUrl.in_(urls),
            SuppliedSource.state == READY,
        )
        .order_by(SuppliedSource.createdAt, SuppliedSource.id)
    )
    newest = {(row.userId, row.citeUrl): row for row in rows}
    found: dict[CitedBy, SuppliedProvenance] = {}
    for claim_id, url in cited:
        row = newest.get((creators.get(claim_id), cite_key(url))) if url else None
        if row is not None:
            found[(claim_id, url)] = _provenance(row)
    return found


def _provenance(row: SuppliedSource) -> SuppliedProvenance:
    confirmed = row.confirmation or {}
    return SuppliedProvenance(
        supplied_source_id=row.id,
        access=row.accessKind,
        accessed_on=row.accessedOn,
        grade=row.grade,
        confirmed_by=confirmed.get("index"),
        text_sha256=row.textSha256 or "",
        characters=row.characters,
    )
