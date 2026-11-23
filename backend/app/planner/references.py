from __future__ import annotations

import asyncio
import re
from collections.abc import Sequence
from dataclasses import dataclass

from app.research.evidence import ReferenceLister, SourceAdapter, SourceDocument
from app.research.evidence_pack import PackedEvidence
from app.sources.records import doi_of

from .failures import FailureLog
from .policy import DOCUMENT_TIMEOUT_SECONDS, LIVE_BUDGETS, REFERENCES_PER_DOCUMENT
from .reading import DocumentReader, with_abstract

__all__ = [
    "FOLLOW_STAGE",
    "CitedDoi",
    "CitedList",
    "FollowedReference",
    "Following",
    "cited_dois",
    "cited_lists",
    "dois_in",
    "follow_cited",
    "follow_reference_lists",
    "follow_references",
]

FOLLOW_STAGE = "FOLLOW"
DOI_IN_TEXT = re.compile(r"(?<![\w.])10\.\d{4,9}/[^\s\"'<>]+")
DOI_TRAILING = ".,;:)]}"


@dataclass(frozen=True)
class CitedDoi:
    doi: str
    parent: PackedEvidence
    position: int


@dataclass(frozen=True)
class CitedList:
    parent: PackedEvidence
    first_position: int
    k: int


@dataclass(frozen=True)
class FollowedReference:
    entry: PackedEvidence
    document: SourceDocument


@dataclass(frozen=True)
class Following:
    doi_source: SourceAdapter
    list_source: ReferenceLister | None
    reader: DocumentReader
    log: FailureLog


def dois_in(text: str) -> list[str]:
    found: dict[str, str] = {}
    for match in DOI_IN_TEXT.finditer(text):
        doi = doi_of(match.group(0).rstrip(DOI_TRAILING))
        if doi is not None:
            found.setdefault(doi.lower(), doi)
    return list(found.values())


def cited_dois(
    evidence: Sequence[PackedEvidence], documents: Sequence[SourceDocument], *, mode: str, limit: int
) -> list[CitedDoi]:
    by_id = {entry.item.id: entry for entry in evidence}
    known = {entry.item.doi.lower() for entry in evidence if entry.item.doi}
    cited: list[CitedDoi] = []
    for document in _following(documents, mode):
        parent = by_id[document.item.id]
        fresh = [doi for doi in dois_in(document.text) if doi.lower() not in known][:REFERENCES_PER_DOCUMENT]
        known.update(doi.lower() for doi in fresh)
        cited.extend(CitedDoi(doi, parent, position) for position, doi in enumerate(fresh, start=1))
    return cited[:limit]


def cited_lists(
    evidence: Sequence[PackedEvidence],
    listed: Sequence[SourceDocument],
    cited: Sequence[CitedDoi],
    *,
    limit: int,
) -> list[CitedList]:
    by_id = {entry.item.id: entry for entry in evidence}
    room = limit - len(cited)
    lists: list[CitedList] = []
    for document in listed:
        taken = sum(1 for lead in cited if lead.parent.item.id == document.item.id)
        k = min(REFERENCES_PER_DOCUMENT - taken, room)
        if k < 1:
            continue
        lists.append(CitedList(by_id[document.item.id], taken + 1, k))
        room -= k
    return lists


async def follow_cited(
    evidence: Sequence[PackedEvidence],
    documents: Sequence[SourceDocument],
    *,
    mode: str,
    limit: int,
    following: Following,
) -> list[FollowedReference]:
    reader, log, lister = following.reader, following.log, following.list_source
    cited = cited_dois(evidence, documents, mode=mode, limit=limit)
    listed = [document for document in _following(documents, mode) if lister and lister.lists(document.item)]
    lists = cited_lists(evidence, listed, cited, limit=limit)
    by_doi, by_list = await asyncio.gather(
        follow_references(cited, source=following.doi_source, reader=reader, log=log),
        follow_reference_lists(lists, source=lister, reader=reader, log=log),
    )
    return _once([*by_doi, *by_list])


async def follow_references(
    cited: Sequence[CitedDoi], *, source: SourceAdapter, reader: DocumentReader, log: FailureLog
) -> list[FollowedReference]:
    followed = await asyncio.gather(*(_follow(lead, source=source, reader=reader, log=log) for lead in cited))
    return _once(followed)


async def follow_reference_lists(
    lists: Sequence[CitedList], *, source: ReferenceLister | None, reader: DocumentReader, log: FailureLog
) -> list[FollowedReference]:
    if source is None or not lists:
        return []
    found = await asyncio.gather(*(_listed(lead, source=source, reader=reader, log=log) for lead in lists))
    return _once([reference for references in found for reference in references])


def _following(documents: Sequence[SourceDocument], mode: str) -> list[SourceDocument]:
    budgets = LIVE_BUDGETS[mode]
    return [
        document
        for document in documents
        if (budget := budgets.get(document.item.tier)) is not None and budget.follows_references
    ]


def _once(followed: Sequence[FollowedReference | None]) -> list[FollowedReference]:
    kept: list[FollowedReference] = []
    keys: set[str] = set()
    for reference in followed:
        if reference is not None and reference.entry.item.source_key not in keys:
            keys.add(reference.entry.item.source_key)
            kept.append(reference)
    return kept


async def _follow(
    lead: CitedDoi, *, source: SourceAdapter, reader: DocumentReader, log: FailureLog
) -> FollowedReference | None:
    fetched = await log.guarded(
        asyncio.wait_for(source.fetch(f"{source.name}:{lead.doi}"), DOCUMENT_TIMEOUT_SECONDS),
        stage=FOLLOW_STAGE,
        service=source.name,
        target=lead.doi,
    )
    if fetched is None:
        return None
    return await _followed(fetched, lead.parent, (source.name, lead.position), reader)


async def _listed(
    lead: CitedList, *, source: ReferenceLister, reader: DocumentReader, log: FailureLog
) -> list[FollowedReference]:
    listed = await log.guarded(
        asyncio.wait_for(source.references(lead.parent.item, lead.k), DOCUMENT_TIMEOUT_SECONDS),
        stage=FOLLOW_STAGE,
        service=source.name,
        target=lead.parent.item.id,
    )
    documents = (listed or [])[: lead.k]
    found = (
        _followed(document, lead.parent, (source.name, lead.first_position + offset), reader)
        for offset, document in enumerate(documents)
    )
    return list(await asyncio.gather(*found))


async def _followed(
    fetched: SourceDocument, parent: PackedEvidence, found: tuple[str, int], reader: DocumentReader
) -> FollowedReference:
    name, position = found
    entry = PackedEvidence(
        item=fetched.item,
        facet_indexes=parent.facet_indexes,
        found_by=(name,),
        hits=1,
        best_rank=position,
        followed_from=parent.item.id,
    )
    opened = await reader.open_access_document(fetched.item)
    document = fetched if opened is None else with_abstract(opened, fetched)
    return FollowedReference(entry=entry, document=document)
