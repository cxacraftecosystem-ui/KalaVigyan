from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput
from app.models import FieldImage, FieldPhotoReview
from app.research.field_photo_reviews import PhotoCrop
from app.research.image_intake_pixels import cropped

from .naming import field_voice_key
from .object_store import PresignedGet

__all__ = [
    "OpenSession",
    "PhotoObjects",
    "PhotoRefused",
    "StoredCrop",
    "made_crop",
    "release_crop",
    "sweep_withdrawn_reviews",
]

OpenSession = Callable[[], AbstractAsyncContextManager[AsyncSession]]
NO_STORE = "Photographs cannot be stored right now. Try again later."
NO_COPY = "The stored copy of this photograph is missing, so it cannot be cropped."
OUTSIDE = "The region to keep lies outside the photograph."
WHOLE = "A crop leaves out part of the photograph; to show all of it, choose Show."


class PhotoObjects(Protocol):
    async def get(self, key: str) -> bytes | None: ...

    async def put(self, key: str, body: bytes, *, content_type: str) -> None: ...

    async def delete(self, key: str) -> None: ...

    def presigned_get(self, key: str, *, disposition: str, seconds: int, now: datetime) -> PresignedGet: ...


class PhotoRefused(Exception):
    def __init__(self, detail: str, status: int) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status = status


@dataclass(frozen=True)
class StoredCrop:
    key: str
    sha256: str
    mime: str
    width: int
    height: int


async def made_crop(objects: PhotoObjects | None, image: FieldImage, crop: PhotoCrop) -> StoredCrop:
    if objects is None:
        raise PhotoRefused(NO_STORE, 503)
    if not crop.inside(image.width, image.height):
        raise PhotoRefused(OUTSIDE, 422)
    if not crop.leaves_out(image.width, image.height):
        raise PhotoRefused(WHOLE, 422)
    original = await objects.get(image.objectKey)
    if original is None:
        raise PhotoRefused(NO_COPY, 409)
    try:
        made = await asyncio.to_thread(cropped, original, crop.box(), image.mimeType)
    except InvalidInput as invalid:
        raise PhotoRefused(str(invalid), 422) from invalid
    digest = hashlib.sha256(made.data).hexdigest()
    key = field_voice_key(digest, image.objectKey.rsplit("/", 1)[-1])
    await objects.put(key, made.data, content_type=made.mime)
    return StoredCrop(key=key, sha256=digest, mime=made.mime, width=made.width, height=made.height)


async def release_crop(session: AsyncSession, objects: PhotoObjects | None, key: str | None) -> bool:
    if objects is None or key is None or await _in_use(session, key):
        return False
    await objects.delete(key)
    return True


async def sweep_withdrawn_reviews(open_session: OpenSession, objects: PhotoObjects | None) -> int:
    async with open_session() as session:
        rows = (
            await session.execute(
                select(FieldPhotoReview.id, FieldPhotoReview.cropKey).where(
                    FieldPhotoReview.imageId.is_(None)
                )
            )
        ).all()
        if not rows:
            return 0
        await session.execute(
            delete(FieldPhotoReview).where(FieldPhotoReview.id.in_([row.id for row in rows]))
        )
        await session.commit()
        for key in sorted({row.cropKey for row in rows if row.cropKey}):
            await release_crop(session, objects, key)
    return len(rows)


async def _in_use(session: AsyncSession, key: str) -> bool:
    reviews = select(func.count()).select_from(FieldPhotoReview).where(FieldPhotoReview.cropKey == key)
    images = select(func.count()).select_from(FieldImage).where(FieldImage.objectKey == key)
    return int(await session.scalar(reviews) or 0) + int(await session.scalar(images) or 0) > 0
