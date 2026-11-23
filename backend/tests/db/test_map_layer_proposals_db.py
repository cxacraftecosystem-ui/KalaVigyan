import hashlib
import json
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput
from app.models import AuditLog, DatasetTable, EnvDataset, MapLayerProposal, User
from app.research.dataset_proposals import DatasetProposal
from app.research.review_queue import LayerQueueItem, QueueApproval, QueueRejection, ReviewFilters
from app.services import dataset_proposals as proposals
from app.services.review_queue import QueueAdapters, list_review_queue
from app.services.review_queue_decisions import ItemRef, approve_item, reject_item
from app.services.review_queue_errors import OwnItem

from .review_queue_seed import TurnsOf
from .testimony_seed import rolled_back_session

pytestmark = pytest.mark.db

NOW = datetime(2026, 11, 23, 9, tzinfo=UTC)
ADAPTERS = QueueAdapters(objects=None, turns_of=TurnsOf())
SITES: dict[str, Any] = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [69.75, 23.25]},
            "properties": {"pits": 4},
        },
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [72.5, 22.5]},
            "properties": {"pits": None},
        },
    ],
}
LAYER = json.dumps(SITES).encode("utf-8")
FAR_SITE = {
    "type": "Feature",
    "geometry": {"type": "Point", "coordinates": [99.0, 23.25]},
    "properties": {"pits": 4},
}
FAR = json.dumps({"type": "FeatureCollection", "features": [FAR_SITE]}).encode("utf-8")
PLAN = {
    "layerClass": "POINT_SITES",
    "valueProperty": "pits",
    "variable": "clay pits recorded at the site",
    "unit": "count",
    "method": "counted from the survey's site records",
}


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in rolled_back_session():
        yield opened


async def person(session: AsyncSession, role: str) -> User:
    token = uuid.uuid4()
    user = User(
        id=token, name=f"{role.title()} {token.hex[:4]}", email=f"{token.hex[:12]}@example.org", role=role
    )
    session.add(user)
    await session.flush()
    return user


def record(code: str, data: bytes = LAYER) -> DatasetProposal:
    body: dict[str, Any] = {
        "code": code,
        "title": "Clay pits of Kachchh",
        "publisher": "A state geological survey",
        "edition": "2025",
        "version": "1",
        "period": "2025",
        "native_resolution": "point sites",
        "crs": "EPSG:4326",
        "licence": "CC BY 4.0",
        "licence_url": "https://creativecommons.org/licenses/by/4.0/",
        "attribution": "A state geological survey",
        "redistributable": True,
        "citation": "A state geological survey (2025). Clay pits of Kachchh.",
        "landing_url": "https://example.org/clay-pits",
        "url": "https://example.org/clay-pits.geojson",
        "sha256": hashlib.sha256(data).hexdigest(),
        "layer": PLAN,
    }
    return DatasetProposal.model_validate(body)


async def proposed(session: AsyncSession, proposer: User, code: str) -> proposals.StoredDataset:
    issued = await proposals.issue_dataset_slot(session, proposer, record(code), now=NOW)
    return await proposals.fill_dataset_slot(session, issued.token, LAYER, now=NOW + timedelta(minutes=5))


async def layer_row(session: AsyncSession, dataset_id: uuid.UUID) -> MapLayerProposal:
    row = await session.scalar(select(MapLayerProposal).where(MapLayerProposal.datasetId == dataset_id))
    assert row is not None
    return row


async def listed(session: AsyncSession, viewer: User) -> list[uuid.UUID]:
    page = await list_review_queue(session, viewer, ReviewFilters(kind="LAYERS"), adapters=ADAPTERS, now=NOW)
    return [item.id for item in page.items]


async def test_a_filled_layer_slot_stores_its_record_and_a_pending_layer_and_no_table(
    session: AsyncSession,
) -> None:
    stored = await proposed(session, await person(session, "RESEARCHER"), "KV_TEST_CLAY_PITS")
    assert stored.table is None and stored.layer is not None and stored.layer.features == 2
    assert (stored.dataset.origin, stored.dataset.crs) == ("CONTRIBUTED", "EPSG:4326")
    row = await layer_row(session, stored.dataset.id)
    assert (row.status, row.featureCount, row.byteSize) == ("PENDING", 2, len(LAYER))
    assert row.sha256 == hashlib.sha256(LAYER).hexdigest() and row.layer == SITES
    assert row.plan["layerClass"] == "POINT_SITES" and row.proposerId == stored.dataset.proposedById
    tables = await session.scalar(
        select(func.count()).select_from(DatasetTable).where(DatasetTable.datasetId == stored.dataset.id)
    )
    assert tables == 0


async def test_a_layer_outside_india_s_frame_stores_nothing(session: AsyncSession) -> None:
    researcher = await person(session, "RESEARCHER")
    issued = await proposals.issue_dataset_slot(session, researcher, record("KV_TEST_FAR_PITS", FAR), now=NOW)
    with pytest.raises(InvalidInput, match="outside India's frame"):
        await proposals.fill_dataset_slot(session, issued.token, FAR, now=NOW)
    held = await session.scalar(select(EnvDataset.id).where(EnvDataset.code == "KV_TEST_FAR_PITS"))
    assert held is None


async def test_an_admin_who_did_not_propose_it_reviews_it_and_its_proposer_never_does(
    session: AsyncSession,
) -> None:
    proposer = await person(session, "ADMIN")
    reviewer = await person(session, "ADMIN")
    stored = await proposed(session, proposer, "KV_TEST_REVIEWED_PITS")
    row = await layer_row(session, stored.dataset.id)
    page = await list_review_queue(
        session, reviewer, ReviewFilters(kind="LAYERS"), adapters=ADAPTERS, now=NOW
    )
    shown = next(item for item in page.items if item.id == row.id)
    assert isinstance(shown, LayerQueueItem) and shown.craft is None
    assert (shown.layer.geometry, shown.layer.features, shown.layer.dataset.code) == (
        "POINT",
        2,
        "KV_TEST_REVIEWED_PITS",
    )
    bounds = shown.layer.bounds
    assert (bounds.west, bounds.south, bounds.east, bounds.north) == (69.75, 22.5, 72.5, 23.25)
    assert row.id not in await listed(session, proposer)
    assert row.id not in await listed(session, await person(session, "PROFESSOR"))
    with pytest.raises(OwnItem):
        await approve_item(session, ItemRef("LAYERS", row.id), proposer, QueueApproval(), now=NOW)


async def test_approving_and_rejecting_move_the_layer_with_an_audit_row(session: AsyncSession) -> None:
    proposer = await person(session, "RESEARCHER")
    reviewer = await person(session, "ADMIN")
    first = await layer_row(session, (await proposed(session, proposer, "KV_TEST_APPROVED_PITS")).dataset.id)
    second = await layer_row(session, (await proposed(session, proposer, "KV_TEST_REJECTED_PITS")).dataset.id)
    approved = await approve_item(
        session, ItemRef("LAYERS", first.id), reviewer, QueueApproval(note="Checked."), now=NOW
    )
    rejection = QueueRejection(reason="The licence page does not allow redistribution.")
    rejected = await reject_item(session, ItemRef("LAYERS", second.id), reviewer, rejection, now=NOW)
    assert (approved.kind, approved.status, rejected.status) == ("LAYERS", "APPROVED", "REJECTED")
    assert "tools/maplayers" in approved.message
    await session.flush()
    assert (first.reviewedById, first.reviewNote, second.reviewNote) == (
        reviewer.id,
        "Checked.",
        "The licence page does not allow redistribution.",
    )
    actions = await session.scalars(
        select(AuditLog.action)
        .where(AuditLog.targetId.in_([str(first.id), str(second.id)]))
        .order_by(AuditLog.action)
    )
    assert actions.all() == ["review.layer_approved", "review.layer_rejected"]
    assert first.id not in await listed(session, reviewer)
