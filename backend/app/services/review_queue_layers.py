from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.geo.datasets import region_dataset
from app.models import EnvDataset, MapLayerProposal, User
from app.research.map_layer_geojson import layer_bounds
from app.research.map_layer_proposals import MapLayerPlan
from app.research.review_queue import KIND_ORIGINS, LAYERS, LayerQueueItem, QueueDecision
from app.research.review_queue_layers import LayerBounds, LayerReview, layer_checks

from . import audit
from .dataset_registry import dataset_record
from .review_queue_errors import DecisionConflict, OwnItem, UnknownItem
from .review_queue_select import PENDING, Rendered, rows_by_id

__all__ = ["approve_layer", "layer_items", "reject_layer"]

APPROVED = "APPROVED"
REJECTED = "REJECTED"
LAYER_ORIGIN = KIND_ORIGINS[LAYERS][0]
MESSAGES = {
    APPROVED: (
        "Approved: an engineer adds it to the site's maps through tools/maplayers from the stored layer and "
        "its record; nothing is drawn until then."
    ),
    REJECTED: "Rejected: the layer stays private and is never drawn, and the reason is kept with it.",
}


@dataclass(frozen=True)
class _Decision:
    status: str
    note: str | None
    action: str


async def layer_items(session: AsyncSession, ids: Sequence[uuid.UUID]) -> list[Rendered]:
    rows = list(await session.scalars(select(MapLayerProposal).where(MapLayerProposal.id.in_(list(ids)))))
    datasets = await rows_by_id(session, EnvDataset, [row.datasetId for row in rows])
    return [Rendered(_item(row, datasets[row.datasetId]), row.proposerId) for row in rows]


async def approve_layer(
    session: AsyncSession, proposal_id: uuid.UUID, reviewer: User, *, note: str | None, now: datetime
) -> QueueDecision:
    return await _decided(session, proposal_id, reviewer, _Decision(APPROVED, note, "approved"), now=now)


async def reject_layer(
    session: AsyncSession, proposal_id: uuid.UUID, reviewer: User, *, reason: str, now: datetime
) -> QueueDecision:
    return await _decided(session, proposal_id, reviewer, _Decision(REJECTED, reason, "rejected"), now=now)


async def _decided(
    session: AsyncSession, proposal_id: uuid.UUID, reviewer: User, decision: _Decision, *, now: datetime
) -> QueueDecision:
    row = await session.get(MapLayerProposal, proposal_id, with_for_update=True)
    if row is None:
        raise UnknownItem(f"No map layer proposal has the id {proposal_id}.")
    if row.proposerId == reviewer.id:
        raise OwnItem("A reviewer does not decide their own proposal.")
    if row.status != PENDING:
        raise DecisionConflict(f"This proposal is {row.status.lower()} already. Reload the queue.")
    row.status, row.reviewedById, row.reviewedAt, row.reviewNote = (
        decision.status,
        reviewer.id,
        now,
        decision.note,
    )
    await session.flush()
    await audit.record(
        session,
        action=f"review.layer_{decision.action}",
        actor=reviewer,
        target_type="MapLayerProposal",
        target_id=row.id,
        detail={"from": PENDING, "to": decision.status, "dataset": str(row.datasetId)},
    )
    return QueueDecision(kind=LAYERS, id=row.id, status=row.status, message=MESSAGES[row.status])


def _item(row: MapLayerProposal, dataset: EnvDataset) -> LayerQueueItem:
    plan = MapLayerPlan.model_validate(row.plan)
    bounds = layer_bounds(row.layer)
    return LayerQueueItem(
        id=row.id,
        origin=LAYER_ORIGIN,
        submitted_at=row.createdAt,
        craft=None,
        layer=LayerReview(
            dataset=region_dataset(dataset_record(dataset)),
            plan=plan,
            geometry=plan.kind.geometry,
            features=row.featureCount,
            byte_size=row.byteSize,
            bounds=LayerBounds(west=bounds.west, south=bounds.south, east=bounds.east, north=bounds.north),
            checks=layer_checks(plan),
        ),
    )
