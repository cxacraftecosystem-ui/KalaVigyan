from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MediaAsset, MediaJob

from .naming import page_media_key

__all__ = [
    "PAGE_MEDIA_COPIED_MAX",
    "AiMediaRecord",
    "PageCopyObjects",
    "copied_older_media",
    "page_copy_key",
    "page_media_key_of",
    "page_visibility",
    "shared_ai_media",
]

logger = logging.getLogger(__name__)

SHARED = "CRAFT_SHARED"
PRIVATE = "PRIVATE"
SUCCEEDED = "SUCCEEDED"
PAGE_MEDIA_COPIED_MAX = 200


class PageCopyObjects(Protocol):
    async def get(self, key: str) -> bytes | None: ...

    async def put(self, key: str, body: bytes, *, content_type: str) -> None: ...


@dataclass(frozen=True)
class AiMediaRecord:
    asset_id: uuid.UUID
    kind: str
    mime: str
    width: int | None
    height: int | None
    duration_seconds: float | None
    alt_text: str
    model: str
    made_at: datetime
    stage_id: uuid.UUID | None
    claim_ids: tuple[uuid.UUID, ...]


def page_copy_key(data: bytes, s3_key: str) -> str:
    return page_media_key(hashlib.sha256(data).hexdigest(), s3_key.rsplit("/", 1)[-1])


def page_visibility(*, depicts_named_cluster: bool) -> str:
    return PRIVATE if depicts_named_cluster else SHARED


async def shared_ai_media(session: AsyncSession, craft_id: uuid.UUID) -> tuple[AiMediaRecord, ...]:
    rows = await session.execute(
        select(MediaAsset, MediaJob)
        .join(MediaJob, MediaJob.id == MediaAsset.jobId)
        .where(
            MediaJob.craftId == craft_id,
            MediaJob.status == SUCCEEDED,
            MediaAsset.visibility == SHARED,
            MediaAsset.pageKey.is_not(None),
        )
        .order_by(MediaAsset.createdAt.desc(), MediaAsset.id)
    )
    return tuple(_record(asset, job) for asset, job in rows.tuples())


async def page_media_key_of(session: AsyncSession, asset_id: uuid.UUID) -> str | None:
    return await session.scalar(
        select(MediaAsset.pageKey).where(
            MediaAsset.id == asset_id, MediaAsset.visibility == SHARED, MediaAsset.pageKey.is_not(None)
        )
    )


async def copied_older_media(session: AsyncSession, objects: PageCopyObjects) -> int:
    rows = await session.scalars(
        select(MediaAsset)
        .join(MediaJob, MediaJob.id == MediaAsset.jobId)
        .where(MediaJob.status == SUCCEEDED, MediaAsset.pageKey.is_(None))
        .order_by(MediaAsset.createdAt, MediaAsset.id)
        .limit(PAGE_MEDIA_COPIED_MAX)
    )
    copied = 0
    for asset in rows.all():
        data = await objects.get(asset.s3Key)
        if data is None:
            logger.warning("AI asset %s has no stored file and gets no page copy", asset.id)
            continue
        key = page_copy_key(data, asset.s3Key)
        await objects.put(key, data, content_type=asset.mime)
        asset.pageKey = key
        asset.visibility = page_visibility(depicts_named_cluster=asset.depictsNamedCluster)
        copied += 1
    await session.commit()
    return copied


def _record(asset: MediaAsset, job: MediaJob) -> AiMediaRecord:
    return AiMediaRecord(
        asset_id=asset.id,
        kind=job.kind,
        mime=asset.mime,
        width=asset.width,
        height=asset.height,
        duration_seconds=None if asset.durationS is None else float(asset.durationS),
        alt_text=asset.altText or "",
        model=asset.model or job.model or "",
        made_at=asset.createdAt,
        stage_id=job.stageId,
        claim_ids=tuple(job.claimIds or ()),
    )
