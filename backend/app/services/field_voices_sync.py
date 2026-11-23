from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any, Protocol

from app.core.errors import AppError, ExternalFailure, InvalidInput, Refused
from app.services.field_voices_feed import (
    IMAGES,
    STREAMS,
    VIEW_ALL,
    VIEW_GONE,
    FieldVoicesPage,
    FieldVoicesState,
    Live,
    StreamState,
)
from app.services.field_voices_images import StoredCopy
from app.services.field_voices_items import ImageItem
from app.services.field_voices_screen import PortalScreen

__all__ = [
    "CALL_SPACING_SECONDS",
    "PAGE_REREADS",
    "RETRY_WAIT_MAX_SECONDS",
    "STREAM_BUDGET_SECONDS",
    "AppliedPage",
    "FieldVoicesLedger",
    "ImageCopy",
    "PortalReader",
    "PortalReport",
    "Stamp",
    "StreamCursors",
    "StreamReport",
    "SyncClock",
    "sync_portal",
]

logger = logging.getLogger(__name__)

STREAM_BUDGET_SECONDS = 20 * 60
CALL_SPACING_SECONDS = 1.0
RETRY_WAIT_MAX_SECONDS = 60.0
RETRIES = 3
PAGE_REREADS = 3
NOT_SERVED = 404
EXPIRED_STATUSES = frozenset({400, 403})

Stamp = tuple[datetime, str]


class PortalReader(Protocol):
    @property
    def portal(self) -> str: ...

    async def state(self) -> FieldVoicesState: ...

    async def page(
        self, stream: str, view: str, cursor: str | None, *, screen: PortalScreen
    ) -> FieldVoicesPage: ...


class ImageCopy(Protocol):
    async def copy(self, item: ImageItem) -> StoredCopy: ...


@dataclass(frozen=True)
class StreamCursors:
    cursor: str | None
    gone_cursor: str | None
    rereading: bool
    last: Stamp | None = None
    gone_last: Stamp | None = None


@dataclass(frozen=True)
class AppliedPage:
    live: int = 0
    gone: int = 0
    images: int = 0


class FieldVoicesLedger(Protocol):
    async def cursors(self, portal: str, stream: str) -> StreamCursors: ...

    async def apply_page(self, page: FieldVoicesPage, copies: Mapping[str, StoredCopy]) -> AppliedPage: ...

    async def needs_copy(self, portal: str, change: Live) -> bool: ...

    async def contact(self, portal: str, stream: str) -> None: ...

    async def matches(self, portal: str, stream: str, state: StreamState) -> bool: ...

    async def restart(self, portal: str, stream: str) -> None: ...

    async def finish_reread(self, portal: str, stream: str) -> int: ...

    async def hide(self, portal: str, stream: str) -> None: ...

    async def relink(self, portal: str) -> None: ...


@dataclass(frozen=True)
class SyncClock:
    monotonic: Callable[[], float] = time.monotonic
    pause: Callable[[float], Awaitable[None]] = asyncio.sleep


@dataclass
class StreamReport:
    stream: str
    ok: bool = True
    skipped: str | None = None
    pages: int = 0
    live: int = 0
    gone: int = 0
    images: int = 0
    refused_pages: int = 0
    withdrawn_unlisted: int = 0
    portal_scrub_misses: int = 0
    caught_up: bool = False
    reconciled: bool | None = None
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "stream": self.stream,
            "ok": self.ok,
            "skipped": self.skipped,
            "pages": self.pages,
            "liveApplied": self.live,
            "goneApplied": self.gone,
            "imagesStored": self.images,
            "refusedPages": self.refused_pages,
            "withdrawnUnlisted": self.withdrawn_unlisted,
            "portalScrubMisses": self.portal_scrub_misses,
            "caughtUp": self.caught_up,
            "reconciled": self.reconciled,
            "error": self.error,
        }


@dataclass
class PortalReport:
    portal: str
    ok: bool = True
    skipped: str | None = None
    error: str | None = None
    streams: list[StreamReport] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "portal": self.portal,
            "ok": self.ok and all(stream.ok for stream in self.streams),
            "skipped": self.skipped,
            "error": self.error,
            "streams": [stream.as_dict() for stream in self.streams],
        }


async def sync_portal(
    reader: PortalReader, ledger: FieldVoicesLedger, copier: ImageCopy | None, *, clock: SyncClock
) -> PortalReport:
    report = PortalReport(portal=reader.portal)
    run = _Run(reader, ledger, copier, clock)
    try:
        state = await run.call(reader.state)
    except ExternalFailure as error:
        return _unreachable(report, error)
    except (InvalidInput, Refused) as error:
        return replace(report, ok=False, error=f"refused: {error}")
    await ledger.relink(reader.portal)
    for stream in STREAMS:
        report.streams.append(await run.stream(stream, state.stream(stream)))
    return report


def _stopped(report: StreamReport, error: Exception, *, refused: bool) -> None:
    report.ok = False
    report.error = str(error)
    if refused:
        report.refused_pages += 1
    logger.warning("%s stopped: %s", report.stream, error)


def _after(portal: str, page: FieldVoicesPage, last: Stamp | None) -> Stamp | None:
    if not page.changes:
        return last
    first = page.changes[0]
    if last is not None and (first.updated_at, first.id) <= last:
        raise InvalidInput(
            f"{portal} {page.stream} {page.view} page starts at {first.id}, before the page it follows"
        )
    final = page.changes[-1]
    return final.updated_at, final.id


@dataclass(frozen=True)
class _Position:
    cursor: str | None
    last: Stamp | None


def _unreachable(report: PortalReport, error: ExternalFailure) -> PortalReport:
    if error.status == NOT_SERVED:
        return replace(report, skipped="not_served")
    return replace(report, ok=False, error=str(error))


class _Run:
    def __init__(
        self, reader: PortalReader, ledger: FieldVoicesLedger, copier: ImageCopy | None, clock: SyncClock
    ) -> None:
        self._reader = reader
        self._ledger = ledger
        self._copier = copier
        self._clock = clock
        self._called = False

    @property
    def portal(self) -> str:
        return self._reader.portal

    async def stream(self, stream: str, state: StreamState) -> StreamReport:
        report = StreamReport(stream=stream)
        if not state.enabled or (stream == IMAGES and self._copier is None):
            await self._ledger.hide(self.portal, stream)
            report.skipped = "disabled" if not state.enabled else "no_media_bucket"
            return report
        screen = PortalScreen()
        try:
            await self._stream(stream, report, screen)
        except ExternalFailure as error:
            _stopped(report, error, refused=False)
        except (AppError, ValueError) as error:
            _stopped(report, error, refused=True)
        report.portal_scrub_misses = screen.misses
        return report

    async def _stream(self, stream: str, report: StreamReport, screen: PortalScreen) -> None:
        cursors = await self._ledger.cursors(self.portal, stream)
        gone = _Position(cursors.gone_cursor, cursors.gone_last)
        await self._read(stream, VIEW_GONE, gone, report, screen, deadline=None)
        await self._ledger.contact(self.portal, stream)
        deadline = self._clock.monotonic() + STREAM_BUDGET_SECONDS
        everything = _Position(cursors.cursor, cursors.last)
        report.caught_up = await self._read(stream, VIEW_ALL, everything, report, screen, deadline=deadline)
        if not report.caught_up:
            return
        if cursors.rereading:
            report.withdrawn_unlisted = await self._ledger.finish_reread(self.portal, stream)
        await self._reconcile(stream, report)

    async def _read(
        self,
        stream: str,
        view: str,
        start: _Position,
        report: StreamReport,
        screen: PortalScreen,
        *,
        deadline: float | None,
    ) -> bool:
        cursor, last = start.cursor, start.last
        while deadline is None or self._clock.monotonic() < deadline:
            page, copies = await self._page_with_copies(stream, view, cursor, screen)
            last = _after(self.portal, page, last)
            applied = await self._ledger.apply_page(page, copies)
            report.pages += 1
            report.live += applied.live
            report.gone += applied.gone
            report.images += applied.images
            if not page.has_more:
                return True
            if page.next_cursor is None or page.next_cursor == cursor:
                raise InvalidInput(f"{self.portal} {stream} {view} pages do not move past cursor {cursor!r}")
            cursor = page.next_cursor
        return False

    async def _page_with_copies(
        self, stream: str, view: str, cursor: str | None, screen: PortalScreen
    ) -> tuple[FieldVoicesPage, dict[str, StoredCopy]]:
        for attempt in range(1, PAGE_REREADS + 1):
            page = await self.call(lambda: self._reader.page(stream, view, cursor, screen=screen))
            try:
                return page, await self._copies(page)
            except ExternalFailure as error:
                if error.status not in EXPIRED_STATUSES or attempt == PAGE_REREADS:
                    raise
                logger.info("%s %s page links expired; reading it again", self.portal, stream)
        raise RuntimeError("unreachable")

    async def _copies(self, page: FieldVoicesPage) -> dict[str, StoredCopy]:
        copies: dict[str, StoredCopy] = {}
        if self._copier is None:
            return copies
        for change in page.changes:
            item = change.item if isinstance(change, Live) else None
            if isinstance(item, ImageItem) and await self._ledger.needs_copy(page.portal, change):
                copies[change.id] = await self._copier.copy(item)
        return copies

    async def _reconcile(self, stream: str, report: StreamReport) -> None:
        state = (await self.call(self._reader.state)).stream(stream)
        cursors = await self._ledger.cursors(self.portal, stream)
        if state.latest_cursor != cursors.cursor:
            return
        report.reconciled = await self._ledger.matches(self.portal, stream, state)
        if not report.reconciled:
            await self._ledger.restart(self.portal, stream)

    async def call[T](self, ask: Callable[[], Awaitable[T]]) -> T:
        for attempt in range(1, RETRIES + 2):
            if self._called:
                await self._clock.pause(CALL_SPACING_SECONDS)
            self._called = True
            try:
                return await ask()
            except ExternalFailure as error:
                if not error.retryable or error.status == NOT_SERVED or attempt > RETRIES:
                    raise
                await self._clock.pause(
                    min(error.retry_after or CALL_SPACING_SECONDS, RETRY_WAIT_MAX_SECONDS)
                )
        raise RuntimeError("unreachable")
