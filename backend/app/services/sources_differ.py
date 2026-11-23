from __future__ import annotations

import uuid
from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pydantic import TypeAdapter
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    CandidateCheck,
    Claim,
    Concept,
    Craft,
    CuratedCategory,
    CuratedCategoryClaim,
    CuratedClaim,
    CuratedCraft,
)
from app.research.candidate_gates import DUPLICATE_GATE
from app.research.retrieval import SHOWN_CLAIM_STATUSES

from .candidate_store import HELD_STATUSES
from .curated_index import IndexConflict
from .differ_clearances import clearances, cleared_claims

__all__ = [
    "HeldScope",
    "conflicted_claims",
    "differing_claims",
    "dismissed",
    "live_pair",
    "live_rivals",
    "settle_sources_differ",
]

CONFLICTS_KEY = "conflicts"
CONCEPT_SUBJECT = "CONCEPT"
CONFLICTS: TypeAdapter[list[IndexConflict]] = TypeAdapter(list[IndexConflict])


@dataclass(frozen=True)
class HeldScope:
    status: str
    craft_id: uuid.UUID | None
    family_id: uuid.UUID | None

    @property
    def held(self) -> bool:
        return self.status in HELD_STATUSES

    @property
    def shown(self) -> bool:
        return self.status in SHOWN_CLAIM_STATUSES


def live_pair(one: HeldScope, other: HeldScope) -> bool:
    return one.held and other.held and (one.shown or other.shown) and _one_scope(one, other)


async def settle_sources_differ(
    session: AsyncSession, claim_ids: Collection[uuid.UUID]
) -> dict[uuid.UUID, frozenset[uuid.UUID]]:
    given = set(claim_ids)
    touched = given | {claim for pair in await _pairs(session, given) for claim in pair}
    rivals = await live_rivals(session, touched)
    curated = await conflicted_claims(session, touched) - await cleared_claims(session, touched)
    flagged = {claim for claim in touched if rivals.get(claim)} | curated
    await _flag(session, flagged & touched, touched - flagged)
    return {claim: rivals.get(claim, frozenset()) for claim in given}


async def differing_claims(session: AsyncSession, claim_ids: Collection[uuid.UUID]) -> frozenset[uuid.UUID]:
    rivals = await live_rivals(session, claim_ids)
    return frozenset(claim for claim in claim_ids if rivals.get(claim))


async def live_rivals(
    session: AsyncSession, claim_ids: Collection[uuid.UUID]
) -> dict[uuid.UUID, frozenset[uuid.UUID]]:
    pairs = await _pairs(session, claim_ids)
    ends = {claim for pair in pairs for claim in pair}
    scopes = await _scopes(session, ends)
    cleared = await clearances(session, ends)
    found: dict[uuid.UUID, set[uuid.UUID]] = {}
    for pair, judged in pairs.items():
        one, other = tuple(pair)
        if _counted(pair, judged, scopes, cleared):
            found.setdefault(one, set()).add(other)
            found.setdefault(other, set()).add(one)
    return {claim: frozenset(rivals) for claim, rivals in found.items()}


def dismissed(pair: frozenset[uuid.UUID], judged: datetime, cleared: dict[uuid.UUID, datetime]) -> bool:
    return any(claim in cleared and cleared[claim] >= judged for claim in pair)


def _counted(
    pair: frozenset[uuid.UUID],
    judged: datetime,
    scopes: dict[uuid.UUID, HeldScope],
    cleared: dict[uuid.UUID, datetime],
) -> bool:
    one, other = tuple(pair)
    in_scope = one in scopes and other in scopes and live_pair(scopes[one], scopes[other])
    return in_scope and not dismissed(pair, judged, cleared)


async def conflicted_claims(session: AsyncSession, claim_ids: Collection[uuid.UUID]) -> set[uuid.UUID]:
    ids = list(claim_ids)
    if not ids:
        return set()
    crafts = select(CuratedClaim.craftId).where(CuratedClaim.claimId.in_(ids))
    categories = select(CuratedCategoryClaim.categoryId).where(CuratedCategoryClaim.claimId.in_(ids))
    craft_pages = await session.scalars(
        select(CuratedCraft.page[CONFLICTS_KEY]).where(CuratedCraft.craftId.in_(crafts))
    )
    category_pages = await session.scalars(
        select(CuratedCategory.page[CONFLICTS_KEY]).where(CuratedCategory.categoryId.in_(categories))
    )
    stored: list[Any] = [*craft_pages.all(), *category_pages.all()]
    named = {claim for found in stored for conflict in _conflicts(found) for claim in conflict.claim_ids}
    return named & set(ids)


def _conflicts(stored: Any) -> list[IndexConflict]:
    return CONFLICTS.validate_python(stored or [])


def _one_scope(one: HeldScope, other: HeldScope) -> bool:
    if one.craft_id is not None and other.craft_id is not None:
        return one.craft_id == other.craft_id
    if one.craft_id is None and other.craft_id is None:
        return one.family_id == other.family_id
    return one.family_id is not None and one.family_id == other.family_id


async def _pairs(
    session: AsyncSession, claim_ids: Collection[uuid.UUID]
) -> dict[frozenset[uuid.UUID], datetime]:
    ids = list(claim_ids)
    if not ids:
        return {}
    rows = await session.execute(
        select(CandidateCheck.claimId, CandidateCheck.relatedClaimIds, CandidateCheck.checkedAt).where(
            CandidateCheck.gate == DUPLICATE_GATE,
            CandidateCheck.passed.is_(True),
            or_(CandidateCheck.claimId.in_(ids), CandidateCheck.relatedClaimIds.overlap(ids)),
        )
    )
    judged: dict[frozenset[uuid.UUID], datetime] = {}
    for claim, related, checked in rows.tuples():
        for pair in (frozenset((claim, other)) for other in related if other != claim):
            judged[pair] = max(checked, judged.get(pair, checked))
    return judged


async def _scopes(session: AsyncSession, claim_ids: set[uuid.UUID]) -> dict[uuid.UUID, HeldScope]:
    if not claim_ids:
        return {}
    family = func.coalesce(Craft.subCategoryId, Concept.subCategoryId)
    rows = await session.execute(
        select(Claim.id, Claim.status, Concept.craftId, family)
        .join(Concept, and_(Claim.subjectType == CONCEPT_SUBJECT, Concept.id == Claim.subjectId))
        .outerjoin(Craft, Craft.id == Concept.craftId)
        .where(Claim.id.in_(list(claim_ids)))
    )
    return {claim: HeldScope(status, craft, owner) for claim, status, craft, owner in rows.tuples()}


async def _flag(session: AsyncSession, raised: set[uuid.UUID], cleared: set[uuid.UUID]) -> None:
    if raised:
        await session.execute(
            update(Claim)
            .where(Claim.id.in_(list(raised)), Claim.sourcesDiffer.is_(False))
            .values(sourcesDiffer=True)
        )
    if cleared:
        await session.execute(
            update(Claim)
            .where(Claim.id.in_(list(cleared)), Claim.sourcesDiffer.is_(True))
            .values(sourcesDiffer=False, differsOn=None)
        )
