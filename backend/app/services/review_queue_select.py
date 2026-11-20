from __future__ import annotations

import uuid
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from sqlalchemy import ColumnElement, and_, exists, func, or_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ArtisanContribution,
    CandidateCheck,
    Claim,
    ClaimSource,
    ComponentProposal,
    Craft,
    ImageContribution,
    LayoutProposal,
    StructureProposal,
)
from app.research.review_queue import (
    COMPONENTS,
    FACTS,
    IMAGES,
    LAYOUTS,
    PENDING_FACT_STATUSES,
    STRUCTURE,
    TESTIMONY,
    ComponentItem,
    FactItem,
    LayoutItem,
    PictureItem,
    QueueEntry,
    QueueKey,
    StructureQueueItem,
    TestimonyItem,
)
from app.research.review_switch import AGENT, RESEARCH
from app.research.write_back import WRITE_BACK_ORIGIN
from app.retrieval.statements import CraftScope, scope_claims

from .claim_holds import held_in_queue

__all__ = [
    "PENDING",
    "QUEUE_MODELS",
    "QueueScope",
    "Rendered",
    "RenderedItem",
    "gated_fact",
    "pending_conditions",
    "queue_count",
    "queue_entries",
    "rows_by_id",
]

PENDING = "PENDING"
CRAFT_SUBJECT = "CRAFT"
QUEUE_MODELS: Mapping[str, Any] = MappingProxyType(
    {
        FACTS: Claim,
        TESTIMONY: ArtisanContribution,
        IMAGES: ImageContribution,
        COMPONENTS: ComponentProposal,
        LAYOUTS: LayoutProposal,
        STRUCTURE: StructureProposal,
    }
)


RenderedItem = FactItem | TestimonyItem | PictureItem | ComponentItem | LayoutItem | StructureQueueItem


@dataclass(frozen=True)
class Rendered:
    item: RenderedItem
    proposer_id: uuid.UUID | None


@dataclass(frozen=True)
class QueueScope:
    viewer_id: uuid.UUID
    craft: Craft | None = None
    origin: str | None = None


def gated_fact() -> ColumnElement[bool]:
    return exists().where(CandidateCheck.claimId == Claim.id)


def pending_conditions(kind: str, scope: QueueScope) -> list[ColumnElement[bool]]:
    return _CONDITIONS[kind](scope)


async def queue_entries(
    session: AsyncSession, kind: str, scope: QueueScope, *, before: QueueKey | None, limit: int
) -> list[QueueEntry]:
    model = QUEUE_MODELS[kind]
    query = select(model.createdAt, model.id).where(*pending_conditions(kind, scope))
    if before is not None:
        query = query.where(tuple_(model.createdAt, model.id) < tuple_(before.created_at, before.item_id))
    rows = await session.execute(query.order_by(model.createdAt.desc(), model.id.desc()).limit(limit))
    return [QueueEntry(QueueKey(created, item_id), kind) for created, item_id in rows.all()]


async def queue_count(session: AsyncSession, kind: str, scope: QueueScope) -> int:
    model = QUEUE_MODELS[kind]
    counted = await session.scalar(select(func.count(model.id)).where(*pending_conditions(kind, scope)))
    return int(counted or 0)


async def rows_by_id(
    session: AsyncSession, model: Any, ids: Iterable[uuid.UUID | None]
) -> dict[uuid.UUID, Any]:
    wanted = list(dict.fromkeys(found for found in ids if found is not None))
    if not wanted:
        return {}
    return {row.id: row for row in await session.scalars(select(model).where(model.id.in_(wanted)))}


def _fact_conditions(scope: QueueScope) -> list[ColumnElement[bool]]:
    conditions = [
        or_(and_(Claim.status.in_(PENDING_FACT_STATUSES), gated_fact()), held_in_queue()),
        Claim.createdById.is_distinct_from(scope.viewer_id),
    ]
    if scope.craft is not None:
        craft = scope.craft
        conditions.append(scope_claims(CraftScope(craft_id=craft.id, sub_category_id=craft.subCategoryId)))
    if scope.origin is not None:
        conditions.append(_fact_origin(scope.origin))
    return conditions


def _fact_origin(origin: str) -> ColumnElement[bool]:
    if origin == RESEARCH:
        return Claim.origin == WRITE_BACK_ORIGIN
    by_agent = exists().where(ClaimSource.claimId == Claim.id, ClaimSource.foundBy == AGENT)
    return and_(Claim.origin != WRITE_BACK_ORIGIN, by_agent if origin == AGENT else ~by_agent)


def _testimony_conditions(scope: QueueScope) -> list[ColumnElement[bool]]:
    conditions = [ArtisanContribution.status == PENDING, ArtisanContribution.userId != scope.viewer_id]
    if scope.craft is not None:
        conditions.append(ArtisanContribution.craftId == scope.craft.id)
    return conditions


def _picture_conditions(scope: QueueScope) -> list[ColumnElement[bool]]:
    conditions = [
        ImageContribution.status == PENDING,
        ImageContribution.contributorId.is_distinct_from(scope.viewer_id),
    ]
    if scope.craft is not None:
        conditions.append(ImageContribution.craftId == scope.craft.id)
    return conditions


def _component_conditions(scope: QueueScope) -> list[ColumnElement[bool]]:
    conditions = [
        ComponentProposal.status == PENDING,
        ComponentProposal.proposerId.is_distinct_from(scope.viewer_id),
    ]
    if scope.craft is not None:
        named = ComponentProposal.subjects.contains([{"kind": CRAFT_SUBJECT, "key": scope.craft.slug}])
        conditions.append(or_(ComponentProposal.craftId == scope.craft.id, named))
    return conditions


def _layout_conditions(scope: QueueScope) -> list[ColumnElement[bool]]:
    conditions = [
        LayoutProposal.status == PENDING,
        LayoutProposal.proposerId.is_distinct_from(scope.viewer_id),
    ]
    if scope.craft is not None:
        conditions.append(LayoutProposal.craftId == scope.craft.id)
    if scope.origin is not None:
        conditions.append(LayoutProposal.origin == scope.origin)
    return conditions


def _structure_conditions(scope: QueueScope) -> list[ColumnElement[bool]]:
    conditions = [
        StructureProposal.status == PENDING,
        StructureProposal.proposerId.is_distinct_from(scope.viewer_id),
    ]
    if scope.craft is not None:
        conditions.append(StructureProposal.craftId == scope.craft.id)
    if scope.origin is not None:
        conditions.append(StructureProposal.origin == scope.origin)
    return conditions


_CONDITIONS: Mapping[str, Callable[[QueueScope], list[ColumnElement[bool]]]] = MappingProxyType(
    {
        FACTS: _fact_conditions,
        TESTIMONY: _testimony_conditions,
        IMAGES: _picture_conditions,
        COMPONENTS: _component_conditions,
        LAYOUTS: _layout_conditions,
        STRUCTURE: _structure_conditions,
    }
)
