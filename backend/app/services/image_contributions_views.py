from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Craft, ImageContribution, MediaAsset
from app.research.image_contributions import ImageContributionView, shown_label
from app.research.image_screens import ScreenSummary

from .image_screens import screen_summaries
from .naming import content_disposition
from .object_store import ObjectStore

__all__ = ["LINK_SECONDS", "views"]

LINK_SECONDS = 600


@dataclass(frozen=True)
class _Shown:
    crafts: Mapping[uuid.UUID, Craft]
    assets: Mapping[uuid.UUID, MediaAsset]
    screens: Mapping[uuid.UUID, ScreenSummary]
    objects: ObjectStore | None
    now: datetime


async def views(
    session: AsyncSession, rows: Sequence[ImageContribution], *, objects: ObjectStore | None, now: datetime
) -> list[ImageContributionView]:
    shown = _Shown(
        crafts=await _by_id(session, Craft, {row.craftId for row in rows}),
        assets=await _by_id(session, MediaAsset, {row.assetId for row in rows if row.assetId is not None}),
        screens=await screen_summaries(session, [row.id for row in rows]),
        objects=objects,
        now=now,
    )
    return [_view(row, shown) for row in rows]


async def _by_id(session: AsyncSession, model: Any, ids: set[uuid.UUID | None]) -> dict[uuid.UUID, Any]:
    wanted = [found for found in ids if found is not None]
    if not wanted:
        return {}
    return {row.id: row for row in await session.scalars(select(model).where(model.id.in_(wanted)))}


def _view(row: ImageContribution, shown: _Shown) -> ImageContributionView:
    craft = shown.crafts[row.craftId]
    asset = shown.assets.get(row.assetId) if row.assetId is not None else None
    return ImageContributionView(
        id=row.id,
        craft_slug=craft.slug,
        craft_name=craft.name,
        stage_id=row.stageId,
        material_id=row.materialId,
        slot=row.slot,
        task_key=row.taskKey,
        claim_ids=row.claimIds,
        origin=row.origin,
        label=shown_label(row.origin, row.generator),
        generator=row.generator,
        prompt=row.prompt,
        caption=row.caption,
        alt_text=row.altText,
        status=row.status,
        ai_marked=row.aiMarked,
        mime=asset.mime if asset else None,
        width=asset.width if asset else None,
        height=asset.height if asset else None,
        file_url=_link(asset, shown),
        screen=shown.screens.get(row.id),
        created_at=row.createdAt,
        reviewed_at=row.reviewedAt,
        review_note=row.reviewNote,
    )


def _link(asset: MediaAsset | None, shown: _Shown) -> str | None:
    if asset is None or shown.objects is None:
        return None
    leaf = asset.s3Key.rsplit("/", 1)[-1]
    return shown.objects.presigned_get(
        asset.s3Key, disposition=content_disposition(leaf, inline=True), seconds=LINK_SECONDS, now=shown.now
    ).url
