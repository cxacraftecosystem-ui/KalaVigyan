from __future__ import annotations

import httpx

from app.research.fetcher import Fetcher
from app.research.images import ImageSource

from ..adapter import Clock, utc_now
from ..http import RatePolicy, ResponseCache, SourceHttp
from ..reference.commons import COMMONS_RATE, WikimediaCommonsAdapter
from ..web.searxng import SEARXNG_RATE, SearxngAdapter
from .europe_pmc_figures import EUROPE_PMC_FIGURES_RATE, EuropePmcFiguresAdapter
from .openverse import OPENVERSE_RATE, OpenverseAdapter

__all__ = ["figure_source", "image_sources"]


def image_sources(
    client: httpx.AsyncClient, *, searxng_url: str, fetcher: Fetcher, clock: Clock = utc_now
) -> tuple[ImageSource, ...]:
    def http(service: str, policy: RatePolicy) -> SourceHttp:
        return SourceHttp(client=client, service=service, policy=policy, cache=ResponseCache())

    return (
        WikimediaCommonsAdapter(http(WikimediaCommonsAdapter.name, COMMONS_RATE), clock=clock),
        OpenverseAdapter(http(OpenverseAdapter.name, OPENVERSE_RATE), clock=clock),
        SearxngAdapter(
            http(SearxngAdapter.name, SEARXNG_RATE), base_url=searxng_url, fetcher=fetcher, clock=clock
        ),
    )


def figure_source(client: httpx.AsyncClient, *, clock: Clock = utc_now) -> ImageSource:
    http = SourceHttp(
        client=client,
        service=EuropePmcFiguresAdapter.name,
        policy=EUROPE_PMC_FIGURES_RATE,
        cache=ResponseCache(),
    )
    return EuropePmcFiguresAdapter(http, clock=clock)
