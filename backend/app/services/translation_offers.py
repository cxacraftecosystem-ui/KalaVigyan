from __future__ import annotations

from collections.abc import Mapping, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Craft
from app.research.translation_regions import HINDI, offered_languages

__all__ = ["CATEGORY", "home_states", "page_offers"]

CATEGORY = "category"


async def home_states(session: AsyncSession, slugs: Sequence[str]) -> dict[str, tuple[str, ...]]:
    if not slugs:
        return {}
    rows = await session.execute(select(Craft.slug, Craft.stateOfOrigin).where(Craft.slug.in_(slugs)))
    return {str(slug): tuple(states or ()) for slug, states in rows.all()}


def page_offers(kind: str, slug: str, states: Mapping[str, Sequence[str]]) -> tuple[str, ...]:
    if kind == CATEGORY:
        return (HINDI,)
    return offered_languages(states.get(slug, ()))
