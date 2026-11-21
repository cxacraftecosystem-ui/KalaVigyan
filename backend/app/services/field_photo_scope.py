from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import ColumnElement, ScalarSelect, and_, exists, func, not_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models import FieldImage, FieldPhotoReview
from app.research.field_photo_reviews import CROP, SHOWING_DECISIONS
from app.retrieval.field_scope import shown_images

__all__ = ["ServedPhoto", "served_photo", "shown_field_photos", "shown_size"]


@dataclass(frozen=True)
class ServedPhoto:
    key: str


def shown_field_photos(craft_id: uuid.UUID | None = None) -> list[ColumnElement[bool]]:
    held = and_(FieldImage.artisanLinked.is_(False), not_(_reviewed()))
    return [*shown_images(craft_id), or_(held, _decided_to_show())]


def shown_size() -> tuple[ColumnElement[Any], ColumnElement[Any]]:
    review = aliased(FieldPhotoReview)
    width = _cropped(review, review.cropWidth)
    height = _cropped(review, review.cropHeight)
    return func.coalesce(width, FieldImage.width), func.coalesce(height, FieldImage.height)


async def served_photo(session: AsyncSession, image_id: uuid.UUID) -> ServedPhoto | None:
    review = aliased(FieldPhotoReview)
    found = (
        await session.execute(
            select(FieldImage.objectKey, _cropped(review, review.cropKey)).where(
                FieldImage.id == image_id, *shown_field_photos()
            )
        )
    ).first()
    if found is None:
        return None
    original, crop = found
    return ServedPhoto(key=crop or original)


def _reviewed() -> ColumnElement[bool]:
    review = aliased(FieldPhotoReview)
    return exists(select(review.id).where(review.imageId == FieldImage.id))


def _decided_to_show() -> ColumnElement[bool]:
    review = aliased(FieldPhotoReview)
    current = and_(review.imageId == FieldImage.id, review.imageSha256 == FieldImage.sha256)
    return exists(select(review.id).where(current, review.decision.in_(SHOWING_DECISIONS)))


def _cropped(review: Any, column: Any) -> ScalarSelect[Any]:
    current = and_(review.imageId == FieldImage.id, review.imageSha256 == FieldImage.sha256)
    return select(column).where(current, review.decision == CROP).scalar_subquery()
