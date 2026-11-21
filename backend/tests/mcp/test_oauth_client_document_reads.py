import asyncio
from dataclasses import dataclass

import httpx
import pytest
from fastapi import FastAPI

from app.fetcher.client_documents import ClientDocumentFetch, add_client_document_route
from app.research.oauth_client_documents import MetadataClient
from app.research.oauth_rules import OAuthError
from app.services.oauth_client_documents import (
    HELD_DOCUMENTS_MAX,
    ClientDocuments,
    FetchedDocument,
    FetcherReader,
    fetched_document,
)

from ..fetcher.site import PUBLIC_A, PUBLIC_B, Site, redirect
from .client_documents import CLAUDE_DOCUMENT, CLAUDE_ID, CLAUDE_RETURN, document_bytes

CLAUDE_KEY = "claude.ai/oauth/mcp-oauth-client-metadata"
FETCHER = "http://fetcher.test"


@dataclass
class Clock:
    now: float = 1000.0

    def __call__(self) -> float:
        return self.now


def served(body: bytes, status: int = 200, **headers: str) -> httpx.Response:
    return httpx.Response(status, content=body, headers={"content-type": "application/json"} | headers)


def claude_site(answer: httpx.Response | None = None) -> Site:
    published = served(document_bytes(CLAUDE_DOCUMENT), **{"cache-control": "max-age=3600"})
    return Site(
        routes={CLAUDE_KEY: answer or published},
        dns={
            "claude.ai": [PUBLIC_A],
            "elsewhere.example.net": [PUBLIC_B],
            "inside.example.org": ["10.0.0.7"],
        },
    )


def documents(site: Site, clock: Clock | None = None, *, timeout: float = 5.0) -> ClientDocuments:
    fetcher = FastAPI()
    add_client_document_route(fetcher, ClientDocumentFetch(site.pinned(), timeout=timeout))
    reader = FetcherReader(FETCHER, httpx.ASGITransport(app=fetcher))
    return ClientDocuments(read=reader, clock=clock or Clock())


async def refusal(held: ClientDocuments, client_id: str = CLAUDE_ID) -> OAuthError:
    with pytest.raises(OAuthError) as refused:
        await held.client(client_id)
    return refused.value


async def test_a_published_identity_is_read_once_and_held_for_its_max_age() -> None:
    site, clock = claude_site(), Clock()
    held = documents(site, clock)
    expected = MetadataClient(client_id=CLAUDE_ID, name="Claude", redirect_uris=(CLAUDE_RETURN,))
    assert await held.client(CLAUDE_ID) == expected
    clock.now += 3599
    assert await held.client(CLAUDE_ID) == expected
    assert len(site.requests) == 1
    clock.now += 2
    assert await held.client(CLAUDE_ID) == expected
    assert len(site.requests) == 2


async def test_a_document_naming_another_client_is_refused_and_never_held() -> None:
    site = claude_site(served(document_bytes(CLAUDE_DOCUMENT, client_id="https://claude.ai/oauth/other")))
    held = documents(site)
    for _ in range(2):
        refused = await refusal(held)
        assert (refused.error, refused.status) == ("invalid_client", 400)
    assert len(site.requests) == 2


async def test_a_client_id_that_is_not_https_is_refused_before_anything_is_fetched() -> None:
    site = claude_site()
    refused = await refusal(documents(site), "http://claude.ai/oauth/mcp-oauth-client-metadata")
    assert (refused.error, refused.status) == ("invalid_client", 400)
    assert "https address" in refused.description
    assert (site.requests, site.lookups) == ([], [])


async def test_a_private_address_is_refused_as_an_invalid_client() -> None:
    site = claude_site()
    refused = await refusal(documents(site), "https://inside.example.org/oauth/client.json")
    assert (refused.error, refused.status) == ("invalid_client", 400)
    assert "10.0.0.7" in refused.description
    assert site.requests == []


async def test_an_oversize_document_and_a_redirect_elsewhere_are_refused_as_invalid_clients() -> None:
    oversize = served(document_bytes(CLAUDE_DOCUMENT, about="x" * 6000))
    moved = redirect("https://elsewhere.example.net/oauth/mcp-oauth-client-metadata", status=302)
    for answer, words in ((oversize, "bytes"), (moved, "redirect")):
        site = claude_site(answer)
        refused = await refusal(documents(site))
        assert (refused.error, refused.status) == ("invalid_client", 400)
        assert words in refused.description
        assert [request.headers["host"] for request in site.requests] == ["claude.ai"]


async def test_a_slow_document_or_a_failing_host_is_a_503_to_try_again() -> None:
    async def slow(_: httpx.Request) -> httpx.Response:
        await asyncio.sleep(2)
        return served(document_bytes(CLAUDE_DOCUMENT))

    site = claude_site()
    site.routes[CLAUDE_KEY] = slow
    refused = await refusal(documents(site, timeout=0.05))
    assert (refused.error, refused.status) == ("temporarily_unavailable", 503)
    failing = await refusal(documents(claude_site(served(b"busy", status=503))))
    assert (failing.error, failing.status) == ("temporarily_unavailable", 503)
    missing = await refusal(documents(claude_site(served(b"gone", status=404))))
    assert (missing.error, missing.status) == ("invalid_client", 400)


async def test_a_fetcher_that_cannot_be_reached_or_answers_off_contract_is_a_503() -> None:
    def unreachable(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    reader = FetcherReader(FETCHER, httpx.MockTransport(unreachable))
    refused = await refusal(ClientDocuments(read=reader, clock=Clock()))
    assert (refused.error, refused.status) == ("temporarily_unavailable", 503)
    with pytest.raises(OAuthError) as garbled:
        fetched_document(CLAUDE_ID, httpx.Response(403, content=b"<html>proxy</html>"))
    assert garbled.value.status == 503


async def test_at_most_the_bound_of_documents_is_held_and_the_oldest_leaves_first() -> None:
    reads: list[str] = []

    async def read(url: str) -> FetchedDocument:
        reads.append(url)
        body = document_bytes(CLAUDE_DOCUMENT, client_id=url)
        return FetchedDocument(body, "max-age=86400")

    held = ClientDocuments(read=read, clock=Clock())
    addresses = [f"https://apps.example.org/clients/{n}.json" for n in range(HELD_DOCUMENTS_MAX + 1)]
    for address in addresses:
        await held.client(address)
    assert len(held.held) == HELD_DOCUMENTS_MAX
    await held.client(addresses[-1])
    await held.client(addresses[0])
    assert reads == [*addresses, addresses[0]]
