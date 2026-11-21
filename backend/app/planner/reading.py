from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from itertools import zip_longest
from types import MappingProxyType

from app.research.evidence import EvidenceItem, OpenAccessLocator, SourceAdapter, SourceDocument
from app.research.evidence_pack import PackedEvidence
from app.research.fetcher import Fetcher, FetchRequest
from app.sources.adapter import build_document
from app.sources.fetcher_client import FETCHER_SERVICE

from .failures import FailureLog
from .policy import DOCUMENT_TIMEOUT_SECONDS, LIVE_BUDGETS, READ_ATTEMPT_FACTOR, READ_CONCURRENCY

__all__ = [
    "FETCH_STAGE",
    "LOCATE_STAGE",
    "MANUSCRIPT_VERSIONS",
    "DocumentReader",
    "LiveSources",
    "copy_read",
    "reading_order",
    "with_abstract",
]

FETCH_STAGE = "FETCH"
LOCATE_STAGE = "LOCATE"
TITLE_MAX_CHARS = 1000
DOI_KEY = "doi"
VERSION_KEY = "open_access_version"
MANUSCRIPT_VERSIONS: Mapping[str, str] = MappingProxyType(
    {
        "submittedVersion": "submitted manuscript, before peer review",
        "acceptedVersion": "author's accepted manuscript",
    }
)


@dataclass(frozen=True)
class LiveSources:
    searchers: tuple[SourceAdapter, ...]
    fetcher: Fetcher | None = None
    locator: OpenAccessLocator | None = None
    doi_source: SourceAdapter | None = None

    def __post_init__(self) -> None:
        names = [searcher.name for searcher in self.searchers]
        if len(set(names)) != len(names):
            raise ValueError(f"live searchers have distinct names, not {names}")


def reading_order(
    evidence: Sequence[PackedEvidence], facet_count: int, seat_kinds: Sequence[Sequence[str]] = ()
) -> list[PackedEvidence]:
    chosen: set[str] = set()
    facets = [_first(evidence, chosen, lambda e, i=i: i in e.facet_indexes) for i in range(facet_count)]
    seats = [_preferred(evidence, chosen, kinds) for kinds in seat_kinds]
    firsts = [entry for pair in zip_longest(facets, seats) for entry in pair if entry is not None]
    return [*firsts, *(entry for entry in evidence if entry.item.id not in chosen)]


def _preferred(
    evidence: Sequence[PackedEvidence], chosen: set[str], kinds: Sequence[str]
) -> PackedEvidence | None:
    for kind in kinds:
        found = _first(evidence, chosen, lambda e, kind=kind: e.item.source_type == kind)
        if found is not None:
            return found
    return None


def _first(
    evidence: Sequence[PackedEvidence], chosen: set[str], wanted: Callable[[PackedEvidence], bool]
) -> PackedEvidence | None:
    found = next((entry for entry in evidence if entry.item.id not in chosen and wanted(entry)), None)
    if found is not None:
        chosen.add(found.item.id)
    return found


class DocumentReader:
    def __init__(
        self,
        sources: LiveSources,
        *,
        mode: str,
        log: FailureLog,
        on_read: Callable[[SourceDocument], Awaitable[None]] | None = None,
    ) -> None:
        self._sources = sources
        self._searchers = {searcher.name: searcher for searcher in sources.searchers}
        self._budgets = LIVE_BUDGETS[mode]
        self._log = log
        self._gate = asyncio.Semaphore(READ_CONCURRENCY)
        self._on_read = on_read

    async def read_best(self, ordered: Sequence[PackedEvidence], *, limit: int) -> list[SourceDocument]:
        documents: list[SourceDocument] = []
        attempts_left = limit * READ_ATTEMPT_FACTOR
        position = 0
        while len(documents) < limit and position < len(ordered) and attempts_left > 0:
            batch = ordered[position : position + min(limit - len(documents), attempts_left)]
            position += len(batch)
            attempts_left -= len(batch)
            read = await asyncio.gather(*(self.read(entry) for entry in batch))
            documents.extend(document for document in read if document is not None)
        return documents[:limit]

    async def read(self, entry: PackedEvidence) -> SourceDocument | None:
        document = await self._opened(entry)
        if document is not None and self._on_read is not None:
            await self._on_read(document)
        return document

    async def _opened(self, entry: PackedEvidence) -> SourceDocument | None:
        async with self._gate:
            if not self._opens(entry.item):
                return await self._fetched(entry)
            opened, abstract = await asyncio.gather(
                self.open_access_document(entry.item), self._fetched(entry)
            )
            return abstract if opened is None else with_abstract(opened, abstract)

    async def _fetched(self, entry: PackedEvidence) -> SourceDocument | None:
        searcher = self._searchers[entry.found_by[0]]
        return await self._log.guarded(
            asyncio.wait_for(searcher.fetch(entry.item.id), DOCUMENT_TIMEOUT_SECONDS),
            stage=FETCH_STAGE,
            service=searcher.name,
            target=entry.item.id,
        )

    async def open_access_document(self, item: EvidenceItem) -> SourceDocument | None:
        locator, fetcher = self._sources.locator, self._sources.fetcher
        if locator is None or fetcher is None or not self._opens(item):
            return None
        location = await self._log.guarded(
            asyncio.wait_for(locator.locate(item.doi or ""), DOCUMENT_TIMEOUT_SECONDS),
            stage=LOCATE_STAGE,
            service=locator.name,
            target=item.doi or item.id,
        )
        if location is None or not location.is_open:
            return None
        url = location.pdf_url or location.landing_url
        if url is None:
            return None
        page = await self._log.guarded(
            asyncio.wait_for(fetcher.fetch(FetchRequest(url=url)), DOCUMENT_TIMEOUT_SECONDS),
            stage=FETCH_STAGE,
            service=FETCHER_SERVICE,
            target=url,
        )
        if page is None or not page.text.strip():
            return None
        opened = item.model_copy(
            update={
                "licence": location.licence,
                "external_ids": {
                    **item.external_ids,
                    "open_access_url": page.final_url,
                    "sha256": page.sha256,
                },
            }
        )
        copy = copy_read(opened, location.version, page.final_url)
        return build_document(copy, page.text, "FULL_TEXT", truncated=page.truncated)

    def _opens(self, item: EvidenceItem) -> bool:
        if self._sources.locator is None or self._sources.fetcher is None:
            return False
        budget = self._budgets.get(item.tier)
        return bool(budget and budget.open_access and item.doi and not item.quotes)


def copy_read(item: EvidenceItem, version: str | None, url: str) -> EvidenceItem:
    label = MANUSCRIPT_VERSIONS.get(version or "")
    if label is None or item.doi is None:
        return item
    return item.model_copy(
        update={
            "title": f"{item.title} ({label})"[:TITLE_MAX_CHARS],
            "url": url,
            "doi": None,
            "external_ids": {**item.external_ids, DOI_KEY: item.doi, VERSION_KEY: version or ""},
        }
    )


def with_abstract(opened: SourceDocument, abstract: SourceDocument | None) -> SourceDocument:
    manuscript = opened.item.external_ids.get(VERSION_KEY) in MANUSCRIPT_VERSIONS
    if abstract is None or manuscript or abstract.text in opened.text:
        return opened
    return build_document(
        opened.item, f"{abstract.text}\n\n{opened.text}", "FULL_TEXT", truncated=opened.truncated
    )
