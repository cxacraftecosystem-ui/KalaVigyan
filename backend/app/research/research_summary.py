from __future__ import annotations

from collections.abc import Sequence

from pydantic import Field

from .base import ContractModel
from .crafts import CraftRef
from .evidence import SEARCH_QUERY_MAX_CHARS
from .vocabulary import AnswerMode, LiveTier

__all__ = [
    "SEARCHED_MAX_CHARS",
    "ResearchSummary",
    "SearchedQuery",
    "not_enough_evidence_message",
    "searched_note",
]

SEARCHED_MAX_CHARS = 2000


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
    for listed in range(len(summary.queries), 0, -1):
        note = " ".join(_searched(summary, listed))
        if len(note) <= SEARCHED_MAX_CHARS:
            return note
    return " ".join(_searched(summary, 0))


def _searched(summary: ResearchSummary, listed: int | None = None) -> list[str]:
    parts = [
        f"Searched {_count(summary.stored_claims, 'stored claim')} and "
        f"{_count(summary.stored_passages, 'stored source passage')}.",
    ]
    if summary.queries:
        parts.append(_live(summary.queries, len(summary.queries) if listed is None else listed))
    else:
        parts.append("No live research ran.")
    if summary.services:
        parts.append(f"Sources searched: {', '.join(summary.services)}.")
    parts.append(
        f"Found {_count(summary.evidence_found, 'item')}, read {_count(summary.documents_read, 'document')}"
        f" and recorded {_count(summary.failures, 'failed request')}."
    )
    return parts


def _live(queries: Sequence[SearchedQuery], listed: int) -> str:
    ran = f"Live research ran {_count(len(queries), 'query', 'queries')}"
    if listed == 0:
        return f"{ran}."
    shown = "; ".join(f'{query.tier} "{query.text}"' for query in queries[:listed])
    rest = len(queries) - listed
    return f"{ran}: {shown}; and {rest} more." if rest else f"{ran}: {shown}."


def _count(n: int, singular: str, plural: str | None = None) -> str:
    return f"{n} {singular if n == 1 else plural or singular + 's'}"
