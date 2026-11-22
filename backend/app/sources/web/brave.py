from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import httpx

from app.core.errors import ExternalFailure, NotConfigured
from app.core.key_checks import KeyVerdict, checked_get
from app.research.evidence import EvidenceItem, SearchQuery
from app.research.fetcher import Fetcher

from ..adapter import Clock, utc_now
from ..http import RatePolicy, SourceHttp
from ..records import UnusableRecord
from .page import WebPageAdapter

__all__ = [
    "BRAVE_CHECK_QUERY",
    "BRAVE_ENDPOINT",
    "BRAVE_KEY_HEADER",
    "BRAVE_KEY_NAME",
    "BRAVE_MAX_COUNT",
    "BRAVE_RATE",
    "BraveAdapter",
    "check_key",
]

BRAVE_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"
BRAVE_KEY_NAME = "BRAVE_SEARCH_API_KEY"
BRAVE_KEY_HEADER = "X-Subscription-Token"
BRAVE_CHECK_QUERY = {"q": "kalamkari", "count": "1"}
JSON_ACCEPT = {"Accept": "application/json"}
BRAVE_RATE = RatePolicy(min_interval=1.0)
BRAVE_MAX_COUNT = 20


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
    results = web.get("results") if isinstance(web, dict) else None
    if not isinstance(results, list):
        raise ExternalFailure("brave answered without a web results list", service="brave")
    return results
