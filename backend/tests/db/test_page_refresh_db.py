import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, PageRefreshJob, User
from app.research.page_refresh import RefreshProgress
from app.research.page_revalidation import PageOwners
from app.services import page_refresh_run
from app.services.page_refresh_jobs import (
    BUSY,
    EVERY_FOR_MASTER,
    TOO_SOON,
    RefreshAsk,
    RefreshRefused,
    claim_night,
    finish_job,
    refresh_state,
    start_refresh,
)
from app.services.page_refresh_run import run_refresh_job

from .testimony_seed import rolled_back_session

pytestmark = pytest.mark.db

NOW = datetime(2026, 11, 19, 12, tzinfo=UTC)
SLUG = "Page-Refresh-Test-Craft"


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in rolled_back_session():
        yield opened


async def person(session: AsyncSession, role: str) -> User:
    key = uuid.uuid4()
    made = User(id=key, name=f"{role.title()} {key.hex[:4]}", email=f"{key.hex[:12]}@example.org", role=role)
    session.add(made)
    await session.flush()
    return made


def asked(scope: str, actor: User | None, origin: str = "WEB") -> RefreshAsk:
    return RefreshAsk(scope, origin, actor, client_name="Claude" if origin == "MCP" else None)


async def done(session: AsyncSession, job_id: uuid.UUID) -> None:
    await finish_job(session, job_id, status="DONE", progress=RefreshProgress(), note=None)


async def test_one_job_runs_at_a_time_and_the_night_never_runs_beside_one(session: AsyncSession) -> None:
    admin = await person(session, "ADMIN")
    night = await claim_night(session, now=NOW)
    assert night is not None
    with pytest.raises(RefreshRefused) as refused:
        await start_refresh(session, asked("CHANGED", admin), now=NOW)
    assert refused.value.reason == BUSY and "night" in refused.value.message
    owners = PageOwners(crafts=(SLUG,))
    with pytest.raises(RefreshRefused):
        await start_refresh(session, RefreshAsk("NAMED", "REVIEW", admin, owners=owners), now=NOW)
    await done(session, night)
    job = await start_refresh(session, asked("CHANGED", admin, "MCP"), now=NOW)
    assert await claim_night(session, now=NOW + timedelta(minutes=1)) is None
    stored = await session.get(PageRefreshJob, job)
    assert stored is not None and (stored.origin, stored.clientName, stored.startedById) == (
        "MCP",
        "Claude",
        admin.id,
    )
    audited = await session.scalars(
        select(AuditLog.detail).where(AuditLog.action == "site.pages_refresh_started")
    )
    assert audited.all() == [{"scope": "CHANGED", "origin": "MCP", "client": "Claude"}]


async def test_a_manual_refresh_waits_ten_minutes_and_every_page_is_the_master_admins_once_a_day(
    session: AsyncSession,
) -> None:
    admin, master = await person(session, "ADMIN"), await person(session, "MASTER_ADMIN")
    await done(session, await start_refresh(session, asked("CHANGED", admin), now=NOW))
    with pytest.raises(RefreshRefused) as early:
        await start_refresh(session, asked("CHANGED", admin), now=NOW + timedelta(minutes=5))
    assert early.value.reason == TOO_SOON and early.value.retry_after == 300
    with pytest.raises(RefreshRefused) as not_master:
        await start_refresh(session, asked("EVERY", admin), now=NOW + timedelta(minutes=11))
    assert not_master.value.reason == EVERY_FOR_MASTER
    await done(session, await start_refresh(session, asked("EVERY", master), now=NOW + timedelta(minutes=11)))
    with pytest.raises(RefreshRefused) as daily:
        await start_refresh(session, asked("EVERY", master), now=NOW + timedelta(hours=2))
    assert daily.value.reason == TOO_SOON and daily.value.retry_after == (22 * 3600 + 11 * 60)
    state = await refresh_state(session, master, now=NOW + timedelta(hours=2))
    assert state.running is None and state.last is not None and state.last.scope == "EVERY"
    assert state.next_allowed_at is None and state.may_refresh_every is True
    assert state.every_allowed_at == NOW + timedelta(minutes=11) + timedelta(hours=24)


async def test_a_job_that_stopped_without_finishing_gives_way_after_fifteen_minutes(
    session: AsyncSession,
) -> None:
    admin = await person(session, "ADMIN")
    stalled = await start_refresh(session, asked("CHANGED", admin), now=NOW)
    with pytest.raises(RefreshRefused):
        await start_refresh(session, RefreshAsk("NAMED", "REVIEW", admin), now=NOW + timedelta(minutes=14))
    later = await start_refresh(
        session, RefreshAsk("NAMED", "REVIEW", admin), now=NOW + timedelta(minutes=16)
    )
    ended = await session.get(PageRefreshJob, stalled, populate_existing=True)
    assert ended is not None and (ended.status, ended.phase) == ("FAILED", "FINISHED") and ended.note
    state = await refresh_state(session, admin, now=NOW + timedelta(minutes=16))
    assert state.running is not None and state.running.id == later and state.may_refresh_every is False


async def test_a_named_refresh_rebuilds_only_its_pages_and_sends_them_to_the_site(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    admin = await person(session, "ADMIN")
    owners = PageOwners(crafts=(SLUG,), categories=("Page-Refresh-Test-Category",))
    sent: list[PageOwners] = []

    async def refreshed(targets: PageOwners) -> dict[str, Any]:
        sent.append(targets)
        return {"ok": True, "pages": 2, "refreshed": 2, "unrefreshed": []}

    monkeypatch.setattr(page_refresh_run, "nightly_refresh", refreshed)
    job = await start_refresh(session, RefreshAsk("NAMED", "REVIEW", admin, owners=owners), now=NOW)

    @asynccontextmanager
    async def same() -> AsyncIterator[AsyncSession]:
        yield session

    await run_refresh_job(same, job)
    stored = await session.get(PageRefreshJob, job, populate_existing=True)
    assert stored is not None and (stored.status, stored.phase) == ("DONE", "FINISHED")
    assert sent == [owners]
    progress = RefreshProgress.model_validate(stored.progress)
    assert (progress.pages_rebuilt, progress.pages_to_refresh, progress.pages_refreshed) == (0, 2, 2)
