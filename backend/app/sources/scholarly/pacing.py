from __future__ import annotations

import logging
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field, replace
from functools import cache
from urllib.parse import urlsplit

from app.core.errors import ExternalFailure
from app.core.logging import current_request_id
from app.core.paces import (
    LeaseAsk,
    MemoryPaces,
    PaceAsk,
    PaceLane,
    PaceLease,
    PaceStore,
    PaceUnread,
    SharedPaces,
)

from ..http import (
    DEFAULT_BLOCK_SECONDS,
    RATE_LIMITED_STATUSES,
    SOURCE_TIMEOUT_SECONDS,
    ResponseCache,
    SourceHttp,
    SourceResponse,
)

__all__ = [
    "ANSWERS_HELD",
    "LEASE_SECONDS",
    "LEASE_STEP_SECONDS",
    "PACED_SHARE",
    "QUEUE_WAIT_MAX",
    "REFUSALS_MAX",
    "AnswerLookups",
    "AnswerPace",
    "PacedHttp",
    "ScholarlyPacing",
    "ServiceLimits",
    "ServicePace",
    "SourceLimit",
    "answer_pace",
    "shared_pacing",
]

logger = logging.getLogger(__name__)

PACED_SHARE = 0.8
REFUSALS_MAX = 2
QUEUE_WAIT_MAX = 30.0
LEASE_MARGIN_SECONDS = 10.0
LEASE_SECONDS = SOURCE_TIMEOUT_SECONDS + LEASE_MARGIN_SECONDS
LEASE_STEP_SECONDS = 0.5
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
    def lanes(self) -> tuple[str, ...]:
        return (SEARCH_LANE,) if self.lookup is None else (SEARCH_LANE, LOOKUP_LANE)

    @property
    def concurrency(self) -> int | None:
        shown = [limit.concurrency for limit in (self.search, self.lookup) if limit and limit.concurrency]
        return min(shown, default=None)


@dataclass(frozen=True)
class ServicePace:
    service: str
    waited_seconds: float = 0.0
    waited_requests: int = 0
    refusals: int = 0
    unsent: int = 0


@dataclass(frozen=True)
class AnswerPace:
    request_id: str
    services: tuple[ServicePace, ...] = ()

    @property
    def waited_seconds(self) -> float:
        return sum(service.waited_seconds for service in self.services)


@dataclass
class AnswerLookups:
    paces: dict[str, ServicePace] = field(default_factory=dict)
    failed: dict[LookupKey, ExternalFailure] = field(default_factory=dict)

    def asked_too_often(self, service: str) -> bool:
        return self._pace(service).refusals >= REFUSALS_MAX

    def note(self, key: LookupKey, failure: ExternalFailure) -> None:
        self.failed[key] = failure
        if failure.status in REFUSED_STATUSES:
            pace = self._pace(key[0])
            self.paces[key[0]] = replace(pace, refusals=pace.refusals + 1)

    def note_wait(self, service: str, seconds: float) -> None:
        pace = self._pace(service)
        self.paces[service] = replace(
            pace, waited_seconds=pace.waited_seconds + seconds, waited_requests=pace.waited_requests + 1
        )

    def note_unsent(self, service: str) -> None:
        pace = self._pace(service)
        self.paces[service] = replace(pace, unsent=pace.unsent + 1)

    def record(self, request_id: str) -> AnswerPace:
        return AnswerPace(request_id, tuple(self.paces[name] for name in sorted(self.paces)))

    def _pace(self, service: str) -> ServicePace:
        return self.paces.get(service) or ServicePace(service)


class ScholarlyPacing:
    def __init__(
        self, store: PaceStore | None = None, *, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self.store: PaceStore = store if store is not None else MemoryPaces(clock=clock)
        self._clock = clock
        self._caches: dict[str, ResponseCache] = {}
        self._answers: OrderedDict[str, AnswerLookups] = OrderedDict()

    def cache(self, service: str) -> ResponseCache:
        return self._caches.setdefault(service, ResponseCache(clock=self._clock))

    def answer(self) -> AnswerLookups | None:
        request_id = current_request_id()
        if request_id is None:
            return None
        found = self._answers.pop(request_id, None) or AnswerLookups()
        self._answers[request_id] = found
        while len(self._answers) > ANSWERS_HELD:
            self._answers.popitem(last=False)
        return found

    def answer_pace(self, request_id: str) -> AnswerPace:
        found = self._answers.get(request_id)
        return AnswerPace(request_id) if found is None else found.record(request_id)


@cache
def shared_pacing() -> ScholarlyPacing:
    return ScholarlyPacing(SharedPaces())


def answer_pace(request_id: str | None = None) -> AnswerPace | None:
    found = request_id or current_request_id()
    return None if found is None else shared_pacing().answer_pace(found)


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
        paced = await self._reserve(self.limits.lane(url))
        if paced > 0:
            await self.sleep(paced)
        lease = await self._lease(paced)
        try:
            return await super()._get_once(url, params, headers)
        finally:
            await self._release(lease)

    async def _send(self, url: str, params: dict, headers: dict) -> SourceResponse:
        response = await super()._send(url, params, headers)
        if response.status in RATE_LIMITED_STATUSES:
            await self._hold(DEFAULT_BLOCK_SECONDS if response.retry_after is None else response.retry_after)
        return response

    async def _reserve(self, lane: str) -> float:
        ask = PaceAsk(
            interval=self.limits.limit(lane).interval,
            queue_max=QUEUE_WAIT_MAX,
            hold_max=self.policy.max_retry_wait,
        )
        slot = await self._stored(self.pacing.store.reserve(PaceLane(self.service, lane), ask))
        if slot.wait is None:
            self._note_unsent()
            raise self._refusal(slot.held_for, ask)
        return slot.wait

    async def _lease(self, paced: float) -> PaceLease | None:
        waited = 0.0
        try:
            if self.limits.concurrency is None:
                return None
            ask = LeaseAsk(concurrency=self.limits.concurrency, seconds=LEASE_SECONDS)
            while (lease := await self._stored(self.pacing.store.lease(self.service, ask))) is None:
                if paced + waited + LEASE_STEP_SECONDS > QUEUE_WAIT_MAX:
                    self._note_unsent()
                    raise self._failure(
                        f"had no free request slot within {QUEUE_WAIT_MAX:.0f} seconds", kind="unavailable"
                    )
                await self.sleep(LEASE_STEP_SECONDS)
                waited += LEASE_STEP_SECONDS
            return lease
        finally:
            self._note_wait(paced + waited)

    async def _release(self, lease: PaceLease | None) -> None:
        if lease is None:
            return
        try:
            await self.pacing.store.release(lease)
        except PaceUnread as unread:
            logger.error("%s, so the lease is left to expire: %s", unread, unread.__cause__)

    async def _stored[T](self, call: Awaitable[T]) -> T:
        try:
            return await call
        except PaceUnread as unread:
            logger.error("%s, so the request is not sent: %s", unread, unread.__cause__)
            raise self._failure("could not be paced just now", kind="unavailable") from None

    def _note_wait(self, seconds: float) -> None:
        answer = self.pacing.answer()
        if answer is not None and seconds > 0:
            answer.note_wait(self.service, seconds)

    def _note_unsent(self) -> None:
        answer = self.pacing.answer()
        if answer is not None:
            answer.note_unsent(self.service)

    def _refusal(self, held_for: float, ask: PaceAsk) -> ExternalFailure:
        if held_for > ask.hold_max:
            return self._failure(
                f"is paused for {held_for:.0f} more seconds", kind="rate_limit", retry_after=held_for
            )
        return self._failure(
            f"has more than {ask.queue_max:.0f} seconds of requests waiting", kind="unavailable"
        )

    async def _hold(self, seconds: float) -> None:
        lanes = [PaceLane(self.service, lane) for lane in self.limits.lanes]
        try:
            await self.pacing.store.hold(lanes, seconds)
        except PaceUnread as unread:
            logger.error("%s, so only this client pauses: %s", unread, unread.__cause__)

    def _check_answer(self, answer: AnswerLookups, key: LookupKey) -> None:
        if answer.asked_too_often(self.service):
            answer.note_unsent(self.service)
            raise self._failure(
                f"refused {REFUSALS_MAX} requests of this answer, so it is not asked again", kind="rate_limit"
            )
        failed = answer.failed.get(key)
        if failed is not None:
            raise failed
