from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.roles import MASTER_ADMIN, role_value
from app.models import FieldImage, FieldImageCraft, FieldPhotoReview, FieldPhotoScreen, User
from app.research.field_photo_reviews import (
    CROP,
    DECIDED_ACTION,
    PHOTO_TARGET,
    SHOW,
    SHOWING_DECISIONS,
    PhotoDecisionRequest,
    master_flags,
)

from . import audit
from .field_photo_crops import PhotoObjects, PhotoRefused, StoredCrop, made_crop
from .page_revalidation import craft_owners, refresh_pages

__all__ = ["Decided", "UnknownPhoto", "decide_photo", "names_someone", "refresh_photo_pages"]

CHANGED = "The photograph changed since you opened it. Reload it and look again."
SCREEN_FIRST = "The screens have not looked at this copy yet. Screen it first, then decide."
MASTER_ONLY = (
    "Only a Master Admin can show a photograph the screen flagged as an identity document or as a "
    "face its record names no one for."
)
CLEAR_OR_CROP = "Clear the screen's flag with a note, or show a crop that leaves the region out."


class UnknownPhoto(LookupError):
    pass


@dataclass(frozen=True)
class Decided:
    image_id: uuid.UUID
    made_key: str | None
    released_key: str | None


def names_someone(image: FieldImage) -> bool:
    return any(isinstance(person, dict) and person.get("name") for person in image.people or [])


async def decide_photo(
    session: AsyncSession,
    image_id: uuid.UUID,
    request: PhotoDecisionRequest,
    *,
    actor: User,
    objects: PhotoObjects | None,
) -> Decided:
    image = await session.get(FieldImage, image_id, with_for_update=True, populate_existing=True)
    if image is None:
        raise UnknownPhoto(str(image_id))
    if request.seen_sha256 != image.sha256:
        raise PhotoRefused(CHANGED, 409)
    risky = await _checked(session, image, request, actor)
    crop = (
        await made_crop(objects, image, request.crop) if request.decision == CROP and request.crop else None
    )
    cleared = list(risky) if request.decision == SHOW and request.clear_flags else []
    review, previous = await _write(session, image, request, (actor, crop, cleared))
    await audit.record(
        session,
        action=DECIDED_ACTION,
        actor=actor,
        target_type=PHOTO_TARGET,
        target_id=image.id,
        detail=_detail(image, review),
    )
    released = previous if previous is not None and previous != review.cropKey else None
    return Decided(image_id=image.id, made_key=crop.key if crop else None, released_key=released)


async def refresh_photo_pages(session: AsyncSession, image_id: uuid.UUID) -> bool:
    crafts = await session.scalars(select(FieldImageCraft.craftId).where(FieldImageCraft.imageId == image_id))
    return await refresh_pages(await craft_owners(session, set(crafts.all())))


async def _checked(
    session: AsyncSession, image: FieldImage, request: PhotoDecisionRequest, actor: User
) -> tuple[str, ...]:
    if request.decision not in SHOWING_DECISIONS:
        return ()
    screen = await session.get(FieldPhotoScreen, image.id, populate_existing=True)
    if screen is None or screen.imageSha256 != image.sha256:
        raise PhotoRefused(SCREEN_FIRST, 409)
    risky = master_flags(screen.flags, someone_named=names_someone(image))
    if risky and role_value(actor) != MASTER_ADMIN:
        raise PhotoRefused(MASTER_ONLY, 403)
    if risky and request.decision == SHOW and not request.clear_flags:
        raise PhotoRefused(CLEAR_OR_CROP, 409)
    return risky


async def _write(
    session: AsyncSession,
    image: FieldImage,
    request: PhotoDecisionRequest,
    made: tuple[User, StoredCrop | None, Sequence[str]],
) -> tuple[FieldPhotoReview, str | None]:
    actor, crop, cleared = made
    review = await session.scalar(
        select(FieldPhotoReview)
        .where(FieldPhotoReview.imageId == image.id)
        .execution_options(populate_existing=True)
    )
    if review is None:
        review = FieldPhotoReview(imageId=image.id)
        session.add(review)
    previous = review.cropKey
    review.imageSha256 = image.sha256
    review.decision = request.decision
    review.reason = request.reason
    review.note = (request.note or "").strip() or None
    review.clearedFlags = list(cleared)
    _crop_columns(review, crop, request)
    review.deciderId = actor.id
    review.deciderRole = role_value(actor)
    review.decidedAt = datetime.now(UTC)
    await session.flush()
    return review, previous


def _crop_columns(review: FieldPhotoReview, crop: StoredCrop | None, request: PhotoDecisionRequest) -> None:
    box = request.crop if crop is not None else None
    review.cropLeft = box.left if box else None
    review.cropTop = box.top if box else None
    review.cropWidth = crop.width if crop else None
    review.cropHeight = crop.height if crop else None
    review.cropKey = crop.key if crop else None
    review.cropSha256 = crop.sha256 if crop else None
    review.cropMime = crop.mime if crop else None


def _detail(image: FieldImage, review: FieldPhotoReview) -> dict[str, Any]:
    crop = None
    if review.cropKey is not None:
        crop = {
            "left": review.cropLeft,
            "top": review.cropTop,
            "width": review.cropWidth,
            "height": review.cropHeight,
        }
    return {
        "itemId": f"{image.portal}:{image.portalMediaId}",
        "imageSha256": review.imageSha256,
        "decision": review.decision,
        "reason": review.reason,
        "note": review.note,
        "clearedFlags": list(review.clearedFlags),
        "crop": crop,
        "decidedAt": review.decidedAt.isoformat(),
    }
