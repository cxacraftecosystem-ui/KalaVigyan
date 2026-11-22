from __future__ import annotations

import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, field

from app.core.errors import ExternalFailure
from app.research.fetcher import FetchRefused

from .robots_txt import ALLOW_ALL, DISALLOW_ALL, RobotsRules, parse_robots
from .targets import Target, checked_target, redirect_target
from .transport import HopGetter

__all__ = [
    "ROBOTS_AGENT",
    "ROBOTS_MAX_BYTES",
    "ROBOTS_MAX_REDIRECTS",
    "ROBOTS_TTL_SECONDS",
    "RobotsPolicy",
    "rules_for_answer",
]

ROBOTS_AGENT = "KalaVigyan"
ROBOTS_MAX_BYTES = 512 * 1024
ROBOTS_MAX_REDIRECTS = 5
ROBOTS_TTL_SECONDS = 3600.0
ROBOTS_CACHE_MAX = 1024
UNREADABLE_ROBOTS = frozenset({"TOO_LARGE", "NOT_HTTPS", "BAD_URL", "CONTENT_TYPE"})


@dataclass
class RobotsPolicy:
    clock: Callable[[], float] = time.monotonic
    _rules: OrderedDict[str, tuple[float, RobotsRules]] = field(default_factory=OrderedDict)

    async def check(self, target: Target, http: HopGetter, *, timeout: float) -> None:
        rules = await self._rules_for(target, http, timeout)
        if not rules.allows(target.path):
            raise FetchRefused(target.url, "ROBOTS_DISALLOWED", f"robots.txt of {target.host} disallows it")

    async def _rules_for(self, page: Target, http: HopGetter, timeout: float) -> RobotsRules:
        host = page.host
        cached = self._rules.get(host)
        if cached is not None and self.clock() - cached[0] <= ROBOTS_TTL_SECONDS:
            self._rules.move_to_end(host)
            return cached[1]
        try:
            rules = await _read(page, http, timeout)
        except ExternalFailure:
            return DISALLOW_ALL
        except FetchRefused as refusal:
            if refusal.reason in UNREADABLE_ROBOTS:
                return DISALLOW_ALL
            raise
        self._rules[host] = (self.clock(), rules)
        while len(self._rules) > ROBOTS_CACHE_MAX:
            self._rules.popitem(last=False)
        return rules


def rules_for_answer(status: int, body: bytes) -> RobotsRules:
    if 200 <= status < 300:
        return parse_robots(body.decode("utf-8", errors="replace")).rules_for(ROBOTS_AGENT)
    if 400 <= status < 500 and status != 429:
        return ALLOW_ALL
    return DISALLOW_ALL


async def _read(page: Target, http: HopGetter, timeout: float) -> RobotsRules:
    target = checked_target(f"https://{page.netloc}/robots.txt")
    for _ in range(ROBOTS_MAX_REDIRECTS + 1):
        hop = await http.get(target, max_bytes=ROBOTS_MAX_BYTES, timeout=timeout, accept="text/plain")
        if not hop.is_redirect or hop.location is None:
            return rules_for_answer(hop.status, hop.body)
        target = redirect_target(target, hop.location)
    return DISALLOW_ALL
