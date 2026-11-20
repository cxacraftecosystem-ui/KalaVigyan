from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput
from app.models import ImageFingerprint, MediaAsset
from app.research.image_intake_pixels import pixels_of
from app.research.image_intake_types import KEPT_TYPES
from app.research.image_screens import signed_fingerprint

from .object_store import ObjectStore

__all__ = ["BACKFILL_BATCH", "FingerprintReport", "fingerprint_stored"]

BACKFILL_BATCH = 100


@dataclass
class FingerprintReport:
    fingerprinted: int = 0
    missing: list[str] = field(default_factory=list)
    unreadable: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": not self.unreadable,
            "fingerprinted": self.fingerprinted,
            "missing": self.missing,
            "unreadable": self.unreadable,
        }


async def fingerprint_stored(session: AsyncSession, objects: ObjectStore) -> FingerprintReport:
    report = FingerprintReport()
    after: uuid.UUID | None = None
    while True:
        batch = await _unfingerprinted(session, after)
        if not batch:
            return report
        for asset_id, key in batch:
            await _fingerprint(session, objects, (asset_id, key), report)
        await session.flush()
        after = batch[-1][0]


async def _unfingerprinted(session: AsyncSession, after: uuid.UUID | None) -> list[tuple[uuid.UUID, str]]:
    query = (
        select(MediaAsset.id, MediaAsset.s3Key)
        .outerjoin(ImageFingerprint, ImageFingerprint.assetId == MediaAsset.id)
        .where(ImageFingerprint.assetId.is_(None), MediaAsset.mime.in_(KEPT_TYPES))
        .order_by(MediaAsset.id)
        .limit(BACKFILL_BATCH)
    )
    if after is not None:
        query = query.where(MediaAsset.id > after)
    return [(asset_id, str(key)) for asset_id, key in (await session.execute(query)).all()]


async def _fingerprint(
    session: AsyncSession, objects: ObjectStore, asset: tuple[uuid.UUID, str], report: FingerprintReport
) -> None:
    asset_id, key = asset
    data = await objects.get(key)
    if data is None:
        report.missing.append(str(asset_id))
        return
    try:
        pixels = await asyncio.to_thread(pixels_of, data)
    except InvalidInput:
        report.unreadable.append(str(asset_id))
        return
    session.add(ImageFingerprint(assetId=asset_id, fingerprint=signed_fingerprint(pixels.fingerprint)))
    report.fingerprinted += 1
