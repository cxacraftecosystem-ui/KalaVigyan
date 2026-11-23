from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import session_scope
from app.core.errors import ExternalFailure
from app.models import Source
from app.research.candidate_gates import CitedSource
from app.research.evidence import SourceDocument, canonical_url
from app.research.fetcher import FetchedPage, Fetcher, FetchRefused, FetchRequest
from app.research.knowledge_writes import FactProposal, ProposedSource
from app.research.retrieval import RESTRICTED_SENSITIVITY
from app.research.source_titles import first_heading, junk_title, usable_title
from app.sources.adapter import build_document
from app.sources.fetcher_client import FetcherClient
from app.sources.web.page import page_item

from .supplied_sources_gate import supplied_read
from .web_fetches import web_fetch_recorder

__all__ = [
    "PROPOSAL_ADAPTER",
    "ReadSource",
    "proposal_fetcher",
    "read_source",
    "read_sources",
    "stored_source",
]

PROPOSAL_ADAPTER = "proposal"
FULL_TEXT = "FULL_TEXT"
NO_TEXT = "the page has no readable text"


@dataclass(frozen=True)
class ReadSource:
    proposed: ProposedSource
    cited: CitedSource
    document: SourceDocument | None
    stored: Source | None
    supplied: bool = False


@dataclass(frozen=True)
class _Fetched:
    page: FetchedPage | None
    unread: str | None


@asynccontextmanager
async def proposal_fetcher() -> AsyncIterator[Fetcher]:
    async with httpx.AsyncClient() as client:
        yield FetcherClient(get_settings().fetcher_url, client, record=web_fetch_recorder(session_scope))


async def read_sources(
    session: AsyncSession, fetcher: Fetcher, proposal: FactProposal, *, proposer_id: uuid.UUID | None = None
) -> tuple[ReadSource, ...]:
    return tuple(
        [
            await read_source(session, fetcher, proposed, proposer_id=proposer_id)
            for proposed in proposal.sources
        ]
    )


async def stored_source(session: AsyncSession, url: str) -> Source | None:
    urls = sorted({url, canonical_url(url)})
    return await session.scalar(
        select(Source).where(Source.url.in_(urls)).order_by(Source.createdAt, Source.id).limit(1)
    )


async def read_source(
    session: AsyncSession, fetcher: Fetcher, proposed: ProposedSource, *, proposer_id: uuid.UUID | None = None
) -> ReadSource:
    stored = await stored_source(session, proposed.url)
    supplied = await supplied_read(session, proposed.url, proposer_id)
    fetched = _Fetched(page=None, unread=None) if supplied else await _fetched(fetcher, proposed.url)
    document = supplied.document if supplied else _document(proposed, fetched.page) if fetched.page else None
    unread = None if document is not None else (fetched.unread or NO_TEXT)
    cited = CitedSource(
        url=proposed.url,
        quotes=[quote.text for quote in proposed.quotes],
        text=document.text if document is not None else None,
        unread=unread,
        grade=_grade(stored, document),
        declared_licence=proposed.licence,
        stated_licence=fetched.page.metadata.licence if fetched.page is not None else None,
        restricted=stored is not None and stored.sensitivity == RESTRICTED_SENSITIVITY,
        supplied=supplied.note if supplied else None,
        published=_published(stored, document),
        untitled=document.item.title if document is not None and junk_title(document.item.title) else None,
    )
    return ReadSource(
        proposed=proposed, cited=cited, document=document, stored=stored, supplied=bool(supplied)
    )


async def _fetched(fetcher: Fetcher, url: str) -> _Fetched:
    try:
        return _Fetched(page=await fetcher.fetch(FetchRequest(url=url)), unread=None)
    except FetchRefused as refused:
        return _Fetched(page=None, unread=refused.message)
    except ExternalFailure as failure:
        if failure.retryable:
            raise
        return _Fetched(page=None, unread=str(failure))


def _document(proposed: ProposedSource, page: FetchedPage) -> SourceDocument | None:
    if not page.text.strip():
        return None
    item = page_item(PROPOSAL_ADAPTER, proposed.url, page)
    title = usable_title(page.metadata.title, proposed.title, first_heading(page.text))
    titled = item if title is None else item.model_copy(update={"title": title})
    licensed = titled if titled.licence else titled.model_copy(update={"licence": proposed.licence})
    return build_document(licensed, page.text, FULL_TEXT, truncated=page.truncated)


def _grade(stored: Source | None, document: SourceDocument | None) -> str | None:
    if stored is not None:
        return stored.reliability
    return document.item.trust if document is not None else None


def _published(stored: Source | None, document: SourceDocument | None) -> str | None:
    if document is not None and document.item.published:
        return document.item.published
    return f"{stored.year:04d}" if stored is not None and stored.year else None
