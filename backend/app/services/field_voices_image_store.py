from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.craft_master_loader import ID_NAMESPACE
from app.models import FieldImage, FieldImageCraft, MediaRef
from app.research.field_voices import PORTAL_PROVIDERS, PORTAL_PUBLISHERS
from app.services.field_voices_feed import Live
from app.services.field_voices_illustrations import link_photo_claims, photo_described
from app.services.field_voices_images import StoredCopy
from app.services.field_voices_items import ImageItem
from app.services.field_voices_photos import PhotoPlan, photo_plan
from app.services.field_voices_store import ApplyContext, resolve_crafts
from app.services.media_ref_store import INLINE_DISPLAY, media_ref_id, media_url_key
from app.services.object_store import ObjectStore

__all__ = [
    "IMAGE_ROUTE",
    "AppliedImage",
    "apply_image",
    "delete_orphaned_copy",
    "field_image_id",
    "image_needs_copy",
    "image_route_url",
    "withdraw_image",
]

IMAGE_ROUTE = "/api/field-voices/images/{id}"


@dataclass(frozen=True)
class AppliedImage:
    changed: bool
    orphaned_key: str | None = None


def field_image_id(portal: str, media_id: str) -> uuid.UUID:
    return uuid.uuid5(ID_NAMESPACE, f"field-image:{portal}:{media_id}")


def image_route_url(api_base: str, image_id: uuid.UUID) -> str:
    return f"{api_base.rstrip('/')}{IMAGE_ROUTE.format(id=image_id)}"


async def image_needs_copy(session: AsyncSession, change: Live, *, portal: str) -> bool:
    row = await session.get(FieldImage, field_image_id(portal, change.id))
    item = change.item
    if not isinstance(item, ImageItem):
        raise TypeError(f"image change {change.id} carries a transcript")
    return row is None or row.portalSha256 != item.image.sha256


async def apply_image(
    session: AsyncSession,
    change: Live,
    *,
    portal: str,
    copy: StoredCopy | None,
    context: ApplyContext,
) -> AppliedImage:
    item = change.item
    if not isinstance(item, ImageItem):
        raise TypeError(f"image change {change.id} carries a transcript")
    image_id = field_image_id(portal, item.id)
    existing = await session.get(FieldImage, image_id)
    if existing is not None and existing.revision == change.revision and copy is None:
        existing.seenAt = context.now
        existing.hiddenAt = None
        return AppliedImage(changed=False)
    stored = copy or (_kept_copy(existing) if existing is not None else None)
    if stored is None:
        raise ValueError(f"image {item.id} has no stored copy to point at")
    plan = photo_plan(item, portal=portal)
    media_id = await _upsert_media_ref(session, image_id, plan, portal=portal, copy=stored, context=context)
    crafts = await resolve_crafts(session, portal, item.crafts)
    values = _image_values(item, plan, stored) | {
        "revision": change.revision,
        "portalUpdatedAt": change.updated_at,
        "seenAt": context.now,
        "mediaRefId": media_id,
        "unresolvedCrafts": list(crafts.unresolved),
        "hiddenAt": None,
    }
    keys = {"id": image_id, "portal": portal, "portalMediaId": item.id}
    statement = insert(FieldImage).values(**keys, **values)
    await session.execute(statement.on_conflict_do_update(index_elements=[FieldImage.id], set_=values))
    await _relink(session, image_id, crafts.craft_ids)
    await link_photo_claims(session, media_id, described=_described(item, plan), craft_ids=crafts.craft_ids)
    old_key = existing.objectKey if existing is not None else None
    if old_key is not None and old_key != stored.key and await _orphaned(session, old_key, keep=image_id):
        return AppliedImage(changed=True, orphaned_key=old_key)
    return AppliedImage(changed=True)


def _described(item: ImageItem, plan: PhotoPlan) -> str:
    return photo_described(item.caption, [(group.kind, group.label) for group in plan.groups])


async def _relink(session: AsyncSession, image_id: uuid.UUID, craft_ids: tuple[uuid.UUID, ...]) -> None:
    await session.execute(delete(FieldImageCraft).where(FieldImageCraft.imageId == image_id))
    if craft_ids:
        rows = [{"imageId": image_id, "craftId": craft_id} for craft_id in craft_ids]
        await session.execute(insert(FieldImageCraft), rows)


async def withdraw_image(session: AsyncSession, portal: str, media_id: str) -> str | None:
    row = await session.get(FieldImage, field_image_id(portal, media_id))
    if row is None:
        return None
    key, media_ref = row.objectKey, row.mediaRefId
    await session.execute(delete(FieldImage).where(FieldImage.id == row.id))
    if media_ref is not None:
        await session.execute(delete(MediaRef).where(MediaRef.id == media_ref))
    return key if await _orphaned(session, key, keep=None) else None


async def delete_orphaned_copy(store: ObjectStore | None, key: str | None) -> None:
    if store is not None and key is not None:
        await store.delete(key)


async def _orphaned(session: AsyncSession, key: str, *, keep: uuid.UUID | None) -> bool:
    others = select(func.count()).select_from(FieldImage).where(FieldImage.objectKey == key)
    if keep is not None:
        others = others.where(FieldImage.id != keep)
    return int(await session.scalar(others) or 0) == 0


def _kept_copy(row: FieldImage) -> StoredCopy:
    return StoredCopy(
        key=row.objectKey,
        mime_type=row.mimeType,
        width=row.width,
        height=row.height,
        bytes=row.bytes,
        sha256=row.sha256,
        portal_sha256=row.portalSha256,
    )


def _image_values(item: ImageItem, plan: PhotoPlan, copy: StoredCopy) -> dict[str, Any]:
    return {
        "takenAt": item.taken_at,
        "caption": item.caption,
        "artisanLinked": item.artisan_linked,
        "belongsTo": [placement.model_dump(mode="json", by_alias=True) for placement in item.belongs_to],
        "context": {
            "workshop": item.workshop.model_dump(mode="json") if item.workshop else None,
            "workshopLine": plan.workshop_line,
            "credit": plan.credit,
            "groups": [{"kind": g.kind, "key": g.key, "label": g.label} for g in plan.groups],
            "crafts": [craft.model_dump(mode="json") for craft in item.crafts],
            "title": plan.title,
            "alt": plan.alt,
        },
        "people": [person.model_dump(mode="json") for person in item.people],
        "credits": [{"personId": c.person_id, "as": c.role} for c in item.credits],
        "statement": item.permission.statement,
        "rightsHolder": item.permission.rights_holder,
        "licence": item.permission.licence,
        "portalSha256": copy.portal_sha256,
        "objectKey": copy.key,
        "mimeType": copy.mime_type,
        "width": copy.width,
        "height": copy.height,
        "bytes": copy.bytes,
        "sha256": copy.sha256,
    }


async def _upsert_media_ref(
    session: AsyncSession,
    image_id: uuid.UUID,
    plan: PhotoPlan,
    *,
    portal: str,
    copy: StoredCopy,
    context: ApplyContext,
) -> uuid.UUID:
    if not (context.api_base or "").startswith("https://"):
        raise ValueError("PUBLIC_API_URL must be the https API address to link field images")
    url = image_route_url(context.api_base or "", image_id)
    provider = PORTAL_PROVIDERS[portal]
    url_key = media_url_key(provider, url, url)
    values = {
        "display": INLINE_DISPLAY,
        "provider": provider,
        "pageUrl": url,
        "imageUrl": url,
        "width": copy.width,
        "height": copy.height,
        "title": plan.title,
        "alt": plan.alt,
        "author": (", ".join(plan.credited) or PORTAL_PUBLISHERS[portal])[:300],
        "site": PORTAL_PUBLISHERS[portal],
        "credit": plan.credit,
        "licence": None,
        "licenceUrl": None,
        "objectKey": copy.key,
        "retrievedAt": context.now,
    }
    media_id = media_ref_id(url_key)
    statement = insert(MediaRef).values(id=media_id, urlKey=url_key, **values)
    await session.execute(statement.on_conflict_do_update(index_elements=[MediaRef.urlKey], set_=values))
    return media_id
