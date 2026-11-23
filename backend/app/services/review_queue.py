from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Awaitable, Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ArtisanContribution, Craft, ImageContribution, User
from app.research.crafts import CraftRef
from app.research.review_queue import (
    COMPONENTS,
    FACTS,
    IMAGES,
    KIND_ORIGINS,
    LAYERS,
    LAYOUTS,
    READINGS,
    STAGES,
    STRUCTURE,
    TESTIMONY,
    TESTIMONY_ORIGIN,
    PictureItem,
    Proposer,
    QueueEntry,
    QueueKey,
    ReviewFilters,
    ReviewQueuePage,
    TestimonyItem,
    newest_first,
    parsed_cursor,
    reviewed_kinds,
    sees_proposer,
    selected_kinds,
)

from . import image_contributions as images, knowledge_view
from .object_store import ObjectStore
from .review_queue_components import component_items
from .review_queue_errors import UnknownCraft
from .review_queue_fact_views import fact_items
from .review_queue_layers import layer_items
from .review_queue_layouts import layout_items
from .review_queue_readings import ReadingScope, reading_count, reading_entries, reading_items
from .review_queue_select import QueueScope, Rendered, RenderedItem, queue_count, queue_entries, rows_by_id
from .review_queue_stages import stage_items
from .review_queue_structure import structure_items
from .testimony_views import Turns, review_item

__all__ = ["QueueAdapters", "TurnsOf", "list_review_queue"]

PICTURE_ORIGIN = KIND_ORIGINS[IMAGES][0]

TurnsOf = Callable[[ArtisanContribution], Awaitable[Turns]]


@dataclass(frozen=True)
class QueueAdapters:
    objects: ObjectStore | None
    turns_of: TurnsOf


async def list_review_queue(
    session: AsyncSession, viewer: User, filters: ReviewFilters, *, adapters: QueueAdapters, now: datetime
) -> ReviewQueuePage:
    kinds = reviewed_kinds(viewer)
    scope = QueueScope(
        viewer_id=viewer.id, craft=await _craft(session, filters.craft_slug), origin=filters.origin
    )
    counted = selected_kinds(kinds, kind=None, origin=filters.origin)
    counts = {kind: await _count(session, kind, scope) if kind in counted else 0 for kind in kinds}
    chosen = selected_kinds(kinds, kind=filters.kind, origin=filters.origin)
    before = parsed_cursor(filters.cursor) if filters.cursor is not None else None
    groups = [await _entries(session, kind, scope, before=before, limit=filters.limit + 1) for kind in chosen]
    kept, following = newest_first(groups, filters.limit)
    return ReviewQueuePage(
        kinds=list(kinds),
        counts=counts,
        total=sum(counts[kind] for kind in chosen),
        items=await _items(session, viewer, kept, adapters=adapters, now=now),
        next_cursor=following,
    )


async def _count(session: AsyncSession, kind: str, scope: QueueScope) -> int:
    if kind == READINGS:
        return await reading_count(session, _reading_scope(scope))
    return await queue_count(session, kind, scope)


async def _entries(
    session: AsyncSession, kind: str, scope: QueueScope, *, before: QueueKey | None, limit: int
) -> list[QueueEntry]:
    if kind == READINGS:
        return await reading_entries(session, _reading_scope(scope), before=before, limit=limit)
    return await queue_entries(session, kind, scope, before=before, limit=limit)


def _reading_scope(scope: QueueScope) -> ReadingScope:
    craft_id = scope.craft.id if scope.craft is not None else None
    return ReadingScope(viewer_id=scope.viewer_id, craft_id=craft_id, origin=scope.origin)


async def _craft(session: AsyncSession, slug: str | None) -> Craft | None:
    if slug is None:
        return None
    craft = await knowledge_view.resolve_craft(session, slug)
    if craft is None:
        raise UnknownCraft(f"No craft has the slug {slug!r}.")
    return craft


async def _items(
    session: AsyncSession,
    viewer: User,
    entries: Sequence[QueueEntry],
    *,
    adapters: QueueAdapters,
    now: datetime,
) -> list[RenderedItem]:
    wanted: dict[str, list[uuid.UUID]] = defaultdict(list)
    for entry in entries:
        wanted[entry.kind].append(entry.key.item_id)
    rendered: dict[uuid.UUID, Rendered] = {}
    for kind, ids in wanted.items():
        for each in await _rendered(session, kind, ids, adapters=adapters, now=now):
            rendered[each.item.id] = each
    names = await _proposers(session, rendered.values()) if sees_proposer(viewer) else {}
    return [_named(rendered[entry.key.item_id], names) for entry in entries if entry.key.item_id in rendered]


async def _rendered(
    session: AsyncSession, kind: str, ids: Sequence[uuid.UUID], *, adapters: QueueAdapters, now: datetime
) -> list[Rendered]:
    if kind == FACTS:
        return await fact_items(session, ids)
    if kind == COMPONENTS:
        return await component_items(session, ids)
    if kind == LAYOUTS:
        return await layout_items(session, ids)
    if kind == STRUCTURE:
        return await structure_items(session, ids)
    if kind == READINGS:
        return await reading_items(session, ids)
    if kind == LAYERS:
        return await layer_items(session, ids)
    if kind == STAGES:
        return await stage_items(session, ids)
    if kind == TESTIMONY:
        return await _testimony_items(session, ids, adapters=adapters, now=now)
    return await _picture_items(session, ids, adapters=adapters, now=now)


async def _testimony_items(
    session: AsyncSession, ids: Sequence[uuid.UUID], *, adapters: QueueAdapters, now: datetime
) -> list[Rendered]:
    rows = await session.scalars(select(ArtisanContribution).where(ArtisanContribution.id.in_(list(ids))))
    rendered = []
    for row in rows.all():
        turns = await adapters.turns_of(row)
        payload = await review_item(session, row, turns=turns, links=adapters.objects, now=now)
        item = TestimonyItem(
            id=row.id,
            origin=TESTIMONY_ORIGIN,
            submitted_at=row.createdAt,
            craft=CraftRef.model_validate(payload["craft"]),
            testimony=payload,
        )
        rendered.append(Rendered(item, row.userId))
    return rendered


async def _picture_items(
    session: AsyncSession, ids: Sequence[uuid.UUID], *, adapters: QueueAdapters, now: datetime
) -> list[Rendered]:
    rows = list(await session.scalars(select(ImageContribution).where(ImageContribution.id.in_(list(ids)))))
    views = await images.views(session, rows, objects=adapters.objects, now=now)
    crafts = await rows_by_id(session, Craft, [row.craftId for row in rows])
    return [
        Rendered(
            PictureItem(
                id=row.id,
                origin=PICTURE_ORIGIN,
                submitted_at=row.createdAt,
                craft=CraftRef.model_validate(knowledge_view.craft_ref(crafts[row.craftId])),
                picture=view,
            ),
            row.contributorId,
        )
        for row, view in zip(rows, views, strict=True)
    ]


async def _proposers(session: AsyncSession, rendered: Iterable[Rendered]) -> dict[uuid.UUID, Proposer]:
    ids = list({each.proposer_id for each in rendered if each.proposer_id is not None})
    if not ids:
        return {}
    rows = await session.execute(select(User.id, User.name, User.role).where(User.id.in_(ids)))
    return {
        user_id: Proposer(name=name, role=str(getattr(role, "value", role)))
        for user_id, name, role in rows.all()
    }


def _named(each: Rendered, names: dict[uuid.UUID, Proposer]) -> RenderedItem:
    proposer = names.get(each.proposer_id) if each.proposer_id is not None else None
    return each.item if proposer is None else each.item.model_copy(update={"proposer": proposer})
