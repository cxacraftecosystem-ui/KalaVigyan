from __future__ import annotations

import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

import httpx
from pydantic import ValidationError

from app.core.config import get_settings
from app.research.fetcher import (
    FETCHER_FAILURE_STATUS,
    FETCHER_REFUSED_STATUS,
    FetchFailureBody,
    FetchRefusalBody,
)
from app.research.oauth_client_documents import (
    CLIENT_DOCUMENT_CACHE_HEADER,
    CLIENT_DOCUMENT_FETCH_PATH,
    CLIENT_DOCUMENT_TIMEOUT_SECONDS,
    ClientDocumentRequest,
    MetadataClient,
    cache_seconds,
    client_id_problem,
    metadata_client,
)
from app.research.oauth_rules import INVALID_CLIENT, TEMPORARILY_UNAVAILABLE, OAuthError

__all__ = [
    "CLIENT_DOCUMENTS",
    "HELD_DOCUMENTS_MAX",
    "ClientDocuments",
    "DocumentReader",
    "FetchedDocument",
    "FetcherReader",
    "client_document",
    "fetched_document",
]

HELD_DOCUMENTS_MAX = 256
FETCHER_MARGIN_SECONDS = 2.0
TRANSIENT_REFUSALS = frozenset({"TIME_LIMIT"})
REFUSED_ID = "This app's client_id is refused: {why}."
UNREAD = "KalaVigyan could not use the app's published identity at {url}: {why}."
UNAVAILABLE = "KalaVigyan could not read the app's published identity just now. Try again from the app."


@dataclass(frozen=True)
class FetchedDocument:
    body: bytes
    cache_control: str | None = None


DocumentReader = Callable[[str], Awaitable[FetchedDocument]]
Clock = Callable[[], float]


@dataclass(frozen=True)
class FetcherReader:
    base_url: str | None = None
    transport: httpx.AsyncBaseTransport | None = None

    async def __call__(self, url: str) -> FetchedDocument:
        endpoint = (self.base_url or get_settings().fetcher_url).rstrip("/") + CLIENT_DOCUMENT_FETCH_PATH
        sent = ClientDocumentRequest(url=url).model_dump(mode="json")
        try:
            async with httpx.AsyncClient(transport=self.transport) as client:
                response = await client.post(
                    endpoint, json=sent, timeout=CLIENT_DOCUMENT_TIMEOUT_SECONDS + FETCHER_MARGIN_SECONDS
                )
        except httpx.HTTPError:
            raise _unavailable() from None
        return fetched_document(url, response)


def fetched_document(url: str, response: httpx.Response) -> FetchedDocument:
    try:
        if response.status_code == FETCHER_REFUSED_STATUS:
            refusal = FetchRefusalBody.model_validate_json(response.content)
            if refusal.reason in TRANSIENT_REFUSALS:
                raise _unavailable()
            raise _unread(url, refusal.detail or refusal.reason)
        if response.status_code == FETCHER_FAILURE_STATUS:
            failure = FetchFailureBody.model_validate_json(response.content)
            if failure.retryable:
                raise _unavailable()
            raise _unread(url, failure.message)
    except ValidationError:
        raise _unavailable() from None
    if response.status_code != 200:
        raise _unavailable()
    return FetchedDocument(response.content, response.headers.get(CLIENT_DOCUMENT_CACHE_HEADER))


@dataclass
class ClientDocuments:
    read: DocumentReader = field(default_factory=FetcherReader)
    clock: Clock = time.monotonic
    held: OrderedDict[str, tuple[float, MetadataClient]] = field(default_factory=OrderedDict)

    async def client(self, client_id: str) -> MetadataClient:
        problem = client_id_problem(client_id)
        if problem is not None:
            raise OAuthError(INVALID_CLIENT, REFUSED_ID.format(why=problem))
        kept = self.held.get(client_id)
        if kept is not None and kept[0] > self.clock():
            self.held.move_to_end(client_id)
            return kept[1]
        fetched = await self.read(client_id)
        made = metadata_client(client_id, fetched.body)
        self._hold(made, self.clock() + cache_seconds(fetched.cache_control))
        return made

    def _hold(self, made: MetadataClient, until: float) -> None:
        self.held[made.client_id] = (until, made)
        self.held.move_to_end(made.client_id)
        while len(self.held) > HELD_DOCUMENTS_MAX:
            self.held.popitem(last=False)


CLIENT_DOCUMENTS = ClientDocuments()


async def client_document(client_id: str) -> MetadataClient:
    return await CLIENT_DOCUMENTS.client(client_id)


def _unread(url: str, why: str) -> OAuthError:
    return OAuthError(INVALID_CLIENT, UNREAD.format(url=url, why=why.rstrip(".")))


def _unavailable() -> OAuthError:
    return OAuthError(TEMPORARILY_UNAVAILABLE, UNAVAILABLE, status=503)
