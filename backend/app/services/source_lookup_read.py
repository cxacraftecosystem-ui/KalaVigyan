from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ExternalFailure, InvalidInput
from app.research.candidate_gates import quote_gate
from app.research.evidence import OpenAccessLocation, OpenAccessLocator
from app.research.knowledge_writes import ProposedQuote, ProposedSource
from app.research.licences import open_licence
from app.research.quotes import normalise_quote_lines

from .candidate_sources import ReadSource, read_source
from .source_lookup import open_copy
from .source_lookup_archive import archived_copy
from .source_lookup_models import QuoteCheck, SourceText
from .source_lookup_sources import LookupSources
from .source_lookup_text import LINE, PARAGRAPH, found_at, nearest_match, page_of, windows_around

__all__ = [
    "DOI_RESOLVER",
    "PAGE_SOURCE_TYPE",
    "Address",
    "TextView",
    "checked_quote",
    "gate_lines",
    "read_page",
    "source_address",
    "source_text",
]

DOI_RESOLVER = "https://doi.org/"
PAGE_SOURCE_TYPE = "WEB_PAGE"
ONE_ADDRESS = "give the source's url or its doi, one of them"


@dataclass(frozen=True)
class Address:
    url: str
    doi: str | None = None
    licence: str | None = None


@dataclass(frozen=True)
class TextView:
    around: str | None = None
    start: int = 1


async def source_address(locator: OpenAccessLocator | None, *, url: str | None, doi: str | None) -> Address:
    if url is not None:
        return Address(url=url)
    if doi is None:
        raise InvalidInput(ONE_ADDRESS)
    copy = open_copy(await _located(locator, doi))
    if copy is None:
        return Address(url=f"{DOI_RESOLVER}{doi}", doi=doi)
    return Address(url=copy.url, doi=doi, licence=copy.licence)


async def read_page(
    session: AsyncSession, sources: LookupSources, address: Address, quotes: Sequence[ProposedQuote] = ()
) -> ReadSource:
    if quotes:
        proposed = ProposedSource(
            url=address.url, title=address.url, licence=address.licence, quotes=list(quotes)
        )
    else:
        proposed = ProposedSource.model_construct(
            url=address.url, title=address.url, licence=address.licence, quotes=[]
        )
    return await read_source(session, sources.fetcher, proposed)


def gate_lines(read: ReadSource) -> list[str]:
    return normalise_quote_lines(read.cited.text) if read.cited.text is not None else []


async def source_text(
    session: AsyncSession, sources: LookupSources, address: Address, view: TextView
) -> SourceText:
    read = await read_page(session, sources, address)
    archived = await archived_copy(session, read.stored, address.url, sources.snapshots)
    licence = read.cited.stated_licence or read.cited.declared_licence
    head = SourceText(
        url=address.url,
        doi=address.doi,
        readable=read.document is not None,
        unread=read.cited.unread,
        licence=licence,
        open_licence=open_licence(licence),
        grade=read.cited.grade,
        held=read.stored is not None,
        restricted=read.cited.restricted,
        archived_url=archived,
    )
    return head if read.document is None else _with_text(head, read, view)


async def checked_quote(
    session: AsyncSession, sources: LookupSources, address: Address, quote: ProposedQuote
) -> QuoteCheck:
    read = await read_page(session, sources, address, [quote])
    outcome = quote_gate("", [read.cited])
    lines, unit = gate_lines(read), _unit(read)
    licence = read.cited.stated_licence or read.cited.declared_licence
    return QuoteCheck(
        url=address.url,
        doi=address.doi,
        quote=quote.text,
        locator=quote.locator,
        passed=outcome.passed,
        reasons=list(outcome.reasons),
        found_at=found_at(lines, unit, quote.text) if outcome.passed else [],
        nearest=None if outcome.passed else nearest_match(lines, unit, quote.text),
        grade=read.cited.grade,
        held=read.stored is not None,
        licence=licence,
        open_licence=open_licence(licence),
    )


def _with_text(head: SourceText, read: ReadSource, view: TextView) -> SourceText:
    document = read.document
    if document is None:
        return head
    lines, unit = gate_lines(read), _unit(read)
    if view.around:
        passages, found = windows_around(lines, unit, view.around)
        next_start = None
    else:
        (passages, next_start), found = page_of(lines, unit, view.start), 0
    item = document.item
    return head.model_copy(
        update={
            "title": item.title,
            "authors": list(item.authors),
            "published": item.published,
            "publisher": item.publisher,
            "truncated": document.truncated,
            "lines": len(lines),
            "around": view.around,
            "found": found,
            "passages": passages,
            "next_start": next_start,
        }
    )


def _unit(read: ReadSource) -> str:
    document = read.document
    return PARAGRAPH if document is None or document.item.source_type == PAGE_SOURCE_TYPE else LINE


async def _located(locator: OpenAccessLocator | None, doi: str) -> OpenAccessLocation | None:
    if locator is None:
        return None
    try:
        return await locator.locate(doi)
    except ExternalFailure, InvalidInput:
        return None
