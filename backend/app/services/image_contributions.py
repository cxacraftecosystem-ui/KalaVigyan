from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ImageContribution, MediaAsset, PictureDeclaration, User
from app.research.image_contributions import ImageBatch, ImageDeclaration

from .image_contributions_checks import check_claims, checked_craft, checked_target
from .image_contributions_errors import ContributionRefused, UnknownImage
from .image_contributions_store import APPROVED, PENDING, REJECTED, Decision, decide, stored
from .image_contributions_views import views
from .image_screens import Screened, ScreenTools, screened
from .object_store import ObjectStore

__all__ = [
    "AWAITING_FILE",
    "ContributionRefused",
    "Filing",
    "UnknownImage",
    "Upload",
    "approve",
    "declare",
    "declare_batch",
    "own_images",
    "queue",
    "receive_file",
    "reject",
    "store_screened",
    "views",
    "withdraw",
]

AWAITING_FILE = "AWAITING_FILE"
WITHDRAWN = "WITHDRAWN"
WITHDRAWABLE = (AWAITING_FILE, PENDING)
APPROVED_STAYS = "An approved picture stays published: the consent to publish it cannot be revoked."
HAS_PICTURE = "This contribution already has its picture"
LIST_MAX = 100


@dataclass(frozen=True)
class Upload:
    contribution_id: uuid.UUID
    user: User
    data: bytes


@dataclass(frozen=True)
class Filing:
    channel: str
    confirmation: str | None = None


async def declare(
    session: AsyncSession,
    user: User,
    declaration: ImageDeclaration,
    *,
    now: datetime,
    declaration_id: uuid.UUID | None = None,
) -> ImageContribution:
    craft = await checked_craft(session, declaration.craft_slug)
    aimed = await checked_target(session, craft, declaration)
    await check_claims(session, aimed.claim_ids)
    row = ImageContribution(
        contributorId=user.id,
        craftId=craft.id,
        stageId=aimed.stage_id,
        materialId=aimed.material_id,
        slot=aimed.slot,
        taskKey=aimed.task_key,
        declarationId=declaration_id,
        claimIds=list(aimed.claim_ids),
        origin=aimed.origin,
        generator=aimed.generator,
        prompt=aimed.prompt,
        caption=aimed.caption,
        altText=aimed.alt_text,
        termsVersion=aimed.terms_version,
        rightsConfirmedAt=now,
        status=AWAITING_FILE,
    )
    session.add(row)
    await session.flush()
    return row


async def declare_batch(
    session: AsyncSession, user: User, batch: ImageBatch, filing: Filing, *, now: datetime
) -> list[ImageContribution]:
    craft = await checked_craft(session, batch.craft_slug)
    record = PictureDeclaration(
        contributorId=user.id,
        craftId=craft.id,
        channel=filing.channel,
        origin=batch.origin,
        generator=batch.generator,
        termsVersion=batch.terms_version,
        rightsConfirmedAt=now,
        confirmation=filing.confirmation,
        pictures=len(batch.pictures),
    )
    session.add(record)
    await session.flush()
    return [
        await declare(session, user, declared, now=now, declaration_id=record.id)
        for declared in batch.declarations()
    ]


async def receive_file(
    session: AsyncSession, upload: Upload, *, objects: ObjectStore, tools: ScreenTools, now: datetime
) -> ImageContribution:
    row = await _own(session, upload.contribution_id, upload.user, lock=False)
    _refuse_filled(row)
    screen = await screened(session, upload.data, origin=row.origin, user=upload.user, tools=tools)
    return await store_screened(
        session, upload.contribution_id, upload.user, screen, objects=objects, now=now
    )


async def store_screened(
    session: AsyncSession,
    contribution_id: uuid.UUID,
    user: User,
    screen: Screened,
    *,
    objects: ObjectStore,
    now: datetime,
) -> ImageContribution:
    row = await _own(session, contribution_id, user, lock=True)
    _refuse_filled(row)
    return await stored(session, row, user, screen, objects=objects, now=now)


async def approve(
    session: AsyncSession, contribution_id: uuid.UUID, reviewer: User, note: str | None, *, now: datetime
) -> ImageContribution:
    row, asset = await _reviewable(session, contribution_id, reviewer)
    await decide(session, row, asset, Decision(reviewer, APPROVED, note, now))
    await session.flush()
    return row


async def reject(
    session: AsyncSession, contribution_id: uuid.UUID, reviewer: User, note: str, *, now: datetime
) -> ImageContribution:
    row, asset = await _reviewable(session, contribution_id, reviewer)
    await decide(session, row, asset, Decision(reviewer, REJECTED, note, now))
    await session.flush()
    return row


async def withdraw(session: AsyncSession, contribution_id: uuid.UUID, user: User) -> ImageContribution:
    row = await _own(session, contribution_id, user, lock=True)
    if row.status == APPROVED:
        raise ContributionRefused(APPROVED_STAYS)
    if row.status not in WITHDRAWABLE:
        raise ContributionRefused("This contribution is already closed")
    row.status = WITHDRAWN
    await session.flush()
    return row


async def queue(session: AsyncSession, status: str) -> list[ImageContribution]:
    rows = await session.scalars(
        select(ImageContribution)
        .where(ImageContribution.status == status)
        .order_by(ImageContribution.createdAt, ImageContribution.id)
        .limit(LIST_MAX)
    )
    return list(rows)


async def own_images(session: AsyncSession, user: User) -> list[ImageContribution]:
    rows = await session.scalars(
        select(ImageContribution)
        .where(ImageContribution.contributorId == user.id)
        .order_by(ImageContribution.createdAt.desc(), ImageContribution.id)
        .limit(LIST_MAX)
    )
    return list(rows)


def _refuse_filled(row: ImageContribution) -> None:
    if row.status != AWAITING_FILE:
        raise ContributionRefused(HAS_PICTURE)


async def _reviewable(
    session: AsyncSession, contribution_id: uuid.UUID, reviewer: User
) -> tuple[ImageContribution, MediaAsset | None]:
    row = await session.get(ImageContribution, contribution_id, with_for_update=True)
    if row is None:
        raise UnknownImage(str(contribution_id))
    if row.status != PENDING:
        raise ContributionRefused("Only a picture waiting for review can be decided")
    if row.contributorId == reviewer.id:
        raise ContributionRefused("A reviewer does not decide their own picture")
    asset = await session.get(MediaAsset, row.assetId) if row.assetId is not None else None
    return row, asset


async def _own(
    session: AsyncSession, contribution_id: uuid.UUID, user: User, *, lock: bool
) -> ImageContribution:
    row = await session.get(
        ImageContribution, contribution_id, with_for_update=lock or None, populate_existing=lock
    )
    if row is None or row.contributorId != user.id:
        raise UnknownImage(str(contribution_id))
    return row
