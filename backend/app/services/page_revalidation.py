from __future__ import annotations

import logging
import uuid
from collections.abc import Collection, Iterable
from dataclasses import dataclass
from typing import Any

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
    category_targets,
    craft_targets,
    revalidation_request,
)

__all__ = [
    "MISSES_BEFORE_GIVING_UP",
    "REVALIDATE_TARGETS_MAX",
    "REVALIDATE_TIMEOUT_SECONDS",
    "UNSET_SECRET",
    "BatchedRefresh",
    "claim_owners",
    "craft_owners",
    "merged_owners",
    "nightly_refresh",
    "owner_batches",
    "refresh_in_batches",
    "refresh_pages",
]

logger = logging.getLogger(__name__)

REVALIDATE_TIMEOUT_SECONDS = 5.0
REVALIDATE_TARGETS_MAX = 40
MISSES_BEFORE_GIVING_UP = 3
UNSET_SECRET = "WEB_REVALIDATE_SECRET is not set"
CONCEPT_SUBJECT = "CONCEPT"
REFRESHED = 200
CRAFT_OWNER, CATEGORY_OWNER = "craft", "category"


@dataclass(frozen=True)
class BatchedRefresh:
    refreshed: PageOwners
    unrefreshed: PageOwners
    batches: int
    tried: int


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
    sent = await refresh_in_batches(owners, settings=settings, transport=transport)
    return sent.unrefreshed.empty


def owner_batches(owners: PageOwners, *, most: int = REVALIDATE_TARGETS_MAX) -> list[PageOwners]:
    batches: list[list[tuple[str, str]]] = []
    room = 0
    for kind, slug in _owned(owners):
        size = _target_count(kind, slug)
        if size > most:
            raise ValueError(
                f"the {kind} {slug} names {size} pages and tags, more than one request takes ({most})"
            )
        if not batches or size > room:
            batches.append([])
            room = most
        batches[-1].append((kind, slug))
        room -= size
    return [_owners_of(batch) for batch in batches]


async def nightly_refresh(
    owners: PageOwners,
    *,
    settings: Settings | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict[str, Any]:
    pages = len(owners.crafts) + len(owners.categories)
    if owners.empty:
        return {"ok": True, "pages": 0, "refreshed": 0, "unrefreshed": []}
    if not ((settings or get_settings()).web_revalidate_secret or "").strip():
        return {"ok": True, "pages": pages, "refreshed": 0, "unrefreshed": [], "reason": UNSET_SECRET}
    sent = await refresh_in_batches(owners, settings=settings, transport=transport)
    left = [*sent.unrefreshed.crafts, *sent.unrefreshed.categories]
    return {"ok": not left, "pages": pages, "refreshed": pages - len(left), "unrefreshed": left}


async def refresh_in_batches(
    owners: PageOwners,
    *,
    settings: Settings | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> BatchedRefresh:
    refreshed: list[PageOwners] = []
    unrefreshed: list[PageOwners] = []
    batches = owner_batches(owners)
    tried = misses = 0
    for batch in batches:
        done = False
        if misses < MISSES_BEFORE_GIVING_UP:
            tried += 1
            done = await _refresh_batch(batch, settings=settings, transport=transport)
        misses = 0 if done else misses + 1
        (refreshed if done else unrefreshed).append(batch)
    return BatchedRefresh(merged_owners(*refreshed), merged_owners(*unrefreshed), len(batches), tried)


async def _refresh_batch(
    owners: PageOwners,
    *,
    settings: Settings | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> bool:
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


def _owned(owners: PageOwners) -> list[tuple[str, str]]:
    return [
        *((CRAFT_OWNER, slug) for slug in _distinct(owners.crafts)),
        *((CATEGORY_OWNER, slug) for slug in _distinct(owners.categories)),
    ]


def _target_count(kind: str, slug: str) -> int:
    paths, tags = craft_targets(slug) if kind == CRAFT_OWNER else category_targets(slug)
    return len(paths) + len(tags)


def _owners_of(batch: list[tuple[str, str]]) -> PageOwners:
    return PageOwners(
        crafts=tuple(slug for kind, slug in batch if kind == CRAFT_OWNER),
        categories=tuple(slug for kind, slug in batch if kind == CATEGORY_OWNER),
    )
