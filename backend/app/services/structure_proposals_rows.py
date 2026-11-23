from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.curation.entities import Reaction as DossierReaction, Species
from app.models import (
    ClaimSource,
    ConceptEdge,
    CuratedClaim,
    Reaction,
    ReactionCitation,
    Term,
    TermConcept,
    TermCraft,
)
from app.research.structure_proposals import (
    ALTERNATIVE,
    GLOSSARY_TERM,
    REACTION,
    AlternativeItem,
    GlossaryTermItem,
    ReactionItem,
)

from .curated_index import CuratedPage
from .curation_keys import curated_id
from .curation_records import label_key
from .curation_structure import CONTRAST_RELATION, alternative_edge_id, reaction_row
from .structure_proposals_owner import StructureOwner
from .structure_proposals_page import OwnerPage, PlacedEntry, material_of, stage_of
from .term_glossary import term_id

__all__ = ["StoredRows", "stored_rows"]

UNSTORED_REACTION = "an approved reaction is stored under its key and the fact that states it"
UNSTORED_ALTERNATIVE = (
    "an approved alternative joins two materials of the page through the fact that states it"
)


@dataclass(frozen=True)
class StoredRows:
    page: OwnerPage
    term_keys: tuple[str, ...] = ()


async def stored_rows(
    session: AsyncSession, owner: StructureOwner, page: OwnerPage, placed: tuple[Any, PlacedEntry]
) -> StoredRows:
    item, entry = placed
    if item.kind == GLOSSARY_TERM:
        return await _glossary_rows(session, owner, page, (item, entry))
    if item.kind == ALTERNATIVE:
        await _alternative_row(session, owner, page, (item, entry))
        return StoredRows(page)
    if item.kind == REACTION and item.stage_key is not None and isinstance(page, CuratedPage):
        return StoredRows(await _reaction_rows(session, owner, page, (item, entry)))
    return StoredRows(page)


async def _glossary_rows(
    session: AsyncSession,
    owner: StructureOwner,
    page: OwnerPage,
    placed: tuple[GlossaryTermItem, PlacedEntry],
) -> StoredRows:
    item, entry = placed
    key = label_key(item.term)
    if key is None or entry.concept_id is None:
        return StoredRows(page)
    term = term_id(key)
    values = {"id": term, "key": key, "label": item.term, "meaning": item.meaning}
    await _insert(session, Term, {**values, "localNames": [], "aliases": [], "wikidataId": None})
    if not owner.is_category:
        await _insert(session, TermCraft, {"termId": term, "craftId": owner.id})
    await _insert(session, TermConcept, {"termId": term, "conceptId": entry.concept_id})
    glossary = [
        found.model_copy(update={"term_key": key}) if found.key == entry.key else found
        for found in page.glossary
    ]
    return StoredRows(page.model_copy(update={"glossary": glossary}), (key,))


async def _alternative_row(
    session: AsyncSession, owner: StructureOwner, page: OwnerPage, placed: tuple[AlternativeItem, PlacedEntry]
) -> None:
    item, entry = placed
    material = material_of(page, item.material_key)
    other = material_of(page, item.alternative_key)
    if material is None or other is None or entry.claim_id is None:
        raise ValueError(UNSTORED_ALTERNATIVE)
    values = {
        "id": alternative_edge_id(owner.slug, item.material_key, item.alternative_key),
        "srcId": material.concept_id,
        "dstId": other.concept_id,
        "relation": CONTRAST_RELATION,
        "sourceRelation": None,
        "claimId": entry.claim_id,
    }
    await _insert(session, ConceptEdge, values)


async def _reaction_rows(
    session: AsyncSession, owner: StructureOwner, page: CuratedPage, placed: tuple[ReactionItem, PlacedEntry]
) -> CuratedPage:
    item, entry = placed
    stage = stage_of(page, item.stage_key)
    if entry.key is None or entry.claim_id is None or stage is None:
        raise ValueError(UNSTORED_REACTION)
    claim_key = await session.scalar(select(CuratedClaim.key).where(CuratedClaim.claimId == entry.claim_id))
    if claim_key is None:
        raise ValueError(UNSTORED_REACTION)
    reaction = DossierReaction(
        id=entry.key,
        kind=item.reaction_kind,
        stage_id=item.stage_key,
        reactants=[Species(name=s.name, formula=s.formula) for s in item.reactants],
        products=[Species(name=s.name, formula=s.formula) for s in item.products],
        claim_ids=[claim_key],
    )
    ordinal = sum(1 for held in page.reactions if held.stage_key == item.stage_key and held.key != entry.key)
    row = {**reaction_row(owner.slug, reaction, ordinal), "stageId": stage.stage_id}
    await _insert(session, Reaction, row)
    cited = await session.scalars(select(ClaimSource.id).where(ClaimSource.claimId == entry.claim_id))
    for claim_source_id in cited.all():
        citation = curated_id(owner.slug, "reaction-citation", entry.key, str(claim_source_id))
        values = {"id": citation, "reactionId": row["id"], "claimSourceId": claim_source_id}
        await _insert(session, ReactionCitation, values)
    reactions = [
        held.model_copy(update={"reaction_id": row["id"]}) if held.key == entry.key else held
        for held in page.reactions
    ]
    return page.model_copy(update={"reactions": reactions})


async def _insert(session: AsyncSession, model: Any, values: dict[str, Any]) -> None:
    await session.execute(insert(model.__table__).values(values).on_conflict_do_nothing())
