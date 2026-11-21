from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import INDIA_TZ
from app.core.errors import InvalidInput
from app.models import FieldImage, FieldImageCraft
from app.research.field_voices import (
    ARTISAN_IMAGE_VISIBILITIES,
    ARTISAN_IMAGES_HIDDEN,
    ARTISAN_IMAGES_SETTING,
    FIELD_LIST_PAGE_SIZE,
    HELD_IMAGES_SCHEMA_VERSION,
    HeldImage,
    HeldImageList,
)
from app.retrieval.field_scope import held_images
from app.services import app_settings
from app.services.field_voices_reading import list_offset

__all__ = [
    "artisan_image_visibility",
    "held_image_list",
    "held_image_of",
    "held_photo_crafts",
    "set_artisan_image_visibility",
]

UNKNOWN_VISIBILITY = "Visibility is HIDDEN or SHOWN."


async def artisan_image_visibility(session: AsyncSession) -> str:
    value = await app_settings.get_value(session, ARTISAN_IMAGES_SETTING)
    return value if value in ARTISAN_IMAGE_VISIBILITIES else ARTISAN_IMAGES_HIDDEN


async def set_artisan_image_visibility(session: AsyncSession, visibility: str, *, actor_id: Any) -> str:
    if visibility not in ARTISAN_IMAGE_VISIBILITIES:
        raise InvalidInput(UNKNOWN_VISIBILITY)
    await app_settings.set_value(session, ARTISAN_IMAGES_SETTING, visibility, updated_by_id=actor_id)
    return visibility


def held_image_of(row: FieldImage) -> HeldImage:
    context = row.context or {}
    people = {person.get("id"): person for person in row.people or []}
    credited = [people[c["personId"]].get("name") for c in row.credits or [] if c.get("personId") in people]
    return HeldImage(
        id=row.id,
        item_id=f"{row.portal}:{row.portalMediaId}",
        origin=row.portal,
        caption=row.caption,
        taken_on=row.takenAt.astimezone(INDIA_TZ).date() if row.takenAt else None,
        crafts=[craft.get("name") for craft in context.get("crafts") or [] if craft.get("name")],
        placements=[group.get("label") for group in context.get("groups") or [] if group.get("label")],
        credited=[name for name in credited if name],
        width=row.width,
        height=row.height,
    )


async def held_image_list(session: AsyncSession, *, cursor: str | None) -> HeldImageList:
    offset = list_offset(cursor)
    held = held_images()
    rows = await session.scalars(
        select(FieldImage)
        .where(*held)
        .order_by(FieldImage.takenAt.desc().nulls_last(), FieldImage.id)
        .offset(offset)
        .limit(FIELD_LIST_PAGE_SIZE)
    )
    total = int(await session.scalar(select(func.count()).select_from(FieldImage).where(*held)) or 0)
    following = offset + FIELD_LIST_PAGE_SIZE
    return HeldImageList(
        schema_version=HELD_IMAGES_SCHEMA_VERSION,
        visibility=await artisan_image_visibility(session),
        total=total,
        cursor=cursor,
        next_cursor=str(following) if following < total else None,
        images=[held_image_of(row) for row in rows],
    )


async def held_photo_crafts(session: AsyncSession) -> set[uuid.UUID]:
    held = select(FieldImage.id).where(*held_images())
    crafts = await session.scalars(
        select(FieldImageCraft.craftId).where(FieldImageCraft.imageId.in_(held)).distinct()
    )
    return set(crafts.all())
