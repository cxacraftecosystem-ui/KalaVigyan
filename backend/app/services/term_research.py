from __future__ import annotations

import logging
import re
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

from app.composer.term_summary import TermBrief, summarise_term
from app.core.errors import AppError, ExternalFailure, InvalidInput
from app.models.knowledge import QUOTE_MAX_CHARS
from app.research.composition import (
    SENTENCE_MAX_CHARS,
    ComposeCandidate,
    ComposedSentence,
    QuotedSpan,
    sentence_violations,
)
from app.research.evidence import SEARCH_QUERY_MAX_CHARS, EvidenceItem, SearchQuery, SourceDocument
from app.research.quotes import trivial_quote
from app.research.structured import StructuredModel
from app.research.terms import TERM_SUMMARY_MAX_SENTENCES

__all__ = [
    "WEB_HITS",
    "WEB_READS",
    "WIKIPEDIA_HITS",
    "GlossaryTerm",
    "LiveTermResearch",
    "ResearchedSummary",
    "TermConceptRef",
    "best_named",
    "lead_sentences",
    "names_the_term",
    "research_query",
]

logger = logging.getLogger(__name__)

WIKIPEDIA_HITS = 3
WEB_HITS = 5
WEB_READS = 2
LEAD_LEVEL = "PROVISIONAL"
SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(“‘])")
GLOSS_ITEMS = re.compile(r"\s*[,/;]\s*")
TITLE_WORD = re.compile(r"[^\W_]+")

ResearchBasis = Literal["WIKIPEDIA", "WEB_SEARCH"]


@dataclass(frozen=True)
class TermConceptRef:
    concept_id: uuid.UUID
    craft_slug: str
    type: str
    name: str
    description: str | None


@dataclass(frozen=True)
class GlossaryTerm:
    id: uuid.UUID
    key: str
    label: str
    meaning: str | None
    local_names: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()
    craft_slugs: tuple[str, ...] = ()
    craft_names: tuple[str, ...] = ()
    concepts: tuple[TermConceptRef, ...] = ()
    wikidata_id: str | None = None


@dataclass(frozen=True)
class ResearchedSummary:
    basis: ResearchBasis
    documents: tuple[SourceDocument, ...]
    sentences: tuple[ComposedSentence, ...]


class Searcher(Protocol):
    async def search(self, query: SearchQuery, k: int) -> list[EvidenceItem]: ...

    async def fetch(self, item_id: str) -> SourceDocument: ...


@dataclass(frozen=True)
class LiveTermResearch:
    wikipedia: Searcher
    web: Searcher
    summarise: StructuredModel

    async def researched(self, term: GlossaryTerm) -> ResearchedSummary | None:
        return await self._wikipedia(term) or await self._web(term)

    async def _wikipedia(self, term: GlossaryTerm) -> ResearchedSummary | None:
        try:
            hits = await self.wikipedia.search(SearchQuery(text=research_query(term)), WIKIPEDIA_HITS)
            hit = best_named(hits, term)
            if hit is None:
                return None
            document = await self.wikipedia.fetch(hit.id)
        except ExternalFailure as failure:
            logger.warning("wikipedia summary of %s failed (%s)", term.key, failure.kind)
            return None
        sentences = lead_sentences(document)
        return ResearchedSummary("WIKIPEDIA", (document,), tuple(sentences)) if sentences else None

    async def _web(self, term: GlossaryTerm) -> ResearchedSummary | None:
        try:
            hits = await self.web.search(SearchQuery(text=research_query(term)), WEB_HITS)
        except ExternalFailure as failure:
            logger.warning("web search for %s failed (%s)", term.key, failure.kind)
            return None
        documents = await self._read(hits)
        if not documents:
            return None
        brief = TermBrief(label=term.label, meaning=term.meaning, crafts=term.craft_names)
        try:
            sentences = await summarise_term(self.summarise, brief, documents)
        except AppError as error:
            logger.warning("summarising %s failed: %s", term.key, error)
            return None
        if not sentences:
            return None
        cited = {span.ref for sentence in sentences for span in sentence.spans}
        used = tuple(document for document in documents if document.item.id in cited)
        return ResearchedSummary("WEB_SEARCH", used, tuple(sentences))

    async def _read(self, hits: Sequence[EvidenceItem]) -> list[SourceDocument]:
        documents: list[SourceDocument] = []
        for hit in hits:
            if len(documents) >= WEB_READS:
                break
            try:
                documents.append(await self.web.fetch(hit.id))
            except (ExternalFailure, InvalidInput) as failure:
                logger.warning("reading %s for a term summary failed: %s", hit.id, failure)
        return documents


def research_query(term: GlossaryTerm) -> str:
    context = term.meaning or (term.craft_names[0] if term.craft_names else "")
    return f"{term.label} {context}".strip()[:SEARCH_QUERY_MAX_CHARS]


def names_the_term(item: EvidenceItem, term: GlossaryTerm) -> bool:
    return _naming(item, term) is not None


def best_named(hits: Sequence[EvidenceItem], term: GlossaryTerm) -> EvidenceItem | None:
    ranked = [(naming, -index, hit) for index, hit in enumerate(hits) if (naming := _naming(hit, term))]
    return max(ranked, key=lambda found: (found[0], found[1]))[2] if ranked else None


def _naming(item: EvidenceItem, term: GlossaryTerm) -> tuple[bool, int] | None:
    found = item.external_ids.get("wikidata")
    if term.wikidata_id and found:
        return (True, 0) if found == term.wikidata_id else None
    title = _words(item.title)
    context = {word for text in (term.meaning or "", *term.craft_names) for word in _words(text)}
    qualified = [_qualifiers(title, _words(name), context) for name in _names(term)]
    found_extra = [extra for extra in qualified if extra is not None]
    return (False, max(found_extra)) if found_extra else None


def _qualifiers(title: list[str], name: list[str], context: set[str]) -> int | None:
    if not name or not _runs_in(name, title):
        return None
    extra = [word for word in title if word not in name]
    return len(title) if all(word in context for word in extra) else None


def _runs_in(name: list[str], title: list[str]) -> bool:
    return any(title[start : start + len(name)] == name for start in range(len(title) - len(name) + 1))


def _names(term: GlossaryTerm) -> list[str]:
    names = [term.label, *term.aliases, *term.local_names]
    if term.meaning:
        names.extend(GLOSS_ITEMS.split(term.meaning))
    return [name for name in names if name]


def _words(text: str) -> list[str]:
    return TITLE_WORD.findall(_folded(text))


def lead_sentences(document: SourceDocument) -> list[ComposedSentence]:
    item = document.item
    allowed = {
        item.id: ComposeCandidate(
            id=item.id, kind="EVIDENCE", text=document.text, source_label=item.title[:300], level=LEAD_LEVEL
        )
    }
    lead = next((line.strip() for line in document.text.split("\n") if line.strip()), "")
    kept: list[ComposedSentence] = []
    for text in SENTENCE_END.split(lead):
        sentence = _quoted(text.strip(), item.id)
        if sentence is not None and not sentence_violations(sentence, allowed):
            kept.append(sentence)
        if len(kept) == TERM_SUMMARY_MAX_SENTENCES:
            break
    return kept


def _quoted(text: str, ref: str) -> ComposedSentence | None:
    if not text or len(text) > SENTENCE_MAX_CHARS or trivial_quote(text):
        return None
    quote = text if len(text) <= QUOTE_MAX_CHARS else text[:QUOTE_MAX_CHARS].rsplit(" ", 1)[0].rstrip(" ,;:")
    if trivial_quote(quote):
        return None
    return ComposedSentence(text=text, evidence_ids=[ref], spans=[QuotedSpan(ref=ref, text=quote)])


def _folded(text: str) -> str:
    return " ".join(text.split()).casefold()
