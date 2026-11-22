from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import BigInteger, and_, cast, func, literal, or_, select
from sqlalchemy.dialects.postgresql import BIT, insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, InvalidInput
from app.core.roles import role_value
from app.models import FieldImage, FieldPhotoScreen, User
from app.research.field_photo_reviews import photo_flags
from app.research.image_intake_pixels import PREVIEW_MIME, Pixels, pixels_of
from app.research.image_screens import (
    FLAGGED,
    NEAR_BITS,
    UNSCREENED,
    ScreenTools,
    VisionRequest,
    VisionVerdict,
    screen_reasons,
    signed_fingerprint,
    unscreened,
    verdict_of,
)
from app.retrieval.field_scope import held_images

from .field_photo_crops import OpenSession, PhotoObjects
from .image_screens import nearest_stored

__all__ = ["SCREENS_PER_CALL", "SCREENS_PER_RUN", "PhotoNear", "ScreenReport", "screen_held_photos"]

SCREENS_PER_RUN = 200
SCREENS_PER_CALL = 10
BIT_WIDTH = 64
NO_VISION = "No vision route is set up, so the photograph was not looked at automatically."
UNREADABLE = "The stored copy could not be read, so the photograph was not looked at automatically."


@dataclass(frozen=True)
class PhotoNear:
    distance: int
    asset_id: uuid.UUID | None = None
    image_id: uuid.UUID | None = None


@dataclass(frozen=True)
class _Target:
    image_id: uuid.UUID
    key: str
    sha256: str


@dataclass
class ScreenReport:
    screened: int = 0
    flagged: int = 0
    unscreened: int = 0
    missing: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": not self.missing,
            "screened": self.screened,
            "flagged": self.flagged,
            "unscreened": self.unscreened,
            "missing": self.missing,
        }


async def screen_held_photos(
    open_session: OpenSession,
    objects: PhotoObjects,
    tools: ScreenTools,
    *,
    limit: int,
    actor: User | None = None,
) -> ScreenReport:
    async with open_session() as session:
        targets = await _waiting(session, limit)
    report = ScreenReport()
    for target in targets:
        data = await _copy(objects, target.key)
        if data is None:
            report.missing.append(str(target.image_id))
            continue
        verdict = await _screened(open_session, target, data, (tools, actor))
        report.screened += 1
        report.flagged += int(verdict == FLAGGED)
        report.unscreened += int(verdict == UNSCREENED)
    return report


async def _waiting(session: AsyncSession, limit: int) -> list[_Target]:
    current = and_(
        FieldPhotoScreen.imageId == FieldImage.id, FieldPhotoScreen.imageSha256 == FieldImage.sha256
    )
    rows = await session.execute(
        select(FieldImage.id, FieldImage.objectKey, FieldImage.sha256)
        .outerjoin(FieldPhotoScreen, current)
        .where(
            *held_images(), or_(FieldPhotoScreen.imageId.is_(None), FieldPhotoScreen.verdict == UNSCREENED)
        )
        .order_by(FieldPhotoScreen.screenedAt.asc().nulls_first(), FieldImage.createdAt, FieldImage.id)
        .limit(limit)
    )
    return [_Target(image_id=row.id, key=row.objectKey, sha256=row.sha256) for row in rows]


async def _copy(objects: PhotoObjects, key: str) -> bytes | None:
    try:
        return await objects.get(key)
    except AppError:
        return None


async def _screened(
    open_session: OpenSession, target: _Target, data: bytes, using: tuple[ScreenTools, User | None]
) -> str:
    tools, actor = using
    try:
        pixels: Pixels | None = await asyncio.to_thread(pixels_of, data)
    except InvalidInput:
        pixels = None
    near = None
    if pixels is not None:
        async with open_session() as session:
            near = await nearest_photo(session, pixels.fingerprint, exclude=target.image_id)
    vision = await _vision(tools, pixels, actor)
    flags = photo_flags(vision.flags, near.distance if near else None)
    async with open_session() as session:
        await _record(session, target, (pixels, near, vision, flags))
        await session.commit()
    return verdict_of(flags)


async def nearest_photo(session: AsyncSession, fingerprint: int, *, exclude: uuid.UUID) -> PhotoNear | None:
    probe = cast(literal(signed_fingerprint(fingerprint)), BigInteger)
    distance = func.bit_count(cast(FieldPhotoScreen.fingerprint.op("#")(probe), BIT(BIT_WIDTH)))
    found = (
        await session.execute(
            select(FieldPhotoScreen.imageId, distance)
            .where(FieldPhotoScreen.imageId != exclude, distance <= NEAR_BITS)
            .order_by(distance, FieldPhotoScreen.imageId)
            .limit(1)
        )
    ).first()
    asset = await nearest_stored(session, fingerprint)
    held = PhotoNear(distance=int(found[1]), image_id=found[0]) if found else None
    stored = PhotoNear(distance=asset.distance, asset_id=asset.asset_id) if asset else None
    candidates = [near for near in (held, stored) if near is not None]
    return min(candidates, key=lambda near: near.distance) if candidates else None


async def _vision(tools: ScreenTools, pixels: Pixels | None, actor: User | None) -> VisionVerdict:
    if pixels is None:
        return unscreened(UNREADABLE)
    if tools.vision is None:
        return unscreened(NO_VISION)
    request = VisionRequest(
        preview=pixels.preview,
        mime=PREVIEW_MIME,
        ai_made=False,
        faces=True,
        user_id=actor.id if actor is not None else None,
        role=role_value(actor) if actor is not None else None,
    )
    return await tools.vision(request)


async def _record(session: AsyncSession, target: _Target, found: tuple[Any, ...]) -> None:
    pixels, near, vision, flags = found
    current = await session.scalar(
        select(FieldImage.sha256).where(FieldImage.id == target.image_id).with_for_update()
    )
    if current != target.sha256:
        return
    values = {
        "imageSha256": target.sha256,
        "fingerprint": signed_fingerprint(pixels.fingerprint) if pixels is not None else None,
        "nearestAssetId": near.asset_id if near else None,
        "nearestImageId": near.image_id if near else None,
        "nearestDistance": near.distance if near else None,
        "verdict": verdict_of(flags),
        "flags": list(flags),
        "reasons": screen_reasons(flags, vision.note),
        "provider": vision.provider,
        "model": vision.model,
        "usageEventId": vision.usage_event_id,
        "inputTokens": vision.input_tokens,
        "outputTokens": vision.output_tokens,
        "costUsd": vision.cost_usd,
        "screenedAt": func.now(),
    }
    statement = insert(FieldPhotoScreen).values(imageId=target.image_id, **values)
    await session.execute(
        statement.on_conflict_do_update(index_elements=[FieldPhotoScreen.imageId], set_=values)
    )
