from __future__ import annotations

from collections.abc import Awaitable, Callable

from app.research.composition import ResearchSummary, not_enough_evidence_message
from app.research.crafts import CraftRef
from app.retrieval.text import query_terms

from .answer_events import CitedClaims
from .answer_translation import AnswerTranslation, english_rendering, needs_english_rendering
from .explainer_events import ExplainerStream
from .stored_explainer import stream_stored_answer

__all__ = ["STORED_ONLY_MODE", "StoredSearch", "stored_only_answer", "stored_search_question"]

STORED_ONLY_MODE = "VERIFIED"

StoredSearch = Callable[[str, str, str], Awaitable[CitedClaims]]


async def stored_only_answer(
    question: str,
    craft: CraftRef,
    *,
    stored: StoredSearch,
    stream: ExplainerStream,
    translation: AnswerTranslation,
) -> None:
    await stream.status("SEARCHING_STORED")
    words = await stored_search_question(question, translation)
    if words is not None:
        cited = await stored(craft.slug, words, STORED_ONLY_MODE)
        if await stream_stored_answer(stream, craft.name, cited, translation=translation):
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
