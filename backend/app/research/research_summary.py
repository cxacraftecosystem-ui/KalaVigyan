from __future__ import annotations

from pydantic import Field

from .base import ContractModel
from .crafts import CraftRef
from .evidence import SEARCH_QUERY_MAX_CHARS
from .vocabulary import AnswerMode, LiveTier

__all__ = ["ResearchSummary", "SearchedQuery", "not_enough_evidence_message", "searched_note"]


class SearchedQuery(ContractModel):
    tier: LiveTier
    text: str = Field(min_length=2, max_length=SEARCH_QUERY_MAX_CHARS)


class ResearchSummary(ContractModel):
    craft: CraftRef | None
    mode: AnswerMode
    stored_claims: int = Field(ge=0)
    stored_passages: int = Field(ge=0)
    queries: tuple[SearchedQuery, ...] = ()
    services: tuple[str, ...] = ()
    evidence_found: int = Field(ge=0)
    documents_read: int = Field(ge=0)
    failures: int = Field(ge=0)


def not_enough_evidence_message(summary: ResearchSummary) -> str:
    about = f" about {summary.craft.name}" if summary.craft else ""
    return " ".join([f"There is not enough cited evidence to answer this{about} yet.", *_searched(summary)])


def searched_note(summary: ResearchSummary) -> str:
    return " ".join(_searched(summary))


def _searched(summary: ResearchSummary) -> list[str]:
    parts = [
        f"Searched {_count(summary.stored_claims, 'stored claim')} and "
        f"{_count(summary.stored_passages, 'stored source passage')}.",
    ]
    if summary.queries:
        listed = "; ".join(f'{query.tier} "{query.text}"' for query in summary.queries)
        parts.append(f"Live research ran {_count(len(summary.queries), 'query', 'queries')}: {listed}.")
    else:
        parts.append("No live research ran.")
    if summary.services:
        parts.append(f"Sources searched: {', '.join(summary.services)}.")
    parts.append(
        f"Found {_count(summary.evidence_found, 'item')}, read {_count(summary.documents_read, 'document')}"
        f" and recorded {_count(summary.failures, 'failed request')}."
    )
    return parts


def _count(n: int, singular: str, plural: str | None = None) -> str:
    return f"{n} {singular if n == 1 else plural or singular + 's'}"
