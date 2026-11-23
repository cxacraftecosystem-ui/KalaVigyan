from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlsplit

import httpx

from app.core.errors import ExternalFailure, NotConfigured
from app.core.key_checks import KeyVerdict, checked_get
from app.research.evidence import EvidenceItem, SearchQuery
from app.research.fetcher import Fetcher
from app.research.images import ImageCandidate, ImageQuery, clipped, same_site

from ..adapter import Clock, checked_k, usable_records, utc_now
from ..http import RatePolicy, SourceHttp
from ..records import UnusableRecord, https_or_none, title_of
from .page import WebPageAdapter

__all__ = [
    "BRAVE_CHECK_QUERY",
    "BRAVE_ENDPOINT",
    "BRAVE_IMAGES_ENDPOINT",
    "BRAVE_KEY_HEADER",
    "BRAVE_KEY_NAME",
    "BRAVE_MAX_COUNT",
    "BRAVE_RATE",
    "BraveAdapter",
    "check_key",
]

BRAVE_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"
BRAVE_IMAGES_ENDPOINT = "https://api.search.brave.com/res/v1/images/search"
BRAVE_KEY_NAME = "BRAVE_SEARCH_API_KEY"
BRAVE_KEY_HEADER = "X-Subscription-Token"
BRAVE_CHECK_QUERY = {"q": "kalamkari", "count": "1"}
JSON_ACCEPT = {"Accept": "application/json"}
BRAVE_RATE = RatePolicy(min_interval=1.0)
BRAVE_MAX_COUNT = 20
WWW = "www."


class BraveAdapter(WebPageAdapter):
    name = "brave"

    def __init__(self, http: SourceHttp, *, api_key: str, fetcher: Fetcher, clock: Clock = utc_now) -> None:
        if not api_key:
            raise NotConfigured(BRAVE_KEY_NAME, "Brave Search needs an API key")
        super().__init__(http, fetcher=fetcher, clock=clock)
        self._api_key = api_key

    async def _search_records(self, query: SearchQuery, k: int) -> list[Any]:
        params = {
            "q": query.text,
            "count": str(min(k, BRAVE_MAX_COUNT)),
            "search_lang": query.language,
            "safesearch": "strict",
            "text_decorations": "false",
            "result_filter": "web",
        }
        if query.freshness_days is not None:
            today = self.clock().date()
            params["freshness"] = f"{today - timedelta(days=query.freshness_days)}to{today}"
        response = await self.http.get(
            BRAVE_ENDPOINT,
            params=params,
            headers=JSON_ACCEPT,
            secret_headers={BRAVE_KEY_HEADER: self._api_key},
        )
        return _web_results(response.json(self.name))

    async def images(self, query: ImageQuery, k: int) -> list[ImageCandidate]:
        wanted = min(checked_k(k), BRAVE_MAX_COUNT)
        params = {
            "q": query.text,
            "count": str(wanted),
            "search_lang": query.language,
            "safesearch": "strict",
        }
        response = await self.http.get(
            BRAVE_IMAGES_ENDPOINT,
            params=params,
            headers=JSON_ACCEPT,
            secret_headers={BRAVE_KEY_HEADER: self._api_key},
        )
        results = _results(response.json(self.name), "images")
        retrieved_at = self.clock()
        return usable_records(self.name, results, lambda record: self._link_card(record, retrieved_at))[
            :wanted
        ]

    def _link_card(self, record: Any, retrieved_at: datetime) -> ImageCandidate:
        if not isinstance(record, dict):
            raise UnusableRecord("not an object")
        properties = record.get("properties") if isinstance(record.get("properties"), dict) else {}
        page = https_or_none(record.get("url"))
        image = https_or_none(properties.get("url"))
        if page is None or image is None:
            raise UnusableRecord("no https page or image")
        if not same_site(page, image):
            raise UnusableRecord("the image is not served by the page's own site")
        width, height = _size(properties)
        return ImageCandidate(
            provider=self.name,
            page_url=page,
            image_url=image,
            original_url=image,
            width=width,
            height=height,
            title=clipped(title_of(record.get("title"))),
            site=(urlsplit(page).hostname or page).lower().removeprefix(WWW),
            retrieved_at=retrieved_at,
        )

    def _item(self, record: Any, retrieved_at: datetime) -> EvidenceItem:
        if not isinstance(record, dict):
            raise UnusableRecord("not an object")
        profile = record.get("profile")
        return self._hit(
            url=record.get("url"),
            title=record.get("title"),
            published=record.get("page_age"),
            publisher=profile.get("name") if isinstance(profile, dict) else None,
            retrieved_at=retrieved_at,
        )


async def check_key(client: httpx.AsyncClient, value: str) -> KeyVerdict:
    return await checked_get(
        client, BRAVE_ENDPOINT, headers=JSON_ACCEPT | {BRAVE_KEY_HEADER: value}, params=BRAVE_CHECK_QUERY
    )


def _web_results(payload: Any) -> list[Any]:
    if not isinstance(payload, dict):
        raise ExternalFailure("brave answered with a body that is not an object", service="brave")
    web = payload.get("web")
    if web is None:
        return []
    if not isinstance(web, dict):
        raise ExternalFailure("brave answered without a web results list", service="brave")
    return _results(web, "web")


def _results(payload: Any, kind: str) -> list[Any]:
    results = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(results, list):
        raise ExternalFailure(f"brave answered without a {kind} results list", service="brave")
    return results


def _size(properties: dict[str, Any]) -> tuple[int | None, int | None]:
    width, height = properties.get("width"), properties.get("height")
    if all(type(value) is int and value >= 1 for value in (width, height)):
        return width, height
    return None, None
