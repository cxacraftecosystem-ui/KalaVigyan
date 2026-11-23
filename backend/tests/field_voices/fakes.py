from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from app.core.errors import ExternalFailure
from app.services.field_voices_feed import VIEW_GONE, FieldVoicesPage, Live, StreamState, stream_digest
from app.services.field_voices_images import StoredCopy
from app.services.field_voices_items import ImageItem
from app.services.field_voices_sync import AppliedPage, Stamp, StreamCursors, SyncClock


@dataclass
class FakeStream:
    cursor: str | None = None
    gone_cursor: str | None = None
    last: Stamp | None = None
    gone_last: Stamp | None = None
    rereading: bool = False
    contacted: int = 0
    hidden: bool = False
    items: dict[str, str] = field(default_factory=dict)
    seen: set[str] = field(default_factory=set)
    withdrawn: list[str] = field(default_factory=list)


class FakeLedger:
    def __init__(self) -> None:
        self.streams: dict[tuple[str, str], FakeStream] = {}
        self.copies: dict[str, str] = {}
        self.relinked: list[str] = []

    def stream(self, portal: str, stream: str) -> FakeStream:
        return self.streams.setdefault((portal, stream), FakeStream())

    async def cursors(self, portal: str, stream: str) -> StreamCursors:
        row = self.stream(portal, stream)
        return StreamCursors(
            cursor=row.cursor,
            gone_cursor=row.gone_cursor,
            rereading=row.rereading,
            last=row.last,
            gone_last=row.gone_last,
        )

    async def apply_page(self, page: FieldVoicesPage, copies: Mapping[str, StoredCopy]) -> AppliedPage:
        row = self.stream(page.portal, page.stream)
        live = gone = 0
        for change in page.changes:
            if isinstance(change, Live):
                row.seen.add(change.id)
                if row.items.get(change.id) != change.revision:
                    row.items[change.id] = change.revision
                    live += 1
                if change.id in copies:
                    self.copies[change.id] = copies[change.id].sha256
            else:
                row.items.pop(change.id, None)
                row.withdrawn.append(change.id)
                gone += 1
        self._advance(row, page)
        return AppliedPage(live=live, gone=gone, images=len(copies))

    def _advance(self, row: FakeStream, page: FieldVoicesPage) -> None:
        if page.next_cursor is None:
            return
        final = page.changes[-1] if page.changes and page.next_cursor != page.cursor else None
        stamp = (final.updated_at, final.id) if final is not None else None
        if page.view == VIEW_GONE:
            row.gone_cursor, row.gone_last = page.next_cursor, stamp or row.gone_last
        else:
            row.cursor, row.last = page.next_cursor, stamp or row.last

    async def needs_copy(self, portal: str, change: Live) -> bool:
        item = change.item
        return isinstance(item, ImageItem) and self.copies.get(change.id) != item.image.sha256

    async def contact(self, portal: str, stream: str) -> None:
        self.stream(portal, stream).contacted += 1

    async def matches(self, portal: str, stream: str, state: StreamState) -> bool:
        items = self.stream(portal, stream).items
        return (len(items), stream_digest(items.items())) == (state.live, state.digest)

    async def restart(self, portal: str, stream: str) -> None:
        row = self.stream(portal, stream)
        row.cursor, row.last, row.rereading, row.seen = None, None, True, set()

    async def finish_reread(self, portal: str, stream: str) -> int:
        row = self.stream(portal, stream)
        unseen = [item for item in row.items if item not in row.seen]
        for item in unseen:
            row.items.pop(item)
            row.withdrawn.append(item)
        row.rereading = False
        return len(unseen)

    async def hide(self, portal: str, stream: str) -> None:
        self.stream(portal, stream).hidden = True

    async def relink(self, portal: str) -> None:
        self.relinked.append(portal)


class FakeCopier:
    def __init__(self, *, expired_first: int = 0) -> None:
        self.copied: list[str] = []
        self._expired = expired_first

    async def copy(self, item: ImageItem) -> StoredCopy:
        if self._expired:
            self._expired -= 1
            raise ExternalFailure("link expired", status=403, service="images")
        self.copied.append(item.id)
        return StoredCopy(
            key=f"media/field-voices/{item.image.sha256}/copy.jpg",
            mime_type="image/jpeg",
            width=item.image.width,
            height=item.image.height,
            bytes=1,
            sha256=item.image.sha256,
            portal_sha256=item.image.sha256,
        )


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.pauses: list[float] = []

    def monotonic(self) -> float:
        return self.now

    async def pause(self, seconds: float) -> None:
        self.pauses.append(seconds)

    def clock(self) -> SyncClock:
        return SyncClock(monotonic=self.monotonic, pause=self.pause)
