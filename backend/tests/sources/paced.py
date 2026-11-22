from __future__ import annotations

import asyncio
from dataclasses import dataclass

import httpx

from app.core.paces import PaceStore
from app.sources.http import RatePolicy
from app.sources.scholarly.pacing import PacedHttp, ScholarlyPacing, ServiceLimits

from .recorded import FakeClock


@dataclass
class YieldingClock(FakeClock):
    async def sleep(self, seconds: float) -> None:
        await super().sleep(seconds)
        await asyncio.sleep(0)


def process(
    client: httpx.AsyncClient, service: str, limits: ServiceLimits, store: PaceStore, clock: FakeClock
) -> PacedHttp:
    pacing = ScholarlyPacing(store, clock=clock)
    return PacedHttp(
        client=client,
        service=service,
        policy=RatePolicy(min_interval=0.0),
        cache=pacing.cache(service),
        clock=clock,
        sleep=clock.sleep,
        limits=limits,
        pacing=pacing,
    )
