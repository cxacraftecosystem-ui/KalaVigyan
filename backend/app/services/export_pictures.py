from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from io import BytesIO
from typing import Protocol

from app.core.errors import AppError
from app.research.media_refs import MediaRef

__all__ = [
    "PICTURE_MAX_PIXELS",
    "PICTURE_MAX_SIDE",
    "ExportPictures",
    "Picture",
    "PictureSource",
    "export_pictures",
    "normalised",
]

logger = logging.getLogger(__name__)

PICTURE_MAX_SIDE = 1600
PICTURE_MAX_PIXELS = 40_000_000
JPEG_QUALITY = 85
WHITE = (255, 255, 255)


@dataclass(frozen=True)
class Picture:
    data: bytes
    width: int
    height: int


@dataclass(frozen=True)
class ExportPictures:
    found: Mapping[uuid.UUID, Picture]
    unread: frozenset[uuid.UUID] = frozenset()


class PictureSource(Protocol):
    async def picture(self, url: str) -> bytes: ...


async def export_pictures(medias: Iterable[MediaRef], source: PictureSource) -> ExportPictures:
    found: dict[uuid.UUID, Picture] = {}
    unread: set[uuid.UUID] = set()
    for media in medias:
        if media.id in found or media.id in unread:
            continue
        try:
            raw = await source.picture(media.image_url)
        except AppError as error:
            logger.warning("picture %s is left out of the export: %s", media.id, error)
            unread.add(media.id)
            continue
        picture = await asyncio.to_thread(normalised, raw)
        if picture is None:
            logger.warning("picture %s is not an image a document can hold", media.id)
            continue
        found[media.id] = picture
    return ExportPictures(found=found, unread=frozenset(unread))


def normalised(raw: bytes) -> Picture | None:
    from PIL import Image, UnidentifiedImageError

    try:
        with Image.open(BytesIO(raw)) as opened:
            if opened.width * opened.height > PICTURE_MAX_PIXELS:
                return None
            image = opened.convert("RGBA")
    except UnidentifiedImageError, OSError, Image.DecompressionBombError:
        return None
    flat = Image.new("RGB", image.size, WHITE)
    flat.paste(image, mask=image.getchannel("A"))
    flat.thumbnail((PICTURE_MAX_SIDE, PICTURE_MAX_SIDE))
    out = BytesIO()
    flat.save(out, format="JPEG", quality=JPEG_QUALITY)
    return Picture(data=out.getvalue(), width=flat.width, height=flat.height)
