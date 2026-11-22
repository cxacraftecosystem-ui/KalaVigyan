from __future__ import annotations

import logging
import uuid
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import ColumnElement, and_, exists, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Claim, Craft, ReviewEvent, SavedItem
from app.models.enums import EVIDENCE_LEVELS
from app.research.alerts import AnswerImproved, FacetNews, SavedExplainer
from app.research.depth import depth_policy
from app.research.vocabulary import FACT_LEVELS, LEVEL_ORDER
from app.retrieval.statements import CraftScope, claim_conditions

from .explainer_payload import EXPLAINER_PAYLOAD_KEY
from .notifications import note_improvement
from .saved_explainers import saved_explainer, saved_join

__all__ = [
    "LEVEL_RAISES",
    "NewClaim",
    "RecheckReport",
    "SavedCheck",
    "answer_news",
    "claim_facets",
    "new_claims",
    "recheck_saved",
    "saved_checks",
]

logger = logging.getLogger(__name__)

LEVEL_RAISES = tuple(
    (lower, higher)
    for lower in EVIDENCE_LEVELS
    for higher in EVIDENCE_LEVELS
    if LEVEL_ORDER[higher] < LEVEL_ORDER[lower]
)


@dataclass(frozen=True)
class SavedCheck:
    saved: SavedExplainer
    user_id: uuid.UUID
    scope: CraftScope
    cited: frozenset[uuid.UUID]
    since: datetime


@dataclass(frozen=True)
class NewClaim:
    claim_id: uuid.UUID
    facets: tuple[str, ...]


@dataclass
class RecheckReport:
    checked: int = 0
    notified: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {"checked": self.checked, "notified": self.notified, "ok": True}


def claim_facets(field: str | None, fields: Sequence[str] | None) -> tuple[str, ...]:
    if field is None:
        return ()
    return tuple(dict.fromkeys([field, *(fields or ())]))


def answer_news(
    check: SavedCheck, claims: Sequence[NewClaim], *, checked_at: datetime
) -> AnswerImproved | None:
    saved = check.saved
    if saved.craft is None:
        return None
    distinct = {claim.claim_id: claim for claim in claims if claim.claim_id not in check.cited}
    counts = Counter(facet for claim in distinct.values() for facet in claim.facets if facet in saved.facets)
    news = [FacetNews(facet=facet, new_claims=counts[facet]) for facet in saved.facets if counts[facet]]
    if not news:
        return None
    return AnswerImproved(
        explainer_id=saved.explainer_id,
        version=saved.latest_version,
        question=saved.question,
        craft=saved.craft,
        news=news,
        checked_at=checked_at,
    )


async def saved_checks(session: AsyncSession) -> list[SavedCheck]:
    joined = saved_join()
    rows = await session.execute(
        joined.select(
            Craft.id,
            Craft.subCategoryId,
            joined.last.claimIds,
            joined.last.payload[EXPLAINER_PAYLOAD_KEY]["createdAt"],
        )
        .join(Craft, Craft.id == joined.first.craftId)
        .order_by(SavedItem.createdAt, SavedItem.id)
    )
    return [_check(row) for row in rows.all()]


async def new_claims(session: AsyncSession, check: SavedCheck) -> list[NewClaim]:
    rows = await session.execute(
        select(Claim.id, Claim.field, Claim.fields).where(
            *claim_conditions(check.scope, mode=depth_policy(check.saved.depth).mode),
            Claim.evidenceLevel.in_(FACT_LEVELS),
            or_(Claim.createdAt > check.since, _raised_since(check.since)),
        )
    )
    return [NewClaim(claim_id, claim_facets(field, fields)) for claim_id, field, fields in rows]


async def recheck_saved(sessions: async_sessionmaker[AsyncSession], *, now: datetime) -> RecheckReport:
    async with sessions() as session:
        checks = await saved_checks(session)
    report = RecheckReport()
    for check in checks:
        async with sessions() as session:
            news = answer_news(check, await new_claims(session, check), checked_at=now)
            if news is not None:
                await note_improvement(session, check.user_id, news)
            await session.execute(
                update(SavedItem)
                .where(SavedItem.userId == check.user_id, SavedItem.answerId == check.saved.explainer_id)
                .values(checkedAt=now)
            )
            await session.commit()
        report.checked += 1
        if news is not None:
            report.notified += 1
            logger.info("explainer %s got better for a reader", check.saved.explainer_id)
    return report


def _check(row: Any) -> SavedCheck:
    saved = saved_explainer(row)
    item = row[0]
    craft_id, sub_category_id, cited, created_at = tuple(row)[-4:]
    return SavedCheck(
        saved=saved,
        user_id=item.userId,
        scope=CraftScope(craft_id=craft_id, sub_category_id=sub_category_id),
        cited=frozenset(cited),
        since=saved.checked_at or datetime.fromisoformat(created_at),
    )


def _raised_since(since: datetime) -> ColumnElement[bool]:
    raises = [
        and_(ReviewEvent.fromLevel == lower, ReviewEvent.toLevel == higher) for lower, higher in LEVEL_RAISES
    ]
    return exists().where(ReviewEvent.claimId == Claim.id, ReviewEvent.createdAt > since, or_(*raises))
