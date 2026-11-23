from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput
from app.models import (
    Craft,
    CraftCategory,
    CuratedCategory,
    CuratedCategoryClaim,
    CuratedClaim,
    CuratedCraft,
    StructureProposal as ProposalRow,
)
from app.research.structure_proposals import CATEGORY_SUBJECT, CRAFT_SUBJECT, StructureSubject

from . import knowledge_view
from .curated_category_index import stored_category_page
from .curated_index import stored_curated_page
from .structure_proposals_page import OwnerPage

__all__ = [
    "OwnerPage",
    "StructureOwner",
    "claim_marker",
    "owned_claim_ids",
    "owner_page",
    "proposal_owner",
    "store_owner_page",
    "subject_owner",
    "taken_claim_keys",
]

UNKNOWN_CRAFT = "No craft has the slug {slug!r}; find_crafts gives the slugs of crafts and families."
UNKNOWN_CATEGORY = "No category has the slug {slug!r}; find_crafts gives the slugs of categories."


@dataclass(frozen=True)
class StructureOwner:
    kind: str
    id: uuid.UUID
    slug: str
    name: str

    @property
    def is_category(self) -> bool:
        return self.kind == CATEGORY_SUBJECT

    @property
    def subject(self) -> StructureSubject:
        return StructureSubject.model_validate({"kind": self.kind, "slug": self.slug})

    def page_url(self, site: str) -> str:
        return f"{site}/{'categories' if self.is_category else 'crafts'}/{self.slug}"

    def row_owner(self) -> dict[str, uuid.UUID | None]:
        if self.is_category:
            return {"craftId": None, "categoryId": self.id}
        return {"craftId": self.id, "categoryId": None}


async def subject_owner(session: AsyncSession, subject: StructureSubject) -> StructureOwner:
    if subject.kind == CATEGORY_SUBJECT:
        category = await session.scalar(select(CraftCategory).where(CraftCategory.slug == subject.slug))
        if category is None:
            raise InvalidInput(UNKNOWN_CATEGORY.format(slug=subject.slug))
        return StructureOwner(CATEGORY_SUBJECT, category.id, category.slug, category.name)
    craft = await knowledge_view.resolve_craft(session, subject.slug)
    if craft is None:
        raise InvalidInput(UNKNOWN_CRAFT.format(slug=subject.slug))
    return StructureOwner(CRAFT_SUBJECT, craft.id, craft.slug, craft.name)


async def proposal_owner(session: AsyncSession, row: ProposalRow) -> StructureOwner | None:
    if row.categoryId is not None:
        category = await session.get(CraftCategory, row.categoryId)
        return (
            None
            if category is None
            else StructureOwner(CATEGORY_SUBJECT, category.id, category.slug, category.name)
        )
    craft = await session.get(Craft, row.craftId) if row.craftId is not None else None
    return None if craft is None else StructureOwner(CRAFT_SUBJECT, craft.id, craft.slug, craft.name)


async def owner_page(session: AsyncSession, owner: StructureOwner, *, lock: bool) -> OwnerPage | None:
    if owner.is_category:
        found = select(CuratedCategory.page).where(CuratedCategory.categoryId == owner.id)
        stored = await session.scalar(found.with_for_update() if lock else found)
        return stored_category_page(owner.id, stored)
    query = select(CuratedCraft.page).where(CuratedCraft.craftId == owner.id)
    return stored_curated_page(owner.id, await session.scalar(query.with_for_update() if lock else query))


async def store_owner_page(session: AsyncSession, owner: StructureOwner, page: OwnerPage) -> None:
    values = {"page": page.model_dump(mode="json", by_alias=True), "updatedAt": func.now()}
    if owner.is_category:
        await session.execute(
            update(CuratedCategory).where(CuratedCategory.categoryId == owner.id).values(values)
        )
        return
    await session.execute(update(CuratedCraft).where(CuratedCraft.craftId == owner.id).values(values))


async def owned_claim_ids(session: AsyncSession, owner: StructureOwner) -> frozenset[uuid.UUID]:
    marker, column = _marker(owner)
    return frozenset(await session.scalars(select(marker.claimId).where(column == owner.id)))


async def taken_claim_keys(session: AsyncSession, owner: StructureOwner) -> list[str]:
    marker, column = _marker(owner)
    return list(await session.scalars(select(marker.key).where(column == owner.id)))


def claim_marker(owner: StructureOwner, claim_id: uuid.UUID, key: str, discipline: str | None) -> Any:
    if owner.is_category:
        return CuratedCategoryClaim(claimId=claim_id, categoryId=owner.id, key=key, discipline=discipline)
    return CuratedClaim(claimId=claim_id, craftId=owner.id, key=key, discipline=discipline)


def _marker(owner: StructureOwner) -> tuple[Any, Any]:
    if owner.is_category:
        return CuratedCategoryClaim, CuratedCategoryClaim.categoryId
    return CuratedClaim, CuratedClaim.craftId
