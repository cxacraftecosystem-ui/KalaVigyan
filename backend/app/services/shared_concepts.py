from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Craft, SharedTermCraft, Term
from app.research.citations import SourceRef
from app.research.crafts import CraftRef
from app.research.offered_facts import OfferedFact
from app.research.retrieval import OPEN_CHUNK_ACLS
from app.research.shared_science import (
    SHARED_SCIENCE_NODES_MAX,
    SharedConcept,
    SharedScience,
    TermCraftOffer,
    TermOffer,
    shared_concept,
    shared_science,
)

from . import knowledge_view
from .learning_facts import offered_fact, source_refs
from .shared_term_crafts import TermCrafts, stored_term_crafts

__all__ = [
    "SHARED_TERMS_SCANNED",
    "TermOffers",
    "craft_shared_science",
    "shared_concept_of",
    "term_ids_of",
    "term_offers",
]

SHARED_TERMS_SCANNED = 2 * SHARED_SCIENCE_NODES_MAX
MERGED = "MERGED"


@dataclass(frozen=True)
class TermOffers:
    offers: tuple[TermOffer, ...] = ()
    sources: Mapping[str, SourceRef] = field(default_factory=dict)


async def craft_shared_science(
    session: AsyncSession, craft: Craft, *, acls: Sequence[str] = OPEN_CHUNK_ACLS
) -> SharedScience:
    found = await term_offers(session, await _shared_term_ids(session, craft.id), acls=acls)
    return shared_science(
        CraftRef.model_validate(knowledge_view.craft_ref(craft)), found.offers, found.sources
    )


async def shared_concept_of(
    session: AsyncSession, term_key: str, focus: Craft | None, *, acls: Sequence[str] = OPEN_CHUNK_ACLS
) -> SharedConcept | None:
    term_ids = await term_ids_of(session, [term_key])
    if not term_ids:
        return None
    found = await term_offers(session, term_ids, acls=acls)
    if not found.offers:
        return None
    return shared_concept(found.offers[0], found.sources, focus=focus.slug if focus is not None else None)


async def term_ids_of(session: AsyncSession, keys: Sequence[str]) -> list[uuid.UUID]:
    if not keys:
        return []
    rows = (await session.execute(select(Term.key, Term.id).where(Term.key.in_(list(keys))))).all()
    by_key = {row.key: row.id for row in rows}
    return [by_key[key] for key in dict.fromkeys(keys) if key in by_key]


async def term_offers(
    session: AsyncSession, term_ids: Sequence[uuid.UUID], *, acls: Sequence[str] = OPEN_CHUNK_ACLS
) -> TermOffers:
    if not term_ids:
        return TermOffers()
    terms = await _terms(session, term_ids)
    shared = await stored_term_crafts(session, term_ids)
    crafts = await _crafts(session, {row.craft_id for row in shared})
    views, sources = await knowledge_view.claims_by_id(
        session, [claim_id for row in shared for claim_id in row.claim_ids], acls=acls
    )
    refs = source_refs(sources)
    facts: dict[uuid.UUID, list[OfferedFact]] = defaultdict(list)
    for view in views.values():
        fact = offered_fact(view, refs)
        if fact is not None and view.concept_id is not None:
            facts[view.concept_id].append(fact)
    offers = tuple(
        _offer(terms[term_id], [row for row in shared if row.term_id == term_id], crafts, facts)
        for term_id in term_ids
        if term_id in terms
    )
    return TermOffers(offers=offers, sources=refs)


def _offer(
    term: Any,
    shared: Sequence[TermCrafts],
    crafts: Mapping[uuid.UUID, CraftRef],
    facts: Mapping[uuid.UUID, Sequence[OfferedFact]],
) -> TermOffer:
    entries = [
        TermCraftOffer(
            craft=crafts[row.craft_id],
            concept_ids=row.concept_ids,
            facts=tuple(fact for concept_id in row.concept_ids for fact in facts.get(concept_id, ())),
        )
        for row in shared
        if row.craft_id in crafts
    ]
    return TermOffer(
        key=term.key,
        label=term.label,
        surfaces=(term.label, *term.aliases, *term.localNames),
        crafts=tuple(entries),
    )


async def _shared_term_ids(session: AsyncSession, craft_id: uuid.UUID) -> list[uuid.UUID]:
    rows = await session.scalars(
        select(Term.id)
        .join(SharedTermCraft, SharedTermCraft.termId == Term.id)
        .where(SharedTermCraft.craftId == craft_id)
        .order_by(Term.label, Term.key)
        .limit(SHARED_TERMS_SCANNED)
    )
    return list(rows)


async def _terms(session: AsyncSession, term_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, Any]:
    rows = await session.execute(
        select(Term.id, Term.key, Term.label, Term.aliases, Term.localNames).where(
            Term.id.in_(list(term_ids))
        )
    )
    return {row.id: row for row in rows.all()}


async def _crafts(session: AsyncSession, craft_ids: set[uuid.UUID]) -> dict[uuid.UUID, CraftRef]:
    if not craft_ids:
        return {}
    rows = await session.execute(
        select(Craft.id, Craft.slug, Craft.name).where(Craft.id.in_(list(craft_ids)), Craft.status != MERGED)
    )
    return {row.id: CraftRef(slug=row.slug, name=row.name, path=f"/crafts/{row.slug}") for row in rows.all()}
