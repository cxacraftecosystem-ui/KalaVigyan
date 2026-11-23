from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Literal

from pydantic import Field

from app.models.admin_work import REFRESH_ORIGINS, REFRESH_PHASES, REFRESH_SCOPES, REFRESH_STATUSES

from .base import ContractModel

__all__ = [
    "CHANGED",
    "CHANGED_COOLDOWN",
    "DEAD_AFTER",
    "DOCUMENTS_PHASE",
    "DONE",
    "EVERY",
    "EVERY_COOLDOWN",
    "FAILED",
    "FINISHED_PHASE",
    "JOB_SECONDS",
    "MCP_ORIGIN",
    "NAMED",
    "NIGHT_DEAD_AFTER",
    "NIGHT_ORIGIN",
    "PAGES_PHASE",
    "PAGE_REFRESH_SCHEMA_VERSION",
    "REFRESHING_PHASE",
    "REVIEW_ORIGIN",
    "RUNNING",
    "UNREFRESHED_SHOWN",
    "WEB_ORIGIN",
    "PageRefreshState",
    "RefreshJobView",
    "RefreshProgress",
    "RefreshStart",
    "cooldown_end",
]

PAGE_REFRESH_SCHEMA_VERSION = 1
CHANGED, EVERY, NAMED = REFRESH_SCOPES
WEB_ORIGIN, MCP_ORIGIN, NIGHT_ORIGIN, REVIEW_ORIGIN = REFRESH_ORIGINS
RUNNING, DONE, FAILED = REFRESH_STATUSES
PAGES_PHASE, DOCUMENTS_PHASE, REFRESHING_PHASE, FINISHED_PHASE = REFRESH_PHASES
CHANGED_COOLDOWN = timedelta(minutes=10)
EVERY_COOLDOWN = timedelta(hours=24)
JOB_SECONDS = 480.0
DEAD_AFTER = timedelta(minutes=15)
NIGHT_DEAD_AFTER = timedelta(minutes=90)
UNREFRESHED_SHOWN = 40

RefreshScope = Literal[*REFRESH_SCOPES]
RefreshOrigin = Literal[*REFRESH_ORIGINS]
RefreshStatus = Literal[*REFRESH_STATUSES]
RefreshPhase = Literal[*REFRESH_PHASES]


class RefreshProgress(ContractModel):
    pages_stale: int = Field(default=0, ge=0)
    pages_rebuilt: int = Field(default=0, ge=0)
    pages_changed: int = Field(default=0, ge=0)
    documents_stale: int = Field(default=0, ge=0)
    documents_rebuilt: int = Field(default=0, ge=0)
    pages_to_refresh: int = Field(default=0, ge=0)
    pages_refreshed: int = Field(default=0, ge=0)
    unrefreshed: list[str] = Field(default_factory=list, max_length=UNREFRESHED_SHOWN)
    failed: list[str] = Field(default_factory=list, max_length=UNREFRESHED_SHOWN)


class RefreshJobView(ContractModel):
    id: uuid.UUID
    scope: RefreshScope
    origin: RefreshOrigin
    status: RefreshStatus
    phase: RefreshPhase
    started_by: str | None
    client_name: str | None
    started_at: datetime
    finished_at: datetime | None
    progress: RefreshProgress
    note: str | None


class PageRefreshState(ContractModel):
    schema_version: Literal[1] = PAGE_REFRESH_SCHEMA_VERSION
    configured: bool
    running: RefreshJobView | None
    last: RefreshJobView | None
    next_allowed_at: datetime | None
    every_allowed_at: datetime | None
    may_refresh_every: bool


class RefreshStart(ContractModel):
    every: bool = False


def cooldown_end(last_started: datetime | None, cooldown: timedelta, *, now: datetime) -> datetime | None:
    if last_started is None:
        return None
    ends = last_started + cooldown
    return ends if ends > now else None
