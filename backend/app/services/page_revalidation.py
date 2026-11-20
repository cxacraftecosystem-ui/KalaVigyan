from __future__ import annotations

import logging
import uuid
from collections.abc import Collection, Iterable

import httpx
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.data.curation_scopes import is_family
from app.models import Claim, Concept, Craft, CraftCategory, CraftSubCategory, CuratedCategoryClaim
from app.research.page_revalidation import (
    REVALIDATE_ROUTE,
    REVALIDATE_SECRET_HEADER,
    PageOwners,
    revalidation_request,
)

__all__ = [
    "REVALIDATE_TIMEOUT_SECONDS",
    "claim_owners",
    "craft_owners",
    "merged_owners",
    "refresh_pages",
]

logger = logging.getLogger(__name__)

REVALIDATE_TIMEOUT_SECONDS = 5.0
CONCEPT_SUBJECT = "CONCEPT"
REFRESHED = 200


async def craft_owners(session: AsyncSession, craft_ids: Collection[uuid.UUID]) -> PageOwners:
    if not craft_ids:
        return PageOwners()
    rows = (
        await session.execute(select(Craft.slug, Craft.subCategoryId).where(Craft.id.in_(list(craft_ids))))
    ).all()
    owned = await _sub_category_owners(session, {row.subCategoryId for row in rows if row.subCategoryId})
    return merged_owners(PageOwners(crafts=tuple(row.slug for row in rows)), owned)


async def claim_owners(session: AsyncSession, claim_ids: Collection[uuid.UUID]) -> PageOwners:
    if not claim_ids:
        return PageOwners()
    ids = list(claim_ids)
    concepts = (
        await session.execute(
            select(Concept.craftId, Concept.subCategoryId)
            .join(Claim, and_(Claim.subjectType == CONCEPT_SUBJECT, Claim.subjectId == Concept.id))
            .where(Claim.id.in_(ids))
        )
    ).all()
    categories = await session.scalars(
        select(CraftCategory.slug)
        .join(CuratedCategoryClaim, CuratedCategoryClaim.categoryId == CraftCategory.id)
        .where(CuratedCategoryClaim.claimId.in_(ids))
    )
    return merged_owners(
        await craft_owners(session, {row.craftId for row in concepts if row.craftId}),
        await _sub_category_owners(session, {row.subCategoryId for row in concepts if row.subCategoryId}),
        PageOwners(categories=tuple(categories.all())),
    )


def merged_owners(*owners: PageOwners) -> PageOwners:
    return PageOwners(
        crafts=_distinct(slug for each in owners for slug in each.crafts),
        categories=_distinct(slug for each in owners for slug in each.categories),
    )


async def refresh_pages(
    owners: PageOwners,
    *,
    settings: Settings | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> bool:
    if owners.empty:
        return False
    chosen = settings or get_settings()
    secret = (chosen.web_revalidate_secret or "").strip()
    if not secret:
        logger.info("WEB_REVALIDATE_SECRET is not set, so signed-out pages refresh on their own schedule")
        return False
    url = f"{chosen.public_web_url.rstrip('/')}{REVALIDATE_ROUTE}"
    body = revalidation_request(owners).model_dump(mode="json")
    try:
        async with httpx.AsyncClient(transport=transport, timeout=REVALIDATE_TIMEOUT_SECONDS) as client:
            response = await client.post(url, json=body, headers={REVALIDATE_SECRET_HEADER: secret})
    except httpx.HTTPError as error:
        logger.warning("signed-out pages of %s were not refreshed: %s", _named(owners), type(error).__name__)
        return False
    if response.status_code != REFRESHED:
        logger.warning("signed-out pages of %s were not refreshed: %s", _named(owners), response.status_code)
        return False
    return True


async def _sub_category_owners(session: AsyncSession, sub_category_ids: set[uuid.UUID]) -> PageOwners:
    if not sub_category_ids:
        return PageOwners()
    subs = list(sub_category_ids)
    members = await session.execute(
        select(Craft.slug, Craft.isCatchAll, Craft.stateOfPractice).where(Craft.subCategoryId.in_(subs))
    )
    families = [
        row.slug for row in members.all() if is_family(bool(row.isCatchAll), row.stateOfPractice or ())
    ]
    categories = await session.scalars(
        select(CraftCategory.slug)
        .join(CraftSubCategory, CraftSubCategory.categoryId == CraftCategory.id)
        .where(CraftSubCategory.id.in_(subs))
    )
    return PageOwners(crafts=tuple(families), categories=tuple(categories.all()))


def _distinct(slugs: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted(set(slugs)))


def _named(owners: PageOwners) -> str:
    return ", ".join((*owners.crafts, *owners.categories))
