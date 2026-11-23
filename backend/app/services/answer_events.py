from __future__ import annotations

import logging
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from app.core.errors import InvalidInput
from app.models import Source
from app.research.composition import ComposedAnswer
from app.research.planning import OPEN_QUESTION_LEVEL
from app.research.vocabulary import weakest_level

from .interface_words import ENGLISH_WORDS, InterfaceWords
from .knowledge_view import ClaimView, source_ref
from .write_back_plan import composed_sentences

__all__ = [
    "FOLLOW_UP_WORDS_KEY",
    "OPEN_HEADING",
    "OPEN_SECTION_ID",
    "STORED_ANSWER_LIMIT",
    "STORED_FOLLOW_UP_QUESTIONS",
    "STORED_OPEN_QUESTION_LIMIT",
    "CitedClaims",
    "StreamEvent",
    "cited_claims",
    "composed_answer_events",
    "joined_claims",
    "stored_follow_ups",
]

logger = logging.getLogger(__name__)

STORED_ANSWER_LIMIT = 14
STORED_OPEN_QUESTION_LIMIT = 4
STORED_FOLLOW_UPS = 3
OPEN_SECTION_ID = "open"
OPEN_HEADING = "Open questions"
FOLLOW_UP_WORDS_KEY = "stream.followUp"
STORED_FOLLOW_UP_QUESTIONS: Mapping[str, str] = MappingProxyType(
    {
        "Materials and tools": "Which materials does {craft} depend on, and why?",
        "Process": "What happens at each step of {craft}?",
        "How it works": "What is the chemistry or physics behind {craft}?",
        "Place and climate": "How do local water, soil and climate shape {craft}?",
        "The artisan's judgement": "How do artisans judge when a step of {craft} is done?",
        "History": "Where did {craft} come from?",
    }
)

StreamEvent = tuple[str, dict[str, Any]]


@dataclass(frozen=True)
class CitedClaims:
    views: Mapping[uuid.UUID, ClaimView] = field(default_factory=dict)
    sources: Mapping[str, dict[str, Any]] = field(default_factory=dict)


def cited_claims(views: Sequence[ClaimView], sources: Mapping[uuid.UUID, Source]) -> CitedClaims:
    return CitedClaims(
        views={view.id: view for view in views},
        sources={str(source_id): source_ref(source) for source_id, source in sources.items()},
    )


def joined_claims(*found: CitedClaims) -> CitedClaims:
    views = {claim_id: view for cited in found for claim_id, view in cited.views.items()}
    sources = {source_id: ref for cited in found for source_id, ref in cited.sources.items()}
    return CitedClaims(views=views, sources=sources)


class _Answer:
    def __init__(self, sources: Mapping[str, dict[str, Any]]) -> None:
        self._sources = sources
        self._sent: set[str] = set()
        self._sections: dict[str, str] = {}
        self._counts: dict[str, int] = {}
        self.events: list[StreamEvent] = []

    @property
    def headings(self) -> list[str]:
        return list(self._sections)

    def add(self, heading: str | None, text: str, level: str, citations: list[dict[str, Any]]) -> None:
        for cite in citations:
            self._source(cite["sourceId"])
        section_id = OPEN_SECTION_ID if heading is None else self._section(heading)
        self._counts[section_id] = self._counts.get(section_id, 0) + 1
        sentence = {
            "id": f"{section_id}.{self._counts[section_id]}",
            "text": text,
            "level": level,
            "citations": citations,
        }
        if heading is None:
            self.events.append(
                (
                    "open_question",
                    {"sectionId": OPEN_SECTION_ID, "heading": OPEN_HEADING, "sentence": sentence},
                )
            )
        else:
            self.events.append(("sentence", {"sectionId": section_id, "sentence": sentence}))

    def _source(self, source_id: str) -> None:
        if source_id in self._sent:
            return
        self._sent.add(source_id)
        self.events.append(("source", self._sources[source_id]))

    def _section(self, heading: str) -> str:
        if heading not in self._sections:
            self._sections[heading] = f"s{len(self._sections) + 1}"
            self.events.append(("section", {"id": self._sections[heading], "heading": heading}))
        return self._sections[heading]


def stored_follow_ups(
    craft_name: str, headings: list[str], words: InterfaceWords = ENGLISH_WORDS
) -> list[str]:
    asked = [prompt for heading, prompt in STORED_FOLLOW_UP_QUESTIONS.items() if heading not in headings]
    return [words.said(FOLLOW_UP_WORDS_KEY, prompt, craft=craft_name) for prompt in asked[:STORED_FOLLOW_UPS]]


def composed_answer_events(
    composed: ComposedAnswer, claims_of: Sequence[Sequence[uuid.UUID]], cited: CitedClaims
) -> list[StreamEvent]:
    answer = _Answer(cited.sources)
    sentences = list(composed_sentences(composed))
    if len(sentences) != len(claims_of):
        raise InvalidInput(f"{len(claims_of)} claim lists were given for {len(sentences)} sentences")
    for (sentence, heading), claim_ids in zip(sentences, claims_of, strict=True):
        views = [cited.views[claim_id] for claim_id in claim_ids if claim_id in cited.views]
        citations = _distinct_citations(views)
        if not citations:
            logger.warning("dropped a composed sentence with no stored citation")
            continue
        level = weakest_level(view.level for view in views)
        answer.add(None if level == OPEN_QUESTION_LEVEL else heading, sentence.text, level, citations)
    if not answer.events:
        return []
    return [*answer.events, ("follow_ups", {"items": list(composed.follow_ups)})]


def _distinct_citations(views: Sequence[ClaimView]) -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    for view in views:
        for cite in view.citations:
            seen.setdefault(cite["id"], cite)
    return list(seen.values())
