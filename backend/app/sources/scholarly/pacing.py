from __future__ import annotations

import asyncio
import contextlib
import time
import weakref
from collections import OrderedDict
from collections.abc import Callable, Mapping
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, field
from functools import cache
from urllib.parse import urlsplit

from app.core.errors import ExternalFailure
from app.core.logging import current_request_id

from ..http import DEFAULT_BLOCK_SECONDS, ResponseCache, SourceHttp, SourceResponse

__all__ = [
    "ANSWERS_HELD",
    "PACED_SHARE",
    "QUEUE_WAIT_MAX",
    "REFUSALS_MAX",
    "AnswerLookups",
    "PacedHttp",
    "ScholarlyPacing",
    "ServiceLimits",
    "SourceLimit",
    "shared_pacing",
]

PACED_SHARE = 0.8
REFUSALS_MAX = 2
QUEUE_WAIT_MAX = 30.0
ANSWERS_HELD = 32
REFUSED_STATUSES = frozenset({403, 429})
SEARCH_LANE = "search"
LOOKUP_LANE = "lookup"

LookupKey = tuple[str, str, tuple[tuple[str, str], ...], tuple[tuple[str, str], ...]]


@dataclass(frozen=True)
class SourceLimit:
    requests: float
    seconds: float = 1.0
    concurrency: int | None = None

    def __post_init__(self) -> None:
        if self.requests <= 0 or self.seconds <= 0 or (self.concurrency is not None and self.concurrency < 1):
            raise ValueError("a source limit allows some requests in some seconds, one at a time or more")

    @property
    def interval(self) -> float:
        return self.seconds / (self.requests * PACED_SHARE)


@dataclass(frozen=True)
class ServiceLimits:
    search: SourceLimit
    lookup: SourceLimit | None = None
    search_path: str = ""

    def lane(self, url: str) -> str:
        if self.lookup is None or urlsplit(url).path.endswith(self.search_path):
            return SEARCH_LANE
        return LOOKUP_LANE

    def limit(self, lane: str) -> SourceLimit:
        return self.lookup if lane == LOOKUP_LANE and self.lookup is not None else self.search

    @property
    def concurrency(self) -> int | None:
        shown = [limit.concurrency for limit in (self.search, self.lookup) if limit and limit.concurrency]
        return min(shown, default=None)


@dataclass
class AnswerLookups:
    refusals: dict[str, int] = field(default_factory=dict)
    failed: dict[LookupKey, ExternalFailure] = field(default_factory=dict)

    def asked_too_often(self, service: str) -> bool:
        return self.refusals.get(service, 0) >= REFUSALS_MAX

    def note(self, key: LookupKey, failure: ExternalFailure) -> None:
        self.failed[key] = failure
        if failure.kind == "rate_limit" or failure.status in REFUSED_STATUSES:
            self.refusals[key[0]] = self.refusals.get(key[0], 0) + 1


class ScholarlyPacing:
    def __init__(self, *, cache_clock: Callable[[], float] = time.monotonic) -> None:
        self._cache_clock = cache_clock
        self._next: dict[tuple[str, str], float] = {}
        self._held: dict[str, float] = {}
        self._caches: dict[str, ResponseCache] = {}
        self._gates: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, dict[str, asyncio.Semaphore]] = (
            weakref.WeakKeyDictionary()
        )
        self._answers: OrderedDict[str, AnswerLookups] = OrderedDict()

    def reserve(self, service: str, lane: str, interval: float, *, now: float) -> float | None:
        start = max(now, self._next.get((service, lane), 0.0), self._held.get(service, 0.0))
        if start - now > QUEUE_WAIT_MAX:
            return None
        self._next[(service, lane)] = start + interval
        return start - now

    def hold(self, service: str, until: float) -> None:
        self._held[service] = max(self._held.get(service, 0.0), until)

    def held_for(self, service: str, now: float) -> float:
        return max(self._held.get(service, 0.0) - now, 0.0)

    def gate(self, service: str, concurrency: int | None) -> AbstractAsyncContextManager[object]:
        if concurrency is None:
            return contextlib.nullcontext()
        gates = self._gates.setdefault(asyncio.get_running_loop(), {})
        return gates.setdefault(service, asyncio.Semaphore(concurrency))

    def cache(self, service: str) -> ResponseCache:
        return self._caches.setdefault(service, ResponseCache(clock=self._cache_clock))

    def answer(self) -> AnswerLookups | None:
        request_id = current_request_id()
        if request_id is None:
            return None
        found = self._answers.pop(request_id, None) or AnswerLookups()
        self._answers[request_id] = found
        while len(self._answers) > ANSWERS_HELD:
            self._answers.popitem(last=False)
        return found


@cache
def shared_pacing() -> ScholarlyPacing:
    return ScholarlyPacing()


@dataclass
class PacedHttp(SourceHttp):
    limits: ServiceLimits = ServiceLimits(search=SourceLimit(requests=1))
    pacing: ScholarlyPacing = field(default_factory=shared_pacing)

    async def get(
        self,
        url: str,
        *,
        params: Mapping[str, str] | None = None,
        headers: Mapping[str, str] | None = None,
        secret_params: Mapping[str, str] | None = None,
        secret_headers: Mapping[str, str] | None = None,
    ) -> SourceResponse:
        answer = self.pacing.answer()
        key = (
            self.service,
            url,
            tuple(sorted((params or {}).items())),
            tuple(sorted((headers or {}).items())),
        )
        if answer is not None:
            self._check_answer(answer, key)
        try:
            return await super().get(
                url,
                params=params,
                headers=headers,
                secret_params=secret_params,
                secret_headers=secret_headers,
            )
        except ExternalFailure as failure:
            if answer is not None:
                answer.note(key, failure)
            raise

    async def _get_once(self, url: str, params: dict, headers: dict) -> SourceResponse:
        lane = self.limits.lane(url)
        interval = self.limits.limit(lane).interval
        now = self.clock()
        held = self.pacing.held_for(self.service, now)
        if held > self.policy.max_retry_wait:
            raise self._failure(f"is paused for {held:.0f} more seconds", kind="rate_limit", retry_after=held)
        wait = self.pacing.reserve(self.service, lane, interval, now=now)
        if wait is None:
            raise self._failure(
                f"has more than {QUEUE_WAIT_MAX:.0f} seconds of requests waiting", kind="unavailable"
            )
        if wait > 0:
            await self.sleep(wait)
        async with self.pacing.gate(self.service, self.limits.concurrency):
            return await super()._get_once(url, params, headers)

    def _note_rate_limit(self, retry_after: float | None) -> None:
        super()._note_rate_limit(retry_after)
        pause = DEFAULT_BLOCK_SECONDS if retry_after is None else retry_after
        self.pacing.hold(self.service, self.clock() + pause)

    def _check_answer(self, answer: AnswerLookups, key: LookupKey) -> None:
        if answer.asked_too_often(self.service):
            raise self._failure(
                f"refused {REFUSALS_MAX} requests of this answer, so it is not asked again", kind="rate_limit"
            )
        failed = answer.failed.get(key)
        if failed is not None:
            raise failed
