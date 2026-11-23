from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.research.crafts import CraftRef
from app.research.research_summary import ResearchSummary, not_enough_evidence_message
from app.retrieval.text import query_terms

from .answer_events import CitedClaims
from .answer_translation import AnswerTranslation, english_rendering, needs_english_rendering
from .explainer_events import ExplainerStream
from .section_enrichment import EnrichmentTools
from .stored_explainer import stream_stored_answer

__all__ = [
    "STORED_ONLY_MODE",
    "StoredOnlyTools",
    "StoredSearch",
    "stored_only_answer",
    "stored_search_question",
]

STORED_ONLY_MODE = "VERIFIED"

StoredSearch = Callable[[str, str, str], Awaitable[CitedClaims]]


@dataclass(frozen=True)
class StoredOnlyTools:
    stored: StoredSearch
    translation: AnswerTranslation
    enrichment: EnrichmentTools


async def stored_only_answer(
    question: str, craft: CraftRef, *, stream: ExplainerStream, tools: StoredOnlyTools
) -> None:
    await stream.status("SEARCHING_STORED")
    words = await stored_search_question(question, tools.translation)
    if words is not None:
        cited = await tools.stored(craft.slug, words, STORED_ONLY_MODE)
        marking = await tools.enrichment.for_answer(craft)
        if await stream_stored_answer(
            stream, craft.name, cited, translation=tools.translation, enrichment=marking
        ):
            return
    await stream.emit("not_enough_evidence", {"message": not_enough_evidence_message(_nothing_found(craft))})


async def stored_search_question(question: str, translation: AnswerTranslation) -> str | None:
    english = (
        await english_rendering(question, translation) if needs_english_rendering(question) else question
    )
    return english if english is not None and query_terms(english) else None


def _nothing_found(craft: CraftRef) -> ResearchSummary:
    return ResearchSummary(
        craft=craft,
        mode=STORED_ONLY_MODE,
        stored_claims=0,
        stored_passages=0,
        evidence_found=0,
        documents_read=0,
        failures=0,
    )
