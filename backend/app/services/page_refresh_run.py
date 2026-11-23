from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import datetime
from typing import Any

import httpx
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import sessionmaker
from app.core.errors import AppError
from app.models import PageRefreshJob
from app.research.page_refresh import (
    CHANGED,
    DOCUMENTS_PHASE,
    DONE,
    EVERY,
    FAILED,
    JOB_SECONDS,
    NAMED,
    REFRESHING_PHASE,
    REVIEW_ORIGIN,
    UNREFRESHED_SHOWN,
    RefreshProgress,
)
from app.research.page_revalidation import PageOwners

from .page_refresh_jobs import (
    Background,
    RefreshAsk,
    RefreshRefused,
    finish_job,
    record_progress,
    start_refresh,
)
from .page_revalidation import nightly_refresh, refresh_pages
from .static_pages import static_pages
from .upkeep_pages import (
    DOCUMENTS_PER_NIGHT,
    PAGES_PER_NIGHT,
    PagesReport,
    rebuild_documents,
    rebuild_stale_pages,
)

__all__ = ["EVERY_STALE_PAGE", "launch_refresh", "progress_of", "refresh_named", "run_refresh_job"]

logger = logging.getLogger(__name__)

EVERY_STALE_PAGE = 100_000
OUT_OF_TIME = "The refresh stopped at its time limit; the night rebuilds what is left."
FAILED_NOTE = "The refresh failed: {error}. The night rebuilds the pages as before."
NAMED_STARTED = "Refreshing the {count} pages these decisions touched now."
NAMED_SENT = (
    "Another refresh was running, so the {count} pages these decisions touched were sent to the site "
    "directly; their stored documents follow with that refresh or tonight."
)

Sessions = Callable[[], AbstractAsyncContextManager[AsyncSession]]


async def launch_refresh(
    session: AsyncSession, ask: RefreshAsk, background: Background, *, now: datetime
) -> uuid.UUID:
    job_id = await start_refresh(session, ask, now=now)
    background.start(run_refresh_job(sessionmaker(), job_id), name=f"page refresh {job_id}")
    return job_id


async def refresh_named(
    session: AsyncSession, owners: PageOwners, actor: Any, background: Background, *, now: datetime
) -> str | None:
    if owners.empty:
        return None
    count = len(owners.crafts) + len(owners.categories)
    ask = RefreshAsk(NAMED, REVIEW_ORIGIN, actor, owners=owners)
    try:
        await launch_refresh(session, ask, background, now=now)
    except RefreshRefused:
        await refresh_pages(owners)
        return NAMED_SENT.format(count=count)
    return NAMED_STARTED.format(count=count)


def progress_of(report: PagesReport, refresh: dict[str, Any] | None = None) -> RefreshProgress:
    sent = refresh or {}
    return RefreshProgress(
        pages_stale=report.pages_stale,
        pages_rebuilt=len(report.pages_rebuilt),
        pages_changed=report.pages_changed,
        documents_stale=report.documents.stale,
        documents_rebuilt=len(report.documents.rebuilt),
        pages_to_refresh=int(sent.get("pages", 0)),
        pages_refreshed=int(sent.get("refreshed", 0)),
        unrefreshed=[str(slug) for slug in sent.get("unrefreshed", [])][:UNREFRESHED_SHOWN],
        failed=report.failed[:UNREFRESHED_SHOWN],
    )


async def run_refresh_job(sessions: Sessions, job_id: uuid.UUID) -> None:
    async with sessions() as session:
        job = await session.get(PageRefreshJob, job_id)
        if job is None:
            return
        scope, named = job.scope, _owners(job.owners)
        report = PagesReport()
        try:
            async with asyncio.timeout(JOB_SECONDS):
                refreshed = await _refreshed(session, job_id, scope, named, report)
        except TimeoutError:
            await session.rollback()
            await finish_job(session, job_id, status=DONE, progress=progress_of(report), note=OUT_OF_TIME)
            return
        except (AppError, ValidationError, SQLAlchemyError, httpx.HTTPError, OSError) as error:
            await session.rollback()
            logger.error("the page refresh %s failed: %s", job_id, type(error).__name__)
            note = FAILED_NOTE.format(error=type(error).__name__)
            await finish_job(session, job_id, status=FAILED, progress=progress_of(report), note=note)
            raise
        await finish_job(session, job_id, status=DONE, progress=refreshed, note=None)


async def _refreshed(
    session: AsyncSession, job_id: uuid.UUID, scope: str, named: PageOwners, report: PagesReport
) -> RefreshProgress:
    within = None if scope in (CHANGED, EVERY) else named
    pages = PAGES_PER_NIGHT if scope == CHANGED else EVERY_STALE_PAGE
    documents = DOCUMENTS_PER_NIGHT if scope == CHANGED else EVERY_STALE_PAGE
    await rebuild_stale_pages(session, skip=(), report=report, limit=pages, within=within)
    await record_progress(session, job_id, phase=DOCUMENTS_PHASE, progress=progress_of(report))
    await rebuild_documents(session, report=report, limit=documents, within=within)
    await record_progress(session, job_id, phase=REFRESHING_PHASE, progress=progress_of(report))
    return progress_of(report, await nightly_refresh(await _targets(session, scope, named, report)))


async def _targets(session: AsyncSession, scope: str, named: PageOwners, report: PagesReport) -> PageOwners:
    if scope == CHANGED:
        return report.changed_owners()
    if scope == EVERY:
        listing = await static_pages(session)
        return PageOwners(crafts=listing.crafts, categories=listing.categories)
    return named


def _owners(stored: dict[str, Any] | None) -> PageOwners:
    if not stored:
        return PageOwners()
    return PageOwners(
        crafts=tuple(str(slug) for slug in stored.get("crafts", [])),
        categories=tuple(str(slug) for slug in stored.get("categories", [])),
    )
