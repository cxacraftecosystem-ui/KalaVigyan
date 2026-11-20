from __future__ import annotations

import uuid
from collections.abc import Collection
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Claim
from app.research.retrieval import SHOWN_CLAIM_STATUSES

from . import audit
from .claim_holds import corroborated_claim, shown_held_ids
from .claim_pages import refresh_claim_pages
from .upkeep_links import LinksReport, look_after_links

__all__ = [
    "CLAIMS_HELD",
    "CLAIMS_LIFTED",
    "HealingReport",
    "corroborate_count",
    "heal",
    "hold_changes",
]

CLAIMS_HELD = "upkeep.claims_held"
CLAIMS_LIFTED = "upkeep.claims_lifted"
CLAIMS_KEY = "claimIds"


@dataclass
class HealingReport:
    held: list[str] = field(default_factory=list)
    lifted: list[str] = field(default_factory=list)
    held_now: int = 0
    corroborate: int = 0
    links: LinksReport = field(default_factory=LinksReport)
    pages_refreshed: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "claimsHeld": len(self.held),
            "claimsLifted": len(self.lifted),
            "heldNow": self.held_now,
            "corroborate": self.corroborate,
            **self.links.as_dict(),
            "pagesRefreshed": self.pages_refreshed,
        }


def hold_changes(
    before: Collection[uuid.UUID], after: Collection[uuid.UUID]
) -> tuple[list[uuid.UUID], list[uuid.UUID]]:
    held = sorted(set(after) - set(before), key=str)
    lifted = sorted(set(before) - set(after), key=str)
    return held, lifted


async def corroborate_count(session: AsyncSession) -> int:
    shown = and_(Claim.status.in_(SHOWN_CLAIM_STATUSES), corroborated_claim())
    counted = await session.scalar(select(func.count(Claim.id)).where(shown))
    return int(counted or 0)


async def heal(session: AsyncSession, *, before: Collection[uuid.UUID]) -> HealingReport:
    after = await shown_held_ids(session)
    held, lifted = hold_changes(before, after)
    links = await look_after_links(session)
    await _recorded(session, CLAIMS_HELD, held)
    await _recorded(session, CLAIMS_LIFTED, lifted)
    await session.commit()
    report = HealingReport(
        held=[str(claim_id) for claim_id in held],
        lifted=[str(claim_id) for claim_id in lifted],
        held_now=len(after),
        corroborate=await corroborate_count(session),
        links=links,
    )
    report.pages_refreshed = await refresh_claim_pages(session, [*held, *lifted])
    return report


async def _recorded(session: AsyncSession, action: str, claim_ids: list[uuid.UUID]) -> None:
    if claim_ids:
        await audit.record(
            session, action=action, detail={CLAIMS_KEY: [str(claim_id) for claim_id in claim_ids]}
        )
