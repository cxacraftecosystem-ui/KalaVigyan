from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Claim, Concept, Craft, KnowledgePiece as PieceRow, Term, TermConcept, TermCraft
from app.research.blocks import ExplainerSentence
from app.research.blocks_learning import COMPARE_CRAFTS_MIN
from app.research.citations import SourceRef
from app.research.craft_compare import (
    COMPARE_BLOCK_ID,
    COMPARE_SCHEMA_VERSION,
    CraftComparison,
    CraftFacts,
    SharedTerm,
    compare_block,
)
from app.research.crafts import CraftRef
from app.research.knowledge_pieces import KnowledgePiece
from app.research.offered_facts import PIECE_FIRST, OfferedFact, fact_rank, sentence_claim_ids
from app.research.piece_reuse import visible_as_cited
from app.research.retrieval import OPEN_CHUNK_ACLS
from app.research.vocabulary import CANONICAL_LANGUAGE

from . import knowledge_view
from .learning_facts import offered_fact, source_refs
from .piece_lookup import claim_states, stored_piece

__all__ = [
    "COMPARE_MODE",
    "COMPARE_PIECES_MAX",
    "CompareOffers",
    "claim_fields",
    "comparison_offers",
    "craft_comparison",
    "filed_facets",
]

COMPARE_MODE = "HYBRID"
COMPARE_PIECES_MAX = 60
PROSE = "prose"


@dataclass(frozen=True)
class CompareOffers:
    crafts: tuple[CraftFacts, ...] = ()
    terms: tuple[SharedTerm, ...] = ()
    sources: Mapping[str, SourceRef] = field(default_factory=dict)


async def craft_comparison(
    session: AsyncSession,
    crafts: Sequence[Craft],
    facets: Sequence[str],
    *,
    acls: Sequence[str] = OPEN_CHUNK_ACLS,
) -> CraftComparison | None:
    offers = await comparison_offers(session, crafts, facets, acls=acls)
    block = compare_block(offers.crafts, offers.terms, facets=facets, block_id=COMPARE_BLOCK_ID)
    if block is None:
        return None
    sources = [offers.sources[sid] for sid in block.cited_source_ids()]
    return CraftComparison(schema_version=COMPARE_SCHEMA_VERSION, comparison=block, sources=sources)


async def comparison_offers(
    session: AsyncSession,
    crafts: Sequence[Craft],
    facets: Sequence[str],
    *,
    acls: Sequence[str] = OPEN_CHUNK_ACLS,
) -> CompareOffers:
    if len(crafts) < COMPARE_CRAFTS_MIN:
        return CompareOffers()
    sources: dict[str, SourceRef] = {}
    pieces = await _piece_facts(session, crafts, facets, sources, acls=acls)
    entries = []
    for craft in crafts:
        claims = await _claim_facts(session, craft, facets, sources, acls=acls)
        ref = CraftRef.model_validate(knowledge_view.craft_ref(craft))
        entries.append(CraftFacts(craft=ref, facts=(*pieces.get(craft.id, ()), *claims)))
    terms = await _shared_terms(session, [craft.id for craft in crafts])
    return CompareOffers(crafts=tuple(entries), terms=terms, sources=sources)


async def _claim_facts(
    session: AsyncSession,
    craft: Craft,
    facets: Sequence[str],
    sources: dict[str, SourceRef],
    *,
    acls: Sequence[str],
) -> list[OfferedFact]:
    views, found = await knowledge_view.claims_for(session, craft, mode=COMPARE_MODE, acls=acls)
    refs = source_refs(found)
    sources.update(refs)
    own = set(await session.scalars(select(Concept.id).where(Concept.craftId == craft.id)))
    filed = await claim_fields(session, [view.id for view in views])
    facts: list[OfferedFact] = []
    for view in views:
        if view.concept_id not in own or view.concept_type == knowledge_view.EDGE_SECTION:
            continue
        for facet in filed_facets(filed.get(view.id, ()), facets):
            fact = offered_fact(view, refs, facet=facet)
            if fact is not None:
                facts.append(fact)
    return facts


def filed_facets(filed: Sequence[str], facets: Sequence[str]) -> list[str]:
    return [facet for facet in dict.fromkeys(facets) if facet in filed]


async def claim_fields(
    session: AsyncSession, claim_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, tuple[str, ...]]:
    if not claim_ids:
        return {}
    rows = await session.execute(
        select(Claim.id, Claim.field, Claim.fields).where(
            Claim.id.in_(list(claim_ids)), Claim.field.is_not(None)
        )
    )
    return {row.id: (row.field, *row.fields) for row in rows.all()}


async def _piece_facts(
    session: AsyncSession,
    crafts: Sequence[Craft],
    facets: Sequence[str],
    sources: dict[str, SourceRef],
    *,
    acls: Sequence[str],
) -> dict[uuid.UUID, list[OfferedFact]]:
    rows = await session.scalars(
        select(PieceRow)
        .where(
            PieceRow.craftId.in_([craft.id for craft in crafts]),
            PieceRow.kind == PROSE,
            PieceRow.facet.in_(list(facets)),
            PieceRow.language == CANONICAL_LANGUAGE,
            PieceRow.staleSince.is_(None),
            PieceRow.supersededById.is_(None),
        )
        .order_by(PieceRow.createdAt.desc(), PieceRow.id)
        .limit(COMPARE_PIECES_MAX)
    )
    newest: dict[tuple[uuid.UUID, str], KnowledgePiece] = {}
    for piece in (stored_piece(row) for row in rows):
        if piece is not None and piece.craft_id is not None:
            newest.setdefault((piece.craft_id, piece.facet), piece)
    if not newest:
        return {}
    states, cited = await claim_states(session, list(newest.values()), acls=acls)
    sources.update({sid: SourceRef.model_validate(ref) for sid, ref in cited.sources.items()})
    facts: dict[uuid.UUID, list[OfferedFact]] = {}
    for (craft_id, facet), piece in newest.items():
        sentence = _first_visible(piece, {str(claim) for claim in visible_as_cited(piece, states)})
        if sentence is not None:
            rank = fact_rank(sentence, sources, origin=PIECE_FIRST)
            facts.setdefault(craft_id, []).append(
                OfferedFact(sentence=sentence, rank=rank, facet=facet, piece_id=piece.id)
            )
    return facts


def _first_visible(piece: KnowledgePiece, visible: set[str]) -> ExplainerSentence | None:
    for sentence in piece.payload.cited_sentences():
        if isinstance(sentence, ExplainerSentence) and sentence_claim_ids(sentence) <= visible:
            return sentence
    return None


async def _shared_terms(session: AsyncSession, craft_ids: Sequence[uuid.UUID]) -> tuple[SharedTerm, ...]:
    shared = (
        select(TermCraft.termId)
        .where(TermCraft.craftId.in_(list(craft_ids)))
        .group_by(TermCraft.termId)
        .having(func.count(distinct(TermCraft.craftId)) >= COMPARE_CRAFTS_MIN)
    )
    rows = (
        await session.execute(
            select(Term.id, Term.key, Term.label, Term.aliases, Term.localNames)
            .where(Term.id.in_(shared))
            .order_by(Term.label, Term.key)
        )
    ).all()
    links = await session.execute(
        select(TermConcept.termId, TermConcept.conceptId).where(
            TermConcept.termId.in_([row.id for row in rows])
        )
    )
    concepts: dict[uuid.UUID, set[uuid.UUID]] = {}
    for link in links.all():
        concepts.setdefault(link.termId, set()).add(link.conceptId)
    return tuple(
        SharedTerm(
            key=row.key,
            label=row.label,
            surfaces=(row.label, *row.aliases, *row.localNames),
            concept_ids=frozenset(concepts.get(row.id, ())),
        )
        for row in rows
    )
