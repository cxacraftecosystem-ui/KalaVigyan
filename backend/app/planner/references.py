from __future__ import annotations

import asyncio
import re
from collections.abc import Sequence
from dataclasses import dataclass

from app.research.evidence import SourceAdapter, SourceDocument
from app.research.evidence_pack import PackedEvidence
from app.sources.records import doi_of

from .failures import FailureLog
from .policy import DOCUMENT_TIMEOUT_SECONDS, LIVE_BUDGETS, REFERENCES_PER_DOCUMENT
from .reading import DocumentReader, with_abstract

__all__ = ["FOLLOW_STAGE", "CitedDoi", "FollowedReference", "cited_dois", "dois_in", "follow_references"]

FOLLOW_STAGE = "FOLLOW"
DOI_IN_TEXT = re.compile(r"(?<![\w.])10\.\d{4,9}/[^\s\"'<>]+")
DOI_TRAILING = ".,;:)]}"


@dataclass(frozen=True)
class CitedDoi:
    doi: str
    parent: PackedEvidence
    position: int


@dataclass(frozen=True)
class FollowedReference:
    entry: PackedEvidence
    document: SourceDocument


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
    budgets = LIVE_BUDGETS[mode]
    by_id = {entry.item.id: entry for entry in evidence}
    known = {entry.item.doi.lower() for entry in evidence if entry.item.doi}
    cited: list[CitedDoi] = []
    for document in documents:
        parent = by_id[document.item.id]
        budget = budgets.get(parent.item.tier)
        if budget is None or not budget.follows_references:
            continue
        fresh = [doi for doi in dois_in(document.text) if doi.lower() not in known][:REFERENCES_PER_DOCUMENT]
        known.update(doi.lower() for doi in fresh)
        cited.extend(CitedDoi(doi, parent, position) for position, doi in enumerate(fresh, start=1))
    return cited[:limit]


async def follow_references(
    cited: Sequence[CitedDoi], *, source: SourceAdapter, reader: DocumentReader, log: FailureLog
) -> list[FollowedReference]:
    followed = await asyncio.gather(*(_follow(lead, source=source, reader=reader, log=log) for lead in cited))
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
    entry = PackedEvidence(
        item=fetched.item,
        facet_indexes=lead.parent.facet_indexes,
        found_by=(source.name,),
        hits=1,
        best_rank=lead.position,
        followed_from=lead.parent.item.id,
    )
    opened = await reader.open_access_document(fetched.item)
    document = fetched if opened is None else with_abstract(opened, fetched)
    return FollowedReference(entry=entry, document=document)
