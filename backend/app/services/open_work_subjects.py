from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import ColumnElement, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput
from app.data.craft_master_loader import ACTIVE
from app.data.curation_scopes import is_family
from app.models import Craft, CraftCategory, CraftSubCategory, CuratedCategory, CuratedCraft
from app.research.category_page import category_path
from app.research.open_work import SUBJECT_KINDS, TaskSubject

__all__ = [
    "CATEGORY",
    "WorkSubject",
    "craft_subject",
    "craft_subjects",
    "is_family",
    "subject_by_key",
    "work_subjects",
]

CRAFT, FAMILY, CATEGORY = SUBJECT_KINDS
GI = "GI"
UNKNOWN = "No {kind} has the slug {slug}; find_crafts gives the slugs of crafts and families."
WRONG_KIND = "{slug} is a {found}, not a {kind}; filter by {found}."


@dataclass(frozen=True)
class WorkSubject:
    id: uuid.UUID
    kind: str
    slug: str
    name: str
    gi: bool
    curated: bool = False

    def task_subject(self, site: str) -> TaskSubject:
        path = category_path(self.slug) if self.kind == CATEGORY else f"/crafts/{self.slug}"
        return TaskSubject(kind=self.kind, slug=self.slug, name=self.name, page_url=f"{site}{path}")


async def work_subjects(session: AsyncSession, subject: tuple[str, str] | None) -> list[WorkSubject]:
    if subject is None:
        return [*await _crafts(session), *await _categories(session)]
    kind, slug = subject
    if kind == CATEGORY:
        category = await _category(session, slug)
        members = await _crafts(session, CraftSubCategory.categoryId == category.id)
        return [category, *members]
    found = await _craft(session, slug, kind)
    if kind == CRAFT:
        return [found]
    row = await session.scalar(select(Craft.subCategoryId).where(Craft.id == found.id))
    members = [] if row is None else await _crafts(session, Craft.subCategoryId == row, Craft.id != found.id)
    return [found, *members]


async def subject_by_key(session: AsyncSession, kind: str, slug: str) -> WorkSubject:
    if kind == CATEGORY:
        return await _category(session, slug)
    return await _craft(session, slug, kind)


async def craft_subject(session: AsyncSession, slug: str) -> WorkSubject:
    rows = await _crafts(session, Craft.slug == slug)
    if not rows:
        raise InvalidInput(UNKNOWN.format(kind=CRAFT, slug=slug))
    return rows[0]


async def craft_subjects(session: AsyncSession, slugs: Sequence[str]) -> list[WorkSubject]:
    if not slugs:
        return []
    return await _crafts(session, Craft.slug.in_(list(dict.fromkeys(slugs))))


async def _crafts(session: AsyncSession, *conditions: ColumnElement[bool]) -> list[WorkSubject]:
    rows = await session.execute(
        select(
            Craft.id,
            Craft.slug,
            Craft.name,
            Craft.giStatus,
            Craft.isCatchAll,
            Craft.stateOfPractice,
            CuratedCraft.craftId.label("curated"),
        )
        .outerjoin(CraftSubCategory, CraftSubCategory.id == Craft.subCategoryId)
        .outerjoin(CuratedCraft, CuratedCraft.craftId == Craft.id)
        .where(Craft.status == ACTIVE, *conditions)
        .order_by(Craft.slug)
    )
    return [_craft_subject(row) for row in rows.all()]


async def _craft(session: AsyncSession, slug: str, kind: str) -> WorkSubject:
    found = await craft_subject(session, slug)
    if found.kind != kind:
        raise InvalidInput(WRONG_KIND.format(slug=slug, found=found.kind, kind=kind))
    return found


async def _categories(session: AsyncSession, *conditions: ColumnElement[bool]) -> list[WorkSubject]:
    rows = await session.execute(
        select(CraftCategory.id, CraftCategory.slug, CraftCategory.name, CuratedCategory.categoryId)
        .outerjoin(CuratedCategory, CuratedCategory.categoryId == CraftCategory.id)
        .where(*conditions)
        .order_by(CraftCategory.sortOrder)
    )
    return [
        WorkSubject(row[0], CATEGORY, row[1], row[2], gi=False, curated=row[3] is not None)
        for row in rows.all()
    ]


async def _category(session: AsyncSession, slug: str) -> WorkSubject:
    found = await _categories(session, CraftCategory.slug == slug)
    if not found:
        raise InvalidInput(f"No category has the slug {slug}.")
    return found[0]


def _craft_subject(row: Any) -> WorkSubject:
    kind = FAMILY if is_family(bool(row.isCatchAll), row.stateOfPractice or ()) else CRAFT
    return WorkSubject(
        row.id, kind, row.slug, row.name, gi=row.giStatus == GI, curated=row.curated is not None
    )
