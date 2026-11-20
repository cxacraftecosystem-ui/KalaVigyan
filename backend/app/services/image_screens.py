from __future__ import annotations

import asyncio
import hashlib
import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import BigInteger, cast, func, literal, select
from sqlalchemy.dialects.postgresql import BIT
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import release_connection
from app.core.errors import InvalidInput
from app.core.roles import role_value
from app.models import ImageContribution, ImageFingerprint, ImageScreen, MediaAsset, User
from app.research.image_contributions import AI_GENERATED
from app.research.image_intake import InspectedImage, inspected_image
from app.research.image_intake_pixels import PREVIEW_MIME, Pixels, pixels_of
from app.research.image_screens import (
    NEAR_BITS,
    NEAR_IDENTICAL_BITS,
    Near,
    ScreenSummary,
    VisionRequest,
    VisionScreen,
    VisionVerdict,
    screen_flags,
    screen_reasons,
    signed_fingerprint,
    unscreened,
    verdict_of,
)

from .image_contributions_errors import ContributionRefused

__all__ = [
    "DECODES_AT_ONCE",
    "ScreenTools",
    "Screened",
    "nearest_stored",
    "recorded_screen",
    "screen_summaries",
    "screened",
]

DECODES_AT_ONCE = 2
LIVE = ("AWAITING_FILE", "PENDING", "APPROVED")
REPEAT = "This picture has been contributed already"
HELD_ALREADY = "This picture is one KalaVigyan already holds"
AI_MARKED = "This file's own metadata says an AI made it. Declare it as AI-generated."
NO_VISION = "No vision route is set up, so the picture was not looked at automatically."
VECTOR = "An SVG drawing is not looked at automatically."
BIT_WIDTH = 64

_decodes = asyncio.Semaphore(DECODES_AT_ONCE)


@dataclass(frozen=True)
class ScreenTools:
    vision: VisionScreen | None


@dataclass(frozen=True)
class Screened:
    image: InspectedImage
    received_bytes: int
    digest: str
    fingerprint: int | None
    near: Near | None
    vision: VisionVerdict
    flags: tuple[str, ...]

    @property
    def clear(self) -> bool:
        return not self.flags

    def summary(self) -> ScreenSummary:
        return ScreenSummary(
            verdict=verdict_of(self.flags),
            flags=list(self.flags),
            reasons=screen_reasons(self.flags, self.vision.note),
        )


async def screened(
    session: AsyncSession, data: bytes, *, origin: str, user: User, tools: ScreenTools
) -> Screened:
    image, pixels = await _decoded(data)
    if image.ai_marked and origin != AI_GENERATED:
        raise InvalidInput(AI_MARKED)
    digest = hashlib.sha256(image.data).hexdigest()
    await _refuse_repeat(session, digest)
    near = None if pixels is None else await nearest_stored(session, pixels.fingerprint)
    if near is not None and near.live and near.distance <= NEAR_IDENTICAL_BITS:
        raise ContributionRefused(REPEAT if near.contributed else HELD_ALREADY)
    await release_connection(session)
    vision = await _vision(tools, pixels, ai_made=origin == AI_GENERATED, user=user)
    fingerprint = pixels.fingerprint if pixels is not None else None
    return Screened(image, len(data), digest, fingerprint, near, vision, screen_flags(vision, near))


async def nearest_stored(session: AsyncSession, fingerprint: int) -> Near | None:
    probe = cast(literal(signed_fingerprint(fingerprint)), BigInteger)
    distance = func.bit_count(cast(ImageFingerprint.fingerprint.op("#")(probe), BIT(BIT_WIDTH)))
    found = (
        await session.execute(
            select(ImageFingerprint.assetId, distance, ImageContribution.status)
            .outerjoin(ImageContribution, ImageContribution.assetId == ImageFingerprint.assetId)
            .where(distance <= NEAR_BITS)
            .order_by(distance, ImageFingerprint.assetId)
            .limit(1)
        )
    ).first()
    if found is None:
        return None
    asset_id, bits, status = found
    return Near(
        asset_id=asset_id,
        distance=int(bits),
        live=status is None or status in LIVE,
        contributed=status is not None,
    )


def recorded_screen(
    session: AsyncSession, contribution: ImageContribution, asset: MediaAsset, screen: Screened
) -> ImageScreen:
    signed = None if screen.fingerprint is None else signed_fingerprint(screen.fingerprint)
    if signed is not None:
        session.add(ImageFingerprint(assetId=asset.id, fingerprint=signed))
    summary, near, vision = screen.summary(), screen.near, screen.vision
    row = ImageScreen(
        contributionId=contribution.id,
        receivedMime=screen.image.received,
        receivedBytes=screen.received_bytes,
        fingerprint=signed,
        nearestAssetId=near.asset_id if near else None,
        nearestDistance=near.distance if near else None,
        verdict=summary.verdict,
        flags=summary.flags,
        reasons=summary.reasons,
        provider=vision.provider,
        model=vision.model,
        usageEventId=vision.usage_event_id,
        inputTokens=vision.input_tokens,
        outputTokens=vision.output_tokens,
        costUsd=vision.cost_usd,
    )
    session.add(row)
    return row


async def screen_summaries(
    session: AsyncSession, contribution_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, ScreenSummary]:
    if not contribution_ids:
        return {}
    rows = await session.scalars(select(ImageScreen).where(ImageScreen.contributionId.in_(contribution_ids)))
    return {
        row.contributionId: ScreenSummary(
            verdict=row.verdict, flags=list(row.flags), reasons=list(row.reasons)
        )
        for row in rows
    }


async def _decoded(data: bytes) -> tuple[InspectedImage, Pixels | None]:
    async with _decodes:
        return await asyncio.to_thread(_decode, data)


def _decode(data: bytes) -> tuple[InspectedImage, Pixels | None]:
    image = inspected_image(data)
    return image, None if image.vector else pixels_of(image.data)


async def _refuse_repeat(session: AsyncSession, digest: str) -> None:
    found = await session.scalar(
        select(ImageContribution.id).where(
            ImageContribution.sha256 == digest, ImageContribution.status.in_(LIVE)
        )
    )
    if found is not None:
        raise ContributionRefused(REPEAT)


async def _vision(tools: ScreenTools, pixels: Pixels | None, *, ai_made: bool, user: User) -> VisionVerdict:
    if pixels is None:
        return unscreened(VECTOR)
    if tools.vision is None:
        return unscreened(NO_VISION)
    request = VisionRequest(
        preview=pixels.preview, mime=PREVIEW_MIME, ai_made=ai_made, user_id=user.id, role=role_value(user)
    )
    return await tools.vision(request)
