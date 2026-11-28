from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, InvalidInput
from app.research.image_intake_pixels import PREVIEW_MIME, thumbnail

from .field_photo_plates import ClearedPhoto
from .field_photo_scope import served_photo

__all__ = ["THUMBNAIL_READS_AT_ONCE", "PhotoThumbnail", "StoredPhotos", "field_photo_thumbnails"]

THUMBNAIL_READS_AT_ONCE = 4
logger = logging.getLogger(__name__)


class StoredPhotos(Protocol):
    async def get(self, key: str) -> bytes | None: ...


@dataclass(frozen=True)
class PhotoThumbnail:
    label: str
    caption: str
    data: bytes
    mime: str = PREVIEW_MIME


async def field_photo_thumbnails(
    session: AsyncSession, photos: Sequence[ClearedPhoto], objects: StoredPhotos
) -> list[PhotoThumbnail]:
    served = [(photo, await served_photo(session, photo.image_id)) for photo in photos]
    reads = asyncio.Semaphore(THUMBNAIL_READS_AT_ONCE)
    made = await asyncio.gather(
        *(_thumbnail(photo, found.key, objects, reads) for photo, found in served if found is not None)
    )
    return [shown for shown in made if shown is not None]


async def _thumbnail(
    photo: ClearedPhoto, key: str, objects: StoredPhotos, reads: asyncio.Semaphore
) -> PhotoThumbnail | None:
    async with reads:
        try:
            data = await objects.get(key)
        except AppError as error:
            logger.warning("field photograph %s could not be read: %s", photo.image_id, error)
            return None
    if data is None:
        logger.warning("field photograph %s has no stored copy", photo.image_id)
        return None
    try:
        small = await asyncio.to_thread(thumbnail, data)
    except InvalidInput as refused:
        logger.warning("field photograph %s could not be made small: %s", photo.image_id, refused)
        return None
    return PhotoThumbnail(label=photo.label, caption=photo.caption, data=small)
