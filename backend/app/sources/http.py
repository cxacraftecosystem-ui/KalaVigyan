from __future__ import annotations

import asyncio
import json
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.core.errors import RETRYABLE_KINDS, ExternalFailure, failure_kind
from app.core.retry_after import parse_headers

__all__ = [
    "DEFAULT_BLOCK_SECONDS",
    "RATE_LIMITED_STATUSES",
    "SOURCE_MAX_BYTES",
    "SOURCE_TIMEOUT_SECONDS",
    "RatePolicy",
    "ResponseCache",
    "SourceHttp",
    "SourceResponse",
    "source_client",
]

SOURCE_TIMEOUT_SECONDS = 20.0
SOURCE_MAX_BYTES = 8 * 1024 * 1024
DEFAULT_BLOCK_SECONDS = 60.0
RATE_LIMITED_STATUSES = frozenset({429, 503})
CACHE_TTL_SECONDS = 600.0
CACHE_MAX_ENTRIES = 512

USER_AGENT = "KalaVigyan (https://kalavigyan.vercel.app; mailto:{contact})"

Clock = Callable[[], float]
Sleep = Callable[[float], Awaitable[None]]


@dataclass(frozen=True)
class RatePolicy:
    min_interval: float
    max_retry_wait: float = 10.0

    def __post_init__(self) -> None:
        if self.min_interval < 0 or self.max_retry_wait < 0:
            raise ValueError("Rate policy intervals are never negative")


@dataclass(frozen=True)
class SourceResponse:
    status: int
    content_type: str
    body: bytes
    retry_after: float | None = None

    def json(self, service: str) -> Any:
        try:
            return json.loads(self.body)
        except ValueError:
            raise ExternalFailure(
                f"{service} answered with a body that is not JSON", service=service
            ) from None

    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")


@dataclass
class ResponseCache:
    ttl_seconds: float = CACHE_TTL_SECONDS
    max_entries: int = CACHE_MAX_ENTRIES
    clock: Clock = time.monotonic
    _entries: OrderedDict[tuple, tuple[float, SourceResponse]] = field(default_factory=OrderedDict)

    def get(self, key: tuple) -> SourceResponse | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        stored_at, response = entry
        if self.clock() - stored_at > self.ttl_seconds:
            del self._entries[key]
            return None
        self._entries.move_to_end(key)
        return response

    def put(self, key: tuple, response: SourceResponse) -> None:
        self._entries[key] = (self.clock(), response)
        self._entries.move_to_end(key)
        while len(self._entries) > self.max_entries:
            self._entries.popitem(last=False)


@dataclass
class SourceHttp:
    client: httpx.AsyncClient
    service: str
    policy: RatePolicy
    cache: ResponseCache = field(default_factory=ResponseCache)
    clock: Clock = time.monotonic
    sleep: Sleep = asyncio.sleep
    _next_allowed: float = 0.0
    _blocked_until: float = 0.0
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def get(
        self,
        url: str,
        *,
        params: Mapping[str, str] | None = None,
        headers: Mapping[str, str] | None = None,
        secret_params: Mapping[str, str] | None = None,
        secret_headers: Mapping[str, str] | None = None,
    ) -> SourceResponse:
        public = dict(params or {})
        key = (url, tuple(sorted(public.items())), tuple(sorted((headers or {}).items())))
        cached = self.cache.get(key)
        if cached is not None:
            return cached
        request_params = public | dict(secret_params or {})
        request_headers = dict(headers or {}) | dict(secret_headers or {})
        response = await self._get_with_retry(url, request_params, request_headers)
        self.cache.put(key, response)
        return response

    async def _get_with_retry(self, url: str, params: dict, headers: dict) -> SourceResponse:
        try:
            return await self._get_once(url, params, headers)
        except ExternalFailure as failure:
            wait = failure.retry_after
            if failure.kind not in RETRYABLE_KINDS or wait is None or wait > self.policy.max_retry_wait:
                raise
        return await self._get_once(url, params, headers)

    async def _get_once(self, url: str, params: dict, headers: dict) -> SourceResponse:
        await self._pace()
        try:
            response = await self._send(url, params, headers)
        except httpx.TimeoutException:
            raise self._failure("timed out", kind="unavailable") from None
        except httpx.HTTPError:
            raise self._failure("could not be reached", kind="unavailable") from None
        if not 200 <= response.status < 300:
            raise self._status_failure(response)
        return response

    async def _send(self, url: str, params: dict, headers: dict) -> SourceResponse:
        async with self.client.stream("GET", url, params=params, headers=headers) as streamed:
            body = bytearray()
            async for chunk in streamed.aiter_bytes():
                body.extend(chunk)
                if len(body) > SOURCE_MAX_BYTES:
                    raise self._failure(f"sent more than {SOURCE_MAX_BYTES} bytes", kind="error")
            content_type = streamed.headers.get("content-type", "").split(";")[0].strip().lower()
            retry_after = None
            if streamed.status_code in RATE_LIMITED_STATUSES:
                retry_after = parse_headers(streamed.headers)
                self._note_rate_limit(retry_after)
            return SourceResponse(streamed.status_code, content_type, bytes(body), retry_after)

    async def _pace(self) -> None:
        async with self._lock:
            now = self.clock()
            blocked_for = self._blocked_until - now
            if blocked_for > self.policy.max_retry_wait:
                raise self._failure(
                    f"asked for a pause of {blocked_for:.0f} more seconds",
                    kind="rate_limit",
                    retry_after=blocked_for,
                )
            wait = max(self._next_allowed - now, blocked_for, 0.0)
            self._next_allowed = now + wait + self.policy.min_interval
            if wait > 0:
                await self.sleep(wait)

    def _note_rate_limit(self, retry_after: float | None) -> None:
        pause = DEFAULT_BLOCK_SECONDS if retry_after is None else retry_after
        self._blocked_until = max(self._blocked_until, self.clock() + pause)

    def _status_failure(self, response: SourceResponse) -> ExternalFailure:
        return self._failure(
            f"answered {response.status}",
            kind=failure_kind(response.status),
            status=response.status,
            retry_after=response.retry_after,
        )

    def _failure(
        self, what: str, *, kind: str, status: int | None = None, retry_after: float | None = None
    ) -> ExternalFailure:
        return ExternalFailure(
            f"{self.service} {what}",
            kind=kind,
            retryable=kind in RETRYABLE_KINDS,
            status=status,
            retry_after=retry_after,
            service=self.service,
        )


def source_client(contact_email: str) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=SOURCE_TIMEOUT_SECONDS,
        follow_redirects=False,
        headers={"User-Agent": USER_AGENT.format(contact=contact_email)},
    )
