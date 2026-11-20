from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import Select, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ArtisanContribution,
    ComponentProposal,
    Concept,
    Craft,
    CraftCategory,
    ImageContribution,
    LayoutProposal,
    StructureProposal,
)
from app.research.page_revalidation import PageOwners
from app.research.review_queue import COMPONENTS, FACTS, IMAGES, LAYOUTS, STRUCTURE, TESTIMONY, QueueDecision
from app.research.structure_proposals import APPROVED_STATUS

from .page_revalidation import claim_owners, craft_owners, merged_owners, refresh_pages

__all__ = ["refresh_after_decision"]

REJECTED_TESTIMONY = "REJECTED"
APPROVED = "APPROVED"
CRAFT_SUBJECT = "CRAFT"
CONCEPT_SUBJECT = "CONCEPT"


async def refresh_after_decision(session: AsyncSession, decided: QueueDecision) -> bool:
    return await refresh_pages(await _owners(session, decided))


async def _owners(session: AsyncSession, decided: QueueDecision) -> PageOwners:
    if decided.kind == FACTS:
        return await claim_owners(session, [decided.id])
    if decided.kind == COMPONENTS and decided.status == APPROVED:
        return await _component_owners(session, decided.id)
    if decided.kind == LAYOUTS and decided.status == APPROVED:
        return await _layout_owners(session, decided.id)
    craft = _owning_craft(decided)
    if craft is None:
        return PageOwners()
    found = [craft_id for craft_id in (await session.scalars(craft)).all() if craft_id is not None]
    return await craft_owners(session, found)


def _owning_craft(decided: QueueDecision) -> Select[Any] | None:
    if decided.kind == TESTIMONY and decided.status == REJECTED_TESTIMONY:
        return select(ArtisanContribution.craftId).where(ArtisanContribution.id == decided.id)
    if decided.kind == STRUCTURE and decided.status == APPROVED_STATUS:
        return select(StructureProposal.craftId).where(StructureProposal.id == decided.id)
    if decided.kind == IMAGES and decided.status == APPROVED:
        return select(ImageContribution.craftId).where(ImageContribution.id == decided.id)
    return None


async def _component_owners(session: AsyncSession, proposal_id: uuid.UUID) -> PageOwners:
    row = await session.get(ComponentProposal, proposal_id)
    if row is None:
        return PageOwners()
    crafts = await _subject_crafts(session, row.subjects)
    owned = await craft_owners(session, {*crafts, *([row.craftId] if row.craftId is not None else [])})
    return merged_owners(owned, await claim_owners(session, list(row.claimIds)))


async def _subject_crafts(session: AsyncSession, subjects: Sequence[Mapping[str, Any]]) -> set[uuid.UUID]:
    slugs = [str(subject["key"]) for subject in subjects if subject.get("kind") == CRAFT_SUBJECT]
    concepts = [_uuid(subject.get("key")) for subject in subjects if subject.get("kind") == CONCEPT_SUBJECT]
    named = [concept for concept in concepts if concept is not None]
    found: set[uuid.UUID] = set()
    if slugs:
        found |= set((await session.scalars(select(Craft.id).where(Craft.slug.in_(slugs)))).all())
    if named:
        owners = select(Concept.subCategoryId).where(
            Concept.id.in_(named), Concept.subCategoryId.is_not(None)
        )
        own = select(Concept.craftId).where(Concept.id.in_(named))
        members = select(Craft.id).where(or_(Craft.id.in_(own), Craft.subCategoryId.in_(owners)))
        found |= set((await session.scalars(members)).all())
    return found


async def _layout_owners(session: AsyncSession, proposal_id: uuid.UUID) -> PageOwners:
    row = (
        await session.execute(
            select(LayoutProposal.craftId, LayoutProposal.categoryId).where(LayoutProposal.id == proposal_id)
        )
    ).first()
    if row is None:
        return PageOwners()
    if row.categoryId is None:
        return await craft_owners(session, [row.craftId] if row.craftId is not None else [])
    slugs = await session.scalars(select(CraftCategory.slug).where(CraftCategory.id == row.categoryId))
    return PageOwners(categories=tuple(slugs.all()))


def _uuid(value: object) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except ValueError:
        return None
