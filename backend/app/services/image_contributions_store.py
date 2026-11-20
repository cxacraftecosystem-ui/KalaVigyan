from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.roles import PROFESSOR, has_rank
from app.models import Craft, ImageContribution, MediaAsset, User
from app.research.image_contributions import AI_GENERATED
from app.research.image_intake_types import AVIF, JPEG, PNG, SVG, WEBP

from .image_screens import Screened, recorded_screen
from .naming import PlaceParts, file_name, media_key
from .object_store import ObjectStore
from .task_reservations import complete_task

__all__ = ["APPROVED", "PENDING", "REJECTED", "Decision", "decide", "stored"]

PENDING = "PENDING"
APPROVED = "APPROVED"
REJECTED = "REJECTED"
SHARED = "CRAFT_SHARED"
PRIVATE = "PRIVATE"
EXTENSIONS = {PNG: "png", JPEG: "jpg", WEBP: "webp", AVIF: "avif", SVG: "svg"}
FILE_WHAT = {"PHOTOGRAPH": "Photo", "DRAWING": "Drawing", AI_GENERATED: "Illustration"}


@dataclass(frozen=True)
class Decision:
    reviewer: User
    status: str
    note: str | None
    now: datetime


async def stored(
    session: AsyncSession,
    row: ImageContribution,
    user: User,
    screen: Screened,
    *,
    objects: ObjectStore,
    now: datetime,
) -> ImageContribution:
    image = screen.image
    craft = await session.get(Craft, row.craftId)
    key = media_key(user.id, _leaf(row, craft, image.mime, now))
    await objects.put(key, image.data, content_type=image.mime)
    asset = MediaAsset(
        s3Key=key,
        mime=image.mime,
        bytes=len(image.data),
        width=image.width,
        height=image.height,
        label=row.caption,
        model=row.generator,
        altText=row.altText,
        visibility=PRIVATE,
    )
    session.add(asset)
    await session.flush()
    row.assetId, row.sha256, row.aiMarked, row.status = asset.id, screen.digest, image.ai_marked, PENDING
    recorded_screen(session, row, asset, screen)
    if has_rank(user, PROFESSOR) and screen.clear:
        await decide(session, row, asset, Decision(user, APPROVED, None, now))
    await session.flush()
    return row


async def decide(
    session: AsyncSession, row: ImageContribution, asset: MediaAsset | None, decision: Decision
) -> None:
    row.status = decision.status
    row.reviewedById = decision.reviewer.id
    row.reviewedAt = decision.now
    row.reviewNote = decision.note
    approved = decision.status == APPROVED
    if asset is not None:
        asset.visibility = SHARED if approved else PRIVATE
        asset.approvedById = decision.reviewer.id if approved else None
    if approved and row.taskKey is not None and row.contributorId is not None:
        await complete_task(session, row.contributorId, row.taskKey, now=decision.now)


def _leaf(row: ImageContribution, craft: Craft | None, mime: str, now: datetime) -> str:
    return file_name(
        entity="Contribution",
        what=FILE_WHAT[row.origin],
        ext=EXTENSIONS[mime],
        moment=now,
        place=PlaceParts(),
        craft=craft.name if craft else None,
        subject=row.caption,
        sequence=None,
    )
