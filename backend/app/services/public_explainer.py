from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.research.citations import Citation
from app.research.explainer import Explainer, explainer_blocks
from app.research.explainer_versions import ExplainerVersionDocument
from app.research.quotes import quote_key
from app.research.retrieval import chunk_acls_for

from . import knowledge_view
from .field_voices_readback import Withdrawn, without_withdrawn
from .visible_claims import stored_uuids

__all__ = [
    "PUBLIC_READING_ACLS",
    "CitationKey",
    "ClosedCitations",
    "citation_key",
    "closed_citations",
    "public_explainer",
    "public_version",
]

PUBLIC_READING_ACLS: tuple[str, ...] = chunk_acls_for(None)

type CitationKey = tuple[str, str, str | None]


@dataclass(frozen=True)
class ClosedCitations(Withdrawn):
    closed: frozenset[CitationKey] = frozenset()

    def __bool__(self) -> bool:
        return bool(self.closed) or super().__bool__()

    def out(self, citation: Citation) -> bool:
        return citation_key(citation) in self.closed or super().out(citation)


async def public_version(
    session: AsyncSession, document: ExplainerVersionDocument
) -> ExplainerVersionDocument | None:
    shown = await public_explainer(session, document.explainer)
    return None if shown is None else document.model_copy(update={"explainer": shown})


async def public_explainer(session: AsyncSession, explainer: Explainer) -> Explainer | None:
    return without_withdrawn(explainer, await closed_citations(session, explainer))


async def closed_citations(session: AsyncSession, explainer: Explainer) -> ClosedCitations:
    cited = {
        citation_key(citation) for block in explainer_blocks(explainer) for citation in block.citations()
    }
    claims = stored_uuids(dict.fromkeys(claim for claim, _source, _quote in cited))
    views, _sources = await knowledge_view.claims_by_id(session, claims, acls=PUBLIC_READING_ACLS)
    readable = {
        key
        for view in views.values()
        for cite in view.citations
        for key in _readable_keys(str(view.id), cite)
    }
    return ClosedCitations(closed=frozenset(cited - readable))


def citation_key(citation: Citation) -> CitationKey:
    return (citation.claim_id, citation.source_id, _folded(citation.quote))


def _readable_keys(claim_id: str, cite: Mapping[str, Any]) -> Iterator[CitationKey]:
    source_id = str(cite["sourceId"])
    yield (claim_id, source_id, None)
    if cite.get("quote"):
        yield (claim_id, source_id, _folded(cite["quote"]))


def _folded(quote: str | None) -> str | None:
    return quote_key(quote) if quote else None
