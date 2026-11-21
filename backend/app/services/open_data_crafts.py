from __future__ import annotations

import json
import uuid
from collections.abc import Mapping
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import defer

from app.data.craft_master_loader import CRAFT_WIKIDATA_FILE
from app.models import (
    AdminDistrict,
    AdminState,
    Craft,
    CraftCategory,
    CraftLocation,
    CraftSubCategory,
    CuratedCategory,
    CuratedCraft,
)

from .glossary_plan import wikidata_links
from .open_data_values import Row, stamp_of

__all__ = [
    "MERGED",
    "NO_PLACE",
    "CraftLookup",
    "Placement",
    "category_rows",
    "craft_lookup",
    "craft_place_rows",
    "craft_rows",
    "family_rows",
]

Placement = tuple[str | None, str | None, str | None]

MERGED = "MERGED"
MERGE_HOPS = 5
NO_PLACE: Placement = (None, None, None)


@dataclass(frozen=True)
class CraftLookup:
    crafts: Mapping[uuid.UUID, Craft]
    families: Mapping[uuid.UUID, CraftSubCategory]
    categories: Mapping[uuid.UUID, CraftCategory]

    def of_craft(self, craft_id: uuid.UUID | None) -> Placement:
        craft = self.live(craft_id)
        if craft is None:
            return NO_PLACE
        _, family, category = self.of_family(craft.subCategoryId)
        return craft.slug, family, category

    def live(self, craft_id: uuid.UUID | None) -> Craft | None:
        craft = self.crafts.get(craft_id) if craft_id is not None else None
        for _ in range(MERGE_HOPS):
            if craft is None or craft.status != MERGED or craft.mergedIntoId is None:
                break
            craft = self.crafts.get(craft.mergedIntoId)
        return craft if craft is not None and craft.status != MERGED else None

    def of_family(self, family_id: uuid.UUID | None) -> Placement:
        family = self.families.get(family_id) if family_id is not None else None
        if family is None:
            return NO_PLACE
        category = self.categories.get(family.categoryId)
        return None, family.slug, category.slug if category is not None else None

    def shown_crafts(self) -> list[Craft]:
        return sorted((c for c in self.crafts.values() if c.status != MERGED), key=lambda c: c.slug)


async def craft_lookup(session: AsyncSession) -> CraftLookup:
    crafts = (await session.scalars(select(Craft).options(defer(Craft.descriptorEmbedding)))).all()
    families = (await session.scalars(select(CraftSubCategory))).all()
    categories = (await session.scalars(select(CraftCategory))).all()
    return CraftLookup(
        crafts={craft.id: craft for craft in crafts},
        families={family.id: family for family in families},
        categories={category.id: category for category in categories},
    )


async def craft_rows(session: AsyncSession, lookup: CraftLookup, *, site: str) -> list[Row]:
    found = select(CuratedCraft.craftId, CuratedCraft.version, CuratedCraft.curatedAt, CuratedCraft.coverage)
    curated = {row.craftId: row for row in (await session.execute(found)).all()}
    wikidata = wikidata_links(json.loads(CRAFT_WIKIDATA_FILE.read_text(encoding="utf-8")))
    rows: list[Row] = []
    for craft in lookup.shown_crafts():
        _, family, category = lookup.of_family(craft.subCategoryId)
        page = curated.get(craft.id)
        link = wikidata.get(craft.slug)
        rows.append(
            {
                "slug": craft.slug,
                "name": craft.name,
                "category": category,
                "family": family,
                "states_of_origin": list(craft.stateOfOrigin or []),
                "states_of_practice": list(craft.stateOfPractice or []),
                "gi_status": craft.giStatus,
                "status": craft.status,
                "wikidata": link.qid if link is not None else None,
                "craft_code": craft.craftCode,
                "page_url": f"{site}/crafts/{craft.slug}",
                "curated_version": page.version if page is not None else None,
                "curated_at": stamp_of(page.curatedAt) if page is not None else None,
                "coverage": page.coverage if page is not None else None,
            }
        )
    return rows


async def craft_place_rows(session: AsyncSession, lookup: CraftLookup) -> list[Row]:
    shown = {craft.id: craft.slug for craft in lookup.shown_crafts()}
    rows = await session.execute(
        select(CraftLocation, AdminState.name, AdminDistrict.name)
        .outerjoin(AdminState, AdminState.lgd == CraftLocation.stateLgd)
        .outerjoin(AdminDistrict, AdminDistrict.lgd == CraftLocation.districtLgd)
        .where(CraftLocation.craftId.in_(list(shown)) if shown else CraftLocation.craftId.is_(None))
    )
    placed = [
        {
            "id": str(place.id),
            "craft": shown[place.craftId],
            "label": place.placeLabel,
            "state": state,
            "state_lgd": place.stateLgd,
            "district": district,
            "district_lgd": place.districtLgd,
            "precision": place.precision,
            "role": place.role,
            "level": place.evidenceLevel,
        }
        for place, state, district in rows.all()
    ]
    return sorted(placed, key=lambda row: (row["craft"], row["id"]))


async def category_rows(session: AsyncSession, lookup: CraftLookup, *, site: str) -> list[Row]:
    found = select(CuratedCategory.categoryId, CuratedCategory.version, CuratedCategory.curatedAt)
    curated = {row.categoryId: row for row in (await session.execute(found)).all()}
    ordered = sorted(lookup.categories.values(), key=lambda category: (category.sortOrder, category.slug))
    return [
        {
            "slug": category.slug,
            "name": category.name,
            "sort_order": category.sortOrder,
            "page_url": f"{site}/categories/{category.slug}",
            "curated_version": curated[category.id].version if category.id in curated else None,
            "curated_at": stamp_of(curated[category.id].curatedAt) if category.id in curated else None,
        }
        for category in ordered
    ]


def family_rows(lookup: CraftLookup) -> list[Row]:
    rows = [
        {
            "slug": family.slug,
            "name": family.name,
            "category": lookup.categories[family.categoryId].slug,
            "sort_order": family.sortOrder,
        }
        for family in lookup.families.values()
        if family.categoryId in lookup.categories
    ]
    return sorted(rows, key=lambda row: (row["category"], row["sort_order"], row["slug"]))
