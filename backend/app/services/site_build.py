from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Protocol
from urllib.parse import urlsplit

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import RETRYABLE_KINDS, ExternalFailure, NotConfigured, Refused, failure_kind
from app.models import AuditLog

from . import audit

__all__ = [
    "DEPLOY_HOOK_SERVICE",
    "DEPLOY_HOOK_SETTING",
    "SITE_BUILD_ACTION",
    "SITE_BUILD_MIN_INTERVAL",
    "BuildTooSoon",
    "DeployHook",
    "SiteBuildHook",
    "SiteBuildState",
    "deploy_hook",
    "refuse_early_build",
    "site_build_state",
    "trigger_site_build",
]

SITE_BUILD_ACTION = "site_build.triggered"
SITE_BUILD_TARGET = "site"
SITE_BUILD_MIN_INTERVAL = timedelta(minutes=10)
DEPLOY_HOOK_SETTING = "VERCEL_DEPLOY_HOOK_URL"
DEPLOY_HOOK_SERVICE = "deploy-hook"
DEPLOY_HOOK_TIMEOUT_SECONDS = 20.0
TOO_SOON = "too_soon"
HTTP_LOGGER = "httpx"


class BuildTooSoon(Refused):
    def __init__(self, retry_after: float) -> None:
        minutes = int(SITE_BUILD_MIN_INTERVAL.total_seconds() // 60)
        super().__init__(
            TOO_SOON, f"A build was started in the last {minutes} minutes. Wait for it to finish."
        )
        self.retry_after = retry_after


class SiteBuildHook(Protocol):
    async def trigger(self) -> None: ...


class DeployHook:
    def __init__(self, url: str, client: httpx.AsyncClient) -> None:
        self._url = url
        self._client = client

    async def trigger(self) -> None:
        try:
            with _unlogged(self._url):
                response = await self._client.post(self._url, timeout=DEPLOY_HOOK_TIMEOUT_SECONDS)
        except httpx.TimeoutException:
            raise _failure("did not answer in time", kind="unavailable") from None
        except httpx.HTTPError:
            raise _failure("could not be reached", kind="unavailable") from None
        if not 200 <= response.status_code < 300:
            status = response.status_code
            raise _failure(f"answered {status}", kind=failure_kind(status), status=status)


class _HiddenAddress(logging.Filter):
    def __init__(self, secret: str) -> None:
        super().__init__()
        self._secret = secret

    def filter(self, record: logging.LogRecord) -> bool:
        return self._secret not in record.getMessage()


@contextmanager
def _unlogged(url: str) -> Iterator[None]:
    path = urlsplit(url).path
    hidden = _HiddenAddress(path if len(path) > 1 else url)
    logger = logging.getLogger(HTTP_LOGGER)
    logger.addFilter(hidden)
    try:
        yield
    finally:
        logger.removeFilter(hidden)


@dataclass(frozen=True)
class SiteBuildState:
    configured: bool
    last_triggered_at: datetime | None
    next_allowed_at: datetime | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "configured": self.configured,
            "lastTriggeredAt": _instant(self.last_triggered_at),
            "nextAllowedAt": _instant(self.next_allowed_at),
        }


def deploy_hook(url: str | None, client: httpx.AsyncClient) -> DeployHook | None:
    cleaned = (url or "").strip()
    return DeployHook(cleaned, client) if cleaned else None


async def site_build_state(session: AsyncSession, *, configured: bool, now: datetime) -> SiteBuildState:
    last = await _last_triggered_at(session)
    allowed = last + SITE_BUILD_MIN_INTERVAL if last is not None else None
    return SiteBuildState(configured, last, allowed if allowed is not None and allowed > now else None)


async def refuse_early_build(session: AsyncSession, *, now: datetime) -> None:
    state = await site_build_state(session, configured=True, now=now)
    if state.next_allowed_at is not None:
        raise BuildTooSoon((state.next_allowed_at - now).total_seconds())


async def trigger_site_build(
    session: AsyncSession, hook: SiteBuildHook | None, *, actor: Any, origin: str
) -> None:
    if hook is None:
        raise NotConfigured(DEPLOY_HOOK_SETTING, f"{DEPLOY_HOOK_SETTING} is not set on the server")
    await hook.trigger()
    await audit.record(
        session,
        action=SITE_BUILD_ACTION,
        actor=actor,
        target_type=SITE_BUILD_TARGET,
        detail={"origin": origin},
    )
    await session.commit()


async def _last_triggered_at(session: AsyncSession) -> datetime | None:
    found: datetime | None = await session.scalar(
        select(AuditLog.createdAt)
        .where(AuditLog.action == SITE_BUILD_ACTION)
        .order_by(AuditLog.createdAt.desc())
        .limit(1)
    )
    return found


def _instant(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _failure(what: str, *, kind: str = "error", status: int | None = None) -> ExternalFailure:
    return ExternalFailure(
        f"the deploy hook {what}",
        kind=kind,
        retryable=kind in RETRYABLE_KINDS,
        status=status,
        service=DEPLOY_HOOK_SERVICE,
    )
