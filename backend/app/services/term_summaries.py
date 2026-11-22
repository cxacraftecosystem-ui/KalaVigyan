from __future__ import annotations

import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from app.core.errors import InvalidInput, Refused
from app.research.citations import AnswerSentence, cited_source_ids
from app.research.terms import TERM_SCHEMA_VERSION, TERM_SUMMARY_MAX_SENTENCES, Term
from app.research.vocabulary import CANONICAL_LANGUAGE, FACT_LEVELS

from .answer_translation import AnswerTranslation, translated_sentences
from .knowledge_view import ClaimView
from .term_research import GlossaryTerm, ResearchedSummary

__all__ = [
    "NEEDS_LOOKUP_MESSAGE",
    "NEEDS_LOOKUP_REASON",
    "NO_SUMMARY_REASON",
    "UNKNOWN_TERM_REASON",
    "StoredClaims",
    "StoredTermLookup",
    "TermLookup",
    "TermReader",
    "TermResearch",
    "TermStore",
    "cites_only_shown",
    "term_view",
]

UNKNOWN_TERM_REASON = "unknown_term"
NO_SUMMARY_REASON = "no_cited_summary"
NEEDS_LOOKUP_REASON = "needs_lookup"
UNKNOWN_TERM_MESSAGE = "No term has that address."
NO_SUMMARY_MESSAGE = "This term has no cited summary yet."
NEEDS_LOOKUP_MESSAGE = "Sign in to look this term up."
STORED_BASIS = "STORED"


@dataclass(frozen=True)
class StoredClaims:
    views: Sequence[ClaimView] = ()
    sources: Mapping[str, dict[str, Any]] = field(default_factory=dict)
    changed_at: datetime | None = None


class TermStore(Protocol):
    async def term(self, key: str) -> GlossaryTerm | None: ...

    async def cached(self, term_id: uuid.UUID, language: str) -> Term | None: ...

    async def defining_claims(self, term: GlossaryTerm) -> StoredClaims: ...

    async def write_back(self, term: GlossaryTerm, researched: ResearchedSummary) -> list[uuid.UUID]: ...

    async def cited(self, claim_ids: Sequence[uuid.UUID]) -> StoredClaims: ...

    async def remember(self, term_id: uuid.UUID, summary: Term) -> None: ...


class TermResearch(Protocol):
    async def researched(self, term: GlossaryTerm) -> ResearchedSummary | None: ...


class TermReader(Protocol):
    async def summary(self, key: str, language: str) -> Term: ...


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class TermLookup:
    store: TermStore
    research: TermResearch
    translation: AnswerTranslation
    clock: Callable[[], datetime] = utc_now

    async def summary(self, key: str, language: str) -> Term:
        term = await _known_term(self.store, key)
        found = await self.store.cached(term.id, language)
        if found is not None:
            return found
        english = None
        if language != CANONICAL_LANGUAGE:
            english = await self.store.cached(term.id, CANONICAL_LANGUAGE)
        if english is None:
            english = await self._english(term)
            await self.store.remember(term.id, english)
        if language == CANONICAL_LANGUAGE:
            return english
        translated = await self._translated(english, language)
        await self.store.remember(term.id, translated)
        return translated

    async def _english(self, term: GlossaryTerm) -> Term:
        stored = await _stored_english(self.store, term)
        if stored is not None:
            return stored
        researched = await self.research.researched(term)
        if researched is None:
            raise Refused(NO_SUMMARY_REASON, NO_SUMMARY_MESSAGE)
        claim_ids = list(dict.fromkeys(await self.store.write_back(term, researched)))
        cited = await self.store.cited(claim_ids)
        if not cited.views:
            raise Refused(NO_SUMMARY_REASON, NO_SUMMARY_MESSAGE)
        return term_view(term, researched.basis, cited, language=CANONICAL_LANGUAGE, checked_at=self.clock())

    async def _translated(self, english: Term, language: str) -> Term:
        sentences = [sentence.model_dump(mode="json", by_alias=True) for sentence in english.summary]
        translated = await translated_sentences(
            sentences, language=language, translation=self.translation, claim_texts=_claim_texts(english)
        )
        shown = english.model_dump(mode="json", by_alias=True)
        return Term.model_validate({**shown, "language": language, "summary": translated})


@dataclass(frozen=True)
class StoredTermLookup:
    store: TermStore

    async def summary(self, key: str, language: str) -> Term:
        term = await _known_term(self.store, key)
        found = await self.store.cached(term.id, language)
        if found is not None:
            return found
        english = await _stored_english(self.store, term) if language == CANONICAL_LANGUAGE else None
        if english is None:
            raise Refused(NEEDS_LOOKUP_REASON, NEEDS_LOOKUP_MESSAGE)
        return english


async def _known_term(store: TermStore, key: str) -> GlossaryTerm:
    term = await store.term(key)
    if term is None:
        raise Refused(UNKNOWN_TERM_REASON, UNKNOWN_TERM_MESSAGE)
    return term


async def _stored_english(store: TermStore, term: GlossaryTerm) -> Term | None:
    stored = await store.defining_claims(term)
    if not stored.views:
        return None
    if stored.changed_at is None:
        raise InvalidInput(
            f"The stored claims defining the term {term.key} carry no time of their last change"
        )
    return term_view(term, STORED_BASIS, stored, language=CANONICAL_LANGUAGE, checked_at=stored.changed_at)


def cites_only_shown(summary: Term, views: Mapping[uuid.UUID, ClaimView]) -> bool:
    for sentence in summary.summary:
        for citation in sentence.citations:
            view = views.get(uuid.UUID(citation.claim_id))
            if view is None or not view.shows_citation(citation.id, quoted=citation.quote is not None):
                return False
    return True


def term_view(
    term: GlossaryTerm, basis: str, claims: StoredClaims, *, language: str, checked_at: datetime
) -> Term:
    facts = [view for view in claims.views if view.level in FACT_LEVELS and view.citations]
    unique = list({view.id: view for view in facts}.values())[:TERM_SUMMARY_MAX_SENTENCES]
    if not unique:
        raise Refused(NO_SUMMARY_REASON, NO_SUMMARY_MESSAGE)
    summary = [
        AnswerSentence(id=f"{term.key}.{n}", text=view.text, level=view.level, citations=view.citations)
        for n, view in enumerate(unique, start=1)
    ]
    return Term(
        schema_version=TERM_SCHEMA_VERSION,
        key=term.key,
        label=term.label,
        language=language,
        local_names=list(term.local_names),
        craft_slugs=list(term.craft_slugs),
        wikidata_id=term.wikidata_id,
        basis=basis,
        summary=summary,
        sources=[claims.sources[source_id] for source_id in cited_source_ids(summary)],
        checked_at=checked_at,
    )


def _claim_texts(summary: Term) -> dict[uuid.UUID, str]:
    texts: dict[uuid.UUID, str] = {}
    for sentence in summary.summary:
        claims = {citation.claim_id for citation in sentence.citations}
        if len(claims) == 1:
            texts[uuid.UUID(claims.pop())] = sentence.original or sentence.text
    return texts
