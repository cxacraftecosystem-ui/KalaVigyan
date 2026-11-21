from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.core.clock import INDIA_TZ
from app.models import FieldImage, FieldPhotoReview, FieldPhotoScreen
from app.research.field_photo_reviews import (
    HIDDEN,
    HIDE,
    SHOWN,
    WAITING,
    FieldPhotoItem,
    PhotoCrop,
    PhotoDecisionView,
    PhotoHistoryEntry,
    PhotoPerson,
    PhotoScreenView,
    master_flags,
    photo_risk,
)
from app.research.field_voices import PORTAL_PUBLISHERS

from .field_photo_crops import PhotoObjects
from .field_photo_decisions import names_someone
from .naming import content_disposition

__all__ = ["LINK_SECONDS", "PhotoRow", "Shown", "photo_item", "photo_state"]

LINK_SECONDS = 600
FALLBACK_ALT = "A photograph from the field"


@dataclass(frozen=True)
class PhotoRow:
    image: FieldImage
    review: FieldPhotoReview | None
    screen: FieldPhotoScreen | None
    decider: str | None


@dataclass(frozen=True)
class Shown:
    objects: PhotoObjects | None
    now: datetime
    history: Mapping[str, Sequence[PhotoHistoryEntry]]


def photo_state(image: FieldImage, review: FieldPhotoReview | None) -> str:
    if review is None or review.imageSha256 != image.sha256:
        return WAITING
    return HIDDEN if review.decision == HIDE else SHOWN


def photo_item(row: PhotoRow, shown: Shown) -> FieldPhotoItem:
    image, screen = row.image, row.screen
    context = image.context or {}
    flags = list(screen.flags) if screen is not None else None
    return FieldPhotoItem(
        id=image.id,
        item_id=f"{image.portal}:{image.portalMediaId}",
        origin=image.portal,
        publisher=PORTAL_PUBLISHERS[image.portal],
        sha256=image.sha256,
        caption=image.caption,
        alt=context.get("alt") or FALLBACK_ALT,
        taken_on=image.takenAt.astimezone(INDIA_TZ).date() if image.takenAt else None,
        crafts=[craft.get("name") for craft in context.get("crafts") or [] if craft.get("name")],
        placements=[group.get("label") for group in context.get("groups") or [] if group.get("label")],
        people=[_person(person) for person in image.people or [] if isinstance(person, dict)],
        credit=context.get("credit") or image.rightsHolder,
        workshop=context.get("workshopLine") or None,
        statement=image.statement,
        rights_holder=image.rightsHolder,
        licence=image.licence,
        width=image.width,
        height=image.height,
        mime=image.mimeType,
        file_url=_link(shown, image.objectKey),
        state=photo_state(image, row.review),
        risk=photo_risk(flags),
        master_only=bool(master_flags(flags, someone_named=names_someone(image))),
        screen=_screen(screen),
        decision=_decision(row, shown),
        history=list(shown.history.get(str(image.id), ())),
    )


def _person(person: Mapping[str, Any]) -> PhotoPerson:
    return PhotoPerson(name=person.get("name") or None, kind=person.get("kind") or None)


def _screen(screen: FieldPhotoScreen | None) -> PhotoScreenView | None:
    if screen is None:
        return None
    return PhotoScreenView(
        verdict=screen.verdict,
        flags=list(screen.flags),
        reasons=list(screen.reasons),
        nearest_distance=screen.nearestDistance,
        model=screen.model,
        screened_at=screen.screenedAt,
    )


def _decision(row: PhotoRow, shown: Shown) -> PhotoDecisionView | None:
    review = row.review
    if review is None:
        return None
    crop = None
    if review.cropLeft is not None and review.cropTop is not None and review.cropWidth and review.cropHeight:
        crop = PhotoCrop(
            left=review.cropLeft, top=review.cropTop, width=review.cropWidth, height=review.cropHeight
        )
    return PhotoDecisionView(
        decision=review.decision,
        reason=review.reason,
        note=review.note,
        cleared_flags=list(review.clearedFlags),
        crop=crop,
        crop_url=_link(shown, review.cropKey),
        decided_at=review.decidedAt,
        decided_by=row.decider,
        decided_role=review.deciderRole,
        current=review.imageSha256 == row.image.sha256,
    )


def _link(shown: Shown, key: str | None) -> str | None:
    if shown.objects is None or key is None:
        return None
    leaf = key.rsplit("/", 1)[-1]
    return shown.objects.presigned_get(
        key, disposition=content_disposition(leaf, inline=True), seconds=LINK_SECONDS, now=shown.now
    ).url
