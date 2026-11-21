import asyncio
import json

import httpx
import pytest
from fastapi import FastAPI

from app.core.errors import ExternalFailure
from app.fetcher.client_documents import ClientDocumentFetch, add_client_document_route
from app.research.fetcher import FetchRefused
from app.research.oauth_client_documents import CLIENT_DOCUMENT_CACHE_HEADER, CLIENT_DOCUMENT_FETCH_PATH

from .site import PUBLIC_A, PUBLIC_B, Site, redirect

HOST = "apps.example.org"
DOCUMENT_URL = f"https://{HOST}/oauth/client.json"
DOCUMENT_KEY = f"{HOST}/oauth/client.json"
DOCUMENT = json.dumps(
    {"client_id": DOCUMENT_URL, "client_name": "Example", "redirect_uris": ["https://apps.example.org/cb"]}
).encode()


def served(body: bytes = DOCUMENT, status: int = 200, **headers: str) -> httpx.Response:
    return httpx.Response(status, content=body, headers={"content-type": "application/json"} | headers)


def document_site(**routes: httpx.Response) -> Site:
    return Site(
        routes={DOCUMENT_KEY: served(**{"cache-control": "public, max-age=3600"})} | routes,
        dns={
            HOST: [PUBLIC_A],
            "elsewhere.example.net": [PUBLIC_B],
            "inside.example.org": ["10.0.0.7"],
            "loopback.example.org": ["127.0.0.1"],
        },
    )


async def test_a_document_is_read_from_the_vetted_address_with_its_cache_header() -> None:
    site = document_site()
    hop = await ClientDocumentFetch(site.pinned()).fetch(DOCUMENT_URL)
    assert (hop.status, hop.body, hop.cache_control) == (200, DOCUMENT, "public, max-age=3600")
    (sent,) = site.requests
    assert (sent.url.host, sent.headers["host"], sent.headers["accept"]) == (
        PUBLIC_A,
        HOST,
        "application/json",
    )


@pytest.mark.parametrize(
    "location", ["https://elsewhere.example.net/oauth/client.json", f"https://{HOST}/oauth/moved.json"]
)
async def test_a_redirect_is_refused_and_never_followed(location: str) -> None:
    site = document_site(**{DOCUMENT_KEY: redirect(location, status=301)})
    with pytest.raises(FetchRefused) as refused:
        await ClientDocumentFetch(site.pinned()).fetch(DOCUMENT_URL)
    assert refused.value.reason == "TOO_MANY_REDIRECTS"
    assert [request.headers["host"] for request in site.requests] == [HOST]


@pytest.mark.parametrize("host", ["inside.example.org", "loopback.example.org", "127.0.0.1", "10.1.2.3"])
async def test_a_private_or_loopback_address_is_never_asked(host: str) -> None:
    site = document_site()
    with pytest.raises(FetchRefused) as refused:
        await ClientDocumentFetch(site.pinned()).fetch(f"https://{host}/oauth/client.json")
    assert refused.value.reason == "PRIVATE_ADDRESS"
    assert site.requests == []


async def test_a_document_over_five_kilobytes_is_refused() -> None:
    padded = DOCUMENT[:-1] + b', "about": "' + b"x" * 5200 + b'"}'
    site = document_site(**{DOCUMENT_KEY: served(padded)})
    with pytest.raises(FetchRefused) as refused:
        await ClientDocumentFetch(site.pinned()).fetch(DOCUMENT_URL)
    assert refused.value.reason == "TOO_LARGE"


async def test_a_slow_document_is_refused_at_the_time_cap() -> None:
    site = document_site()

    async def slow(_: httpx.Request) -> httpx.Response:
        await asyncio.sleep(2)
        return served()

    site.routes[DOCUMENT_KEY] = slow
    with pytest.raises(FetchRefused) as refused:
        await ClientDocumentFetch(site.pinned(), timeout=0.05).fetch(DOCUMENT_URL)
    assert refused.value.reason == "TIME_LIMIT"


async def test_a_plain_http_address_and_a_missing_document_are_refused() -> None:
    site = document_site(**{DOCUMENT_KEY: served(b"gone", status=404)})
    with pytest.raises(FetchRefused) as plain:
        await ClientDocumentFetch(site.pinned()).fetch(f"http://{HOST}/oauth/client.json")
    assert plain.value.reason == "NOT_HTTPS"
    with pytest.raises(ExternalFailure) as missing:
        await ClientDocumentFetch(site.pinned()).fetch(DOCUMENT_URL)
    assert (missing.value.kind, missing.value.retryable) == ("not_found", False)


async def test_the_route_answers_the_document_with_its_cache_header_or_the_refusal() -> None:
    site = document_site()
    app = FastAPI()
    add_client_document_route(app, ClientDocumentFetch(site.pinned()))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://fetcher") as client:
        fetched = await client.post(CLIENT_DOCUMENT_FETCH_PATH, json={"url": DOCUMENT_URL})
        refused = await client.post(
            CLIENT_DOCUMENT_FETCH_PATH, json={"url": "https://inside.example.org/c.json"}
        )
    assert (fetched.status_code, fetched.content) == (200, DOCUMENT)
    assert fetched.headers["content-type"] == "application/json"
    assert fetched.headers[CLIENT_DOCUMENT_CACHE_HEADER] == "public, max-age=3600"
    assert refused.status_code == 403 and refused.json()["reason"] == "PRIVATE_ADDRESS"
