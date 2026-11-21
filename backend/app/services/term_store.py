from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime

from sqlalchemy import Select, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.errors import InvalidInput
from app.models import (
    Claim,
    ClaimSource,
    Concept,
    Craft,
    Term as TermRow,
    TermConcept,
    TermCraft,
    TermSummary,
)
from app.research.composition import ComposedSentence
from app.research.embedding import TextEmbedder
from app.research.evidence import Quote, SourceDocument
from app.research.retrieval import OPEN_CHUNK_ACLS
from app.research.terms import Term
from app.research.write_back import ClaimWriteBack, WriteBackCitation, WriteBackSubject

from . import knowledge_view
from .live_source_store import keep_document
from .research_write_back import write_through_gates
from .term_research import GlossaryTerm, ResearchedSummary, TermConceptRef
from .term_summaries import StoredClaims, cites_only_shown
from .write_back_plan import QUOTED_REASON, WRITE_BACK_PREDICATE, quote_carries
from .written_vectors import embed_now

__all__ = ["CONCEPT_SUBJECT_TYPE", "SqlTermStore", "claim_for_sentence", "write_back_subject"]

CONCEPT_SUBJECT_TYPE = "CONCEPT"
TERM_FACET = "CONCEPT"
FOUND_BY = "BACKGROUND"


class SqlTermStore:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        *,
        acls: Sequence[str] = OPEN_CHUNK_ACLS,
        embed: TextEmbedder | None = None,
    ) -> None:
        self._sessions = sessions
        self._acls = acls
        self._embed = embed

    async def term(self, key: str) -> GlossaryTerm | None:
        async with self._sessions() as session:
            row = await session.scalar(select(TermRow).where(TermRow.key == key))
            if row is None:
                return None
            crafts = (await session.execute(_crafts_of(row.id))).all()
            concepts = (await session.execute(_concepts_of(row.id))).all()
        return GlossaryTerm(
            id=row.id,
            key=row.key,
            label=row.label,
            meaning=row.meaning,
            local_names=tuple(row.localNames),
            aliases=tuple(row.aliases),
            craft_slugs=tuple(craft.slug for craft in crafts),
            craft_names=tuple(craft.name for craft in crafts),
            concepts=tuple(TermConceptRef(c.id, c.slug, c.type, c.name, c.description) for c in concepts),
            wikidata_id=row.wikidataId,
        )

    async def cached(self, term_id: uuid.UUID, language: str) -> Term | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(TermSummary).where(TermSummary.termId == term_id, TermSummary.language == language)
            )
            if row is None:
                return None
            visible, _ = await knowledge_view.claims_by_id(session, row.claimIds, acls=self._acls)
        if set(row.claimIds) - set(visible):
            return None
        summary = Term.model_validate(row.payload)
        return summary if cites_only_shown(summary, visible) else None

    async def defining_claims(self, term: GlossaryTerm) -> StoredClaims:
        described = {c.concept_id: _folded(c.description) for c in term.concepts if c.description}
        if not described:
            return StoredClaims()
        async with self._sessions() as session:
            rows = (
                await session.execute(
                    select(Claim.id, Claim.subjectId, Claim.text).where(
                        Claim.subjectType == CONCEPT_SUBJECT_TYPE, Claim.subjectId.in_(list(described))
                    )
                )
            ).all()
            defining = {
                row.subjectId: row.id for row in rows if _folded(row.text) == described[row.subjectId]
            }
            ordered = [defining[c.concept_id] for c in term.concepts if c.concept_id in defining]
            views, sources = await knowledge_view.claims_by_id(session, ordered, acls=self._acls)
            stored = _stored(ordered, views, sources)
            changed = await _changed_at(session, stored.views)
        return replace(stored, changed_at=changed)

    async def write_back(self, term: GlossaryTerm, researched: ResearchedSummary) -> list[uuid.UUID]:
        craft_slug, subject = write_back_subject(term)
        documents = {document.item.id: document for document in researched.documents}
        claims = [
            claim_for_sentence(sentence, documents, craft_slug, subject) for sentence in researched.sentences
        ]
        async with self._sessions() as session:
            kept = [await keep_document(session, document) for document in researched.documents]
            gated = await write_through_gates(session, claims, documents, embed=None, judge=None)
            await session.commit()
            written = gated.claim_ids()
            if self._embed is not None:
                await embed_now(session, self._embed, claim_ids=list(written.values()), source_ids=kept)
        return [written[claim.dedupe_key] for claim in claims if claim.dedupe_key in written]

    async def cited(self, claim_ids: Sequence[uuid.UUID]) -> StoredClaims:
        async with self._sessions() as session:
            views, sources = await knowledge_view.claims_by_id(session, claim_ids, acls=self._acls)
        return _stored(claim_ids, views, sources)

    async def remember(self, term_id: uuid.UUID, summary: Term) -> None:
        claim_ids = sorted(
            {uuid.UUID(c.claim_id) for sentence in summary.summary for c in sentence.citations}, key=str
        )
        values = {
            "termId": term_id,
            "language": summary.language,
            "basis": summary.basis,
            "payload": summary.model_dump(mode="json", by_alias=True),
            "claimIds": claim_ids,
            "checkedAt": summary.checked_at,
        }
        statement = insert(TermSummary).values(values)
        changed = {key: statement.excluded[key] for key in ("basis", "payload", "claimIds", "checkedAt")}
        async with self._sessions() as session:
            await session.execute(
                statement.on_conflict_do_update(
                    index_elements=[TermSummary.termId, TermSummary.language],
                    set_={**changed, "updatedAt": func.now()},
                )
            )
            await session.commit()


def write_back_subject(term: GlossaryTerm) -> tuple[str | None, WriteBackSubject]:
    if not term.craft_slugs:
        raise InvalidInput(f"Term {term.key} belongs to no craft, so what is found for it cannot be kept")
    craft_slug = _owning_craft(term)
    if craft_slug is None:
        return None, WriteBackSubject(concept_type=TERM_FACET, concept_name=term.label)
    concept = next((c for c in term.concepts if c.craft_slug == craft_slug), None)
    if concept is None:
        return craft_slug, WriteBackSubject(concept_type=TERM_FACET, concept_name=term.label)
    return craft_slug, WriteBackSubject(
        concept_id=concept.concept_id, concept_type=concept.type, concept_name=concept.name
    )


def _owning_craft(term: GlossaryTerm) -> str | None:
    if len(term.craft_slugs) == 1:
        return term.craft_slugs[0]
    owners = list(dict.fromkeys(concept.craft_slug for concept in term.concepts))
    return owners[0] if len(owners) == 1 else None


def claim_for_sentence(
    sentence: ComposedSentence,
    documents: dict[str, SourceDocument],
    craft_slug: str | None,
    subject: WriteBackSubject,
) -> ClaimWriteBack:
    citations = []
    for span in sentence.spans:
        item = documents[span.ref].item
        quote = Quote(text=span.text)
        known = item.quotes if quote in item.quotes else [*item.quotes, quote]
        citations.append(
            WriteBackCitation(
                evidence=item.model_copy(update={"quotes": known}),
                quote=quote,
                quote_check="PASS",
                relation="DIRECT" if quote_carries(sentence.text, quote) else "CONTEXTUAL",
            )
        )
    return ClaimWriteBack(
        craft_slug=craft_slug,
        subject=subject,
        predicate=WRITE_BACK_PREDICATE,
        text=sentence.text,
        label="QUOTED",
        level_reason=QUOTED_REASON,
        citations=citations,
        found_by=FOUND_BY,
    )


def _crafts_of(term_id: uuid.UUID) -> Select:
    return (
        select(Craft.slug, Craft.name)
        .join(TermCraft, TermCraft.craftId == Craft.id)
        .where(TermCraft.termId == term_id)
        .order_by(Craft.slug)
    )


def _concepts_of(term_id: uuid.UUID) -> Select:
    return (
        select(Concept.id, Concept.type, Concept.name, Concept.description, Craft.slug)
        .join(TermConcept, TermConcept.conceptId == Concept.id)
        .join(Craft, Craft.id == Concept.craftId)
        .where(TermConcept.termId == term_id)
        .order_by(Craft.slug, Concept.type, Concept.name)
    )


async def _changed_at(session: AsyncSession, views: Sequence[knowledge_view.ClaimView]) -> datetime | None:
    if not views:
        return None
    citation_ids = [uuid.UUID(citation["id"]) for view in views for citation in view.citations]
    claims = await session.scalar(
        select(func.max(Claim.updatedAt)).where(Claim.id.in_([v.id for v in views]))
    )
    citations = await session.scalar(
        select(func.max(ClaimSource.updatedAt)).where(ClaimSource.id.in_(citation_ids))
    )
    return max(stamp for stamp in (claims, citations) if stamp is not None)


def _stored(order: Sequence[uuid.UUID], views: dict, sources: dict) -> StoredClaims:
    shown = [views[claim_id] for claim_id in dict.fromkeys(order) if claim_id in views]
    return StoredClaims(
        views=shown, sources={str(key): knowledge_view.source_ref(source) for key, source in sources.items()}
    )


def _folded(text: str | None) -> str:
    return " ".join((text or "").split()).casefold().rstrip(" .")
