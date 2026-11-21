from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AdminDistrict
from app.models.enums import DISTRICT_PLACE_PREFIX
from app.research.knowledge_api import ComponentSubject

from .component_places import PlacesHeld
from .component_places_held import places_held
from .open_work_subjects import CATEGORY, WorkSubject

__all__ = ["PLACE_KEYS_MAX", "district_key", "page_keys"]

PLACE_KEYS_MAX = 40
CRAFT_KIND = "CRAFT"
PLACE_KIND = "PLACE"


def district_key(lgd: int) -> str:
    return f"{DISTRICT_PLACE_PREFIX}:{lgd}"


async def page_keys(session: AsyncSession, subject: WorkSubject) -> list[ComponentSubject]:
    if subject.kind == CATEGORY:
        return []
    held = (await places_held(session, [subject.id])).get(subject.id, PlacesHeld())
    districts = await _districts(session, sorted(held.districts)[:PLACE_KEYS_MAX])
    return [
        ComponentSubject(kind=CRAFT_KIND, key=subject.slug, name=subject.name),
        *(ComponentSubject(kind=PLACE_KIND, key=district_key(lgd), name=name) for lgd, name in districts),
    ]


async def _districts(session: AsyncSession, lgds: Sequence[int]) -> list[tuple[int, str]]:
    if not lgds:
        return []
    rows = await session.execute(
        select(AdminDistrict.lgd, AdminDistrict.name)
        .where(AdminDistrict.lgd.in_(list(lgds)))
        .order_by(AdminDistrict.name, AdminDistrict.lgd)
    )
    return [(int(lgd), str(name)) for lgd, name in rows.all()]
