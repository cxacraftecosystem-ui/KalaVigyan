from __future__ import annotations

import logging
import uuid
from collections.abc import Callable, Mapping
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models import FieldImage, FieldImageCraft, FieldRecording, FieldRecordingCraft, FieldSegment
from app.research.embedding import TextEmbedder
from app.retrieval.indexing import embed_written
from app.services.field_voices_feed import IMAGES, TRANSCRIPTS, VIEW_GONE, FieldVoicesPage, Live, StreamState
from app.services.field_voices_illustrations import relink_photo_claims
from app.services.field_voices_image_store import (
    apply_image,
    delete_orphaned_copy,
    image_needs_copy,
    withdraw_image,
)
from app.services.field_voices_images import StoredCopy
from app.services.field_voices_items import FeedCraft, FeedPerson
from app.services.field_voices_store import (
    ApplyContext,
    apply_transcript,
    hide_stored,
    resolve_crafts,
    stored_digest,
    stream_row,
    withdraw_recording,
)
from app.services.field_voices_sync import AppliedPage, Stamp, StreamCursors
from app.services.object_store import ObjectStore

__all__ = ["OpenSession", "SqlFieldVoicesLedger", "rekey_people", "rekeyed"]

logger = logging.getLogger(__name__)

OpenSession = Callable[[], AbstractAsyncContextManager[AsyncSession]]
MODELS: Mapping[str, Any] = {TRANSCRIPTS: FieldRecording, IMAGES: FieldImage}
LINKS: Mapping[str, tuple[Any, str]] = {
    TRANSCRIPTS: (FieldRecordingCraft, "recordingId"),
    IMAGES: (FieldImageCraft, "imageId"),
}


@dataclass
class _PageWork:
    context: ApplyContext
    live: int = 0
    gone: int = 0
    images: int = 0
    sources: list[uuid.UUID] = field(default_factory=list)
    orphans: list[str] = field(default_factory=list)

    def applied(self) -> AppliedPage:
        return AppliedPage(live=self.live, gone=self.gone, images=self.images)


class SqlFieldVoicesLedger:
    def __init__(
        self,
        open_session: OpenSession,
        *,
        embed: TextEmbedder,
        store: ObjectStore | None,
        context: ApplyContext,
    ) -> None:
        self._open = open_session
        self._embed = embed
        self._store = store
        self._context = context

    def _now(self) -> ApplyContext:
        return replace(self._context, now=datetime.now(UTC))

    async def cursors(self, portal: str, stream: str) -> StreamCursors:
        async with self._open() as session:
            row = await stream_row(session, portal, stream)
            await session.commit()
            return StreamCursors(
                cursor=row.cursor,
                gone_cursor=row.goneCursor,
                rereading=row.rereadFrom is not None,
                last=_change_stamp(row.lastAt, row.lastId),
                gone_last=_change_stamp(row.goneLastAt, row.goneLastId),
            )

    async def needs_copy(self, portal: str, change: Live) -> bool:
        async with self._open() as session:
            return await image_needs_copy(session, change, portal=portal)

    async def apply_page(self, page: FieldVoicesPage, copies: Mapping[str, StoredCopy]) -> AppliedPage:
        work = _PageWork(context=self._now())
        async with self._open() as session:
            for change in page.changes:
                if isinstance(change, Live):
                    await self._live(session, page, change, copies.get(change.id), work)
                    continue
                orphan = await self._withdraw_one(session, page.stream, page.portal, change.id)
                work.orphans += [orphan] if orphan else []
                work.gone += 1
            await self._advance(session, page)
            await session.commit()
        for key in work.orphans:
            await delete_orphaned_copy(self._store, key)
        await self._embed_sources(work.sources)
        return work.applied()

    async def contact(self, portal: str, stream: str) -> None:
        model = MODELS[stream]
        async with self._open() as session:
            row = await stream_row(session, portal, stream)
            row.lastContactAt = datetime.now(UTC)
            await session.execute(
                update(model).where(model.portal == portal, model.hiddenAt.is_not(None)).values(hiddenAt=None)
            )
            await session.commit()

    async def matches(self, portal: str, stream: str, state: StreamState) -> bool:
        async with self._open() as session:
            live, digest = await stored_digest(session, MODELS[stream], portal)
            row = await stream_row(session, portal, stream)
            row.live, row.digest = live, digest
            same = (live, digest) == (state.live, state.digest)
            if same:
                row.lastReconciledAt = datetime.now(UTC)
            row.lastCaughtUpAt = datetime.now(UTC)
            await session.commit()
            return same

    async def restart(self, portal: str, stream: str) -> None:
        await self._stamp(portal, stream, cursor=None, lastAt=None, lastId=None, rereadFrom=datetime.now(UTC))

    async def finish_reread(self, portal: str, stream: str) -> int:
        model = MODELS[stream]
        async with self._open() as session:
            row = await stream_row(session, portal, stream)
            since = row.rereadFrom
            stale = (
                list(
                    await session.scalars(
                        select(model.portalMediaId).where(model.portal == portal, model.seenAt < since)
                    )
                )
                if since
                else []
            )
            orphans = [await self._withdraw_one(session, stream, portal, media_id) for media_id in stale]
            row.rereadFrom = None
            await session.commit()
        for key in orphans:
            await delete_orphaned_copy(self._store, key)
        return len(stale)

    async def hide(self, portal: str, stream: str) -> None:
        async with self._open() as session:
            await hide_stored(session, MODELS[stream], portal, datetime.now(UTC))
            await session.commit()

    async def relink(self, portal: str) -> None:
        async with self._open() as session:
            for stream, model in MODELS.items():
                await _relink_unresolved(session, stream, model, portal)
            await session.commit()

    async def _live(
        self,
        session: AsyncSession,
        page: FieldVoicesPage,
        change: Live,
        copy: StoredCopy | None,
        work: _PageWork,
    ) -> None:
        portal = page.portal
        if page.stream == TRANSCRIPTS:
            source = await apply_transcript(session, change, portal=portal, context=work.context)
            work.sources += [source] if source else []
            work.live += 1 if source else 0
        else:
            applied = await apply_image(session, change, portal=portal, copy=copy, context=work.context)
            work.live += 1 if applied.changed else 0
            work.images += 1 if copy else 0
            work.orphans += [applied.orphaned_key] if applied.orphaned_key else []
        for person in change.item.people:
            if person.merged_ids:
                await rekey_people(session, MODELS[page.stream], portal, person)

    async def _withdraw_one(
        self, session: AsyncSession, stream: str, portal: str, media_id: str
    ) -> str | None:
        if stream == TRANSCRIPTS:
            await withdraw_recording(session, portal, media_id)
            return None
        return await withdraw_image(session, portal, media_id)

    async def _advance(self, session: AsyncSession, page: FieldVoicesPage) -> None:
        row = await stream_row(session, page.portal, page.stream)
        if page.next_cursor is None:
            return
        moved = page.next_cursor != page.cursor and bool(page.changes)
        last = page.changes[-1] if moved else None
        if page.view == VIEW_GONE:
            row.goneCursor = page.next_cursor
            if last is not None:
                row.goneLastAt, row.goneLastId = last.updated_at, last.id
        else:
            row.cursor = page.next_cursor
            if last is not None:
                row.lastAt, row.lastId = last.updated_at, last.id

    async def _stamp(self, portal: str, stream: str, **values: Any) -> None:
        async with self._open() as session:
            row = await stream_row(session, portal, stream)
            for key, value in values.items():
                setattr(row, key, value)
            await session.commit()

    async def _embed_sources(self, sources: list[uuid.UUID]) -> None:
        if not sources:
            return
        try:
            async with self._open() as session:
                await embed_written(session, self._embed, claim_ids=[], source_ids=sources)
        except AppError as error:
            logger.warning("field voices stored without vectors, left for embed_knowledge: %s", error)


async def rekey_people(session: AsyncSession, model: Any, portal: str, person: FeedPerson) -> None:
    for old in person.merged_ids:
        rows = await session.scalars(
            select(model).where(model.portal == portal, model.people.contains([{"id": old}]))
        )
        for row in rows:
            row.people = rekeyed(row.people, "id", old, person.id)
            if model is FieldRecording:
                row.speakers = rekeyed(row.speakers, "personId", old, person.id)
            else:
                row.credits = rekeyed(row.credits, "personId", old, person.id)
    if model is FieldRecording and person.merged_ids:
        await session.execute(
            update(FieldSegment)
            .where(
                FieldSegment.personId.in_(list(person.merged_ids)),
                FieldSegment.recordingId.in_(
                    select(FieldRecording.id).where(FieldRecording.portal == portal)
                ),
            )
            .values(personId=person.id)
        )


def _change_stamp(at: datetime | None, change_id: str | None) -> Stamp | None:
    return None if at is None or change_id is None else (at, change_id)


def rekeyed(entries: list[Any], key: str, old: str, new: str) -> list[Any]:
    return [{**each, key: new} if each.get(key) == old else each for each in entries]


async def _relink_unresolved(session: AsyncSession, stream: str, model: Any, portal: str) -> None:
    link, key = LINKS[stream]
    rows = await session.scalars(select(model).where(model.portal == portal, model.unresolvedCrafts != []))
    for row in rows:
        crafts = await resolve_crafts(session, portal, _feed_crafts(row.unresolvedCrafts))
        if crafts.craft_ids:
            values = [{key: row.id, "craftId": craft_id} for craft_id in crafts.craft_ids]
            await session.execute(insert(link).values(values).on_conflict_do_nothing())
            if model is FieldImage:
                await relink_photo_claims(session, row)
        row.unresolvedCrafts = list(crafts.unresolved)


def _feed_crafts(stored: list[Any]) -> list[FeedCraft]:
    return [
        FeedCraft(id=each["id"], slug=each["slug"], name=each.get("name") or each["slug"]) for each in stored
    ]
