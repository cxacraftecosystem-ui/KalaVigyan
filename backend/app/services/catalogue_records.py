from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from pydantic import TypeAdapter, ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.geo.places import DISTRICT_PRECISIONS
from app.models import (
    Concept,
    CraftGiRecord,
    CraftLocation,
    CuratedCraft,
    Material,
    Process,
    ProcessStage,
    Term,
    TermCraft,
)
from app.models.science import live_process
from app.research.craft_catalogue import CatalogueDepth, CatalogueHero
from app.research.retrieval import VISIBLE_SENSITIVITY

from .catalogue_rows import CatalogueExtras, ConceptLink, curated_hero, material_link
from .craft_claim_counts import craft_claim_counts
from .craft_page_records import PAGE_MODE
from .curated_index import CuratedPage, IndexPicture
from .media_ref_store import stored_media_refs

__all__ = ["load_catalogue_extras"]

logger = logging.getLogger(__name__)

PICTURES_KEY = CuratedPage.model_fields["pictures"].alias or "pictures"
PICTURES = TypeAdapter(list[IndexPicture])

CuratedPictures = dict[str, tuple[str, list[IndexPicture]]]


async def load_catalogue_extras(session: AsyncSession) -> CatalogueExtras:
    places = await _place_counts(session)
    curated = await _curated_pictures(session)
    counts = await craft_claim_counts(session, mode=PAGE_MODE)
    claims = {str(craft_id): count for craft_id, count in counts.items()}
    return CatalogueExtras(
        depth=_depths(claims, await _stage_counts(session), places, curated),
        heroes=await _heroes(session, curated),
        gi_years=await _gi_years(session),
        located=frozenset(places),
        concepts=await _concept_links(session),
    )


def _depths(
    claims: Mapping[str, int], stages: Mapping[str, int], places: Mapping[str, int], curated: CuratedPictures
) -> dict[str, CatalogueDepth]:
    crafts = set(claims) | set(stages) | set(places) | set(curated)
    return {
        craft_id: CatalogueDepth(
            coverage=curated[craft_id][0] if craft_id in curated else None,
            claims=claims.get(craft_id, 0),
            stages=stages.get(craft_id, 0),
            pictures=len(curated[craft_id][1]) if craft_id in curated else 0,
            places=places.get(craft_id, 0),
        )
        for craft_id in sorted(crafts)
    }


async def _curated_pictures(session: AsyncSession) -> CuratedPictures:
    rows = await session.execute(
        select(CuratedCraft.craftId, CuratedCraft.coverage, CuratedCraft.page[PICTURES_KEY])
    )
    found: CuratedPictures = {}
    for craft_id, coverage, pictures in rows.all():
        try:
            found[str(craft_id)] = (coverage, PICTURES.validate_python(pictures or []))
        except ValidationError:
            logger.warning("craft %s has curated pictures that no longer meet their model", craft_id)
            found[str(craft_id)] = (coverage, [])
    return found


async def _heroes(session: AsyncSession, curated: CuratedPictures) -> dict[str, CatalogueHero]:
    wanted = [picture.media_ref_id for _coverage, pictures in curated.values() for picture in pictures]
    media = await stored_media_refs(session, list(dict.fromkeys(wanted)))
    heroes = {craft_id: curated_hero(pictures, media) for craft_id, (_coverage, pictures) in curated.items()}
    return {craft_id: hero for craft_id, hero in heroes.items() if hero is not None}


async def _stage_counts(session: AsyncSession) -> dict[str, int]:
    per_process = (
        select(ProcessStage.processId.label("processId"), func.count(ProcessStage.id).label("stages"))
        .group_by(ProcessStage.processId)
        .subquery()
    )
    rows = await session.execute(
        select(Process.craftId, func.max(per_process.c.stages))
        .join(per_process, per_process.c.processId == Process.id)
        .where(live_process())
        .group_by(Process.craftId)
    )
    return {str(craft_id): int(count) for craft_id, count in rows.all()}


async def _place_counts(session: AsyncSession) -> dict[str, int]:
    rows = await session.execute(
        select(CraftLocation.craftId, func.count(CraftLocation.id))
        .where(CraftLocation.precision.in_(DISTRICT_PRECISIONS))
        .group_by(CraftLocation.craftId)
    )
    return {str(craft_id): int(count) for craft_id, count in rows.all()}


async def _gi_years(session: AsyncSession) -> dict[str, int]:
    records = await session.execute(
        select(CraftGiRecord.craftId, CraftGiRecord.registeredOn).where(
            CraftGiRecord.registeredOn.is_not(None)
        )
    )
    return {str(craft_id): int(str(registered)[:4]) for craft_id, registered in records.all()}


async def _concept_links(session: AsyncSession) -> tuple[ConceptLink, ...]:
    terms = await session.execute(
        select(Term.key, Term.label, Term.aliases, Term.localNames, TermCraft.craftId)
        .join(TermCraft, TermCraft.termId == Term.id)
        .order_by(Term.key, TermCraft.craftId)
    )
    links = [_term_link(row) for row in terms.all()]
    materials = await session.execute(
        select(Material.name, Concept.craftId)
        .join(Concept, Concept.id == Material.conceptId)
        .where(Concept.craftId.is_not(None), Concept.sensitivity == VISIBLE_SENSITIVITY)
        .order_by(Material.name, Concept.craftId)
    )
    found = (material_link(name, str(craft_id)) for name, craft_id in materials.all())
    return (*links, *(link for link in found if link is not None))


def _term_link(row: Any) -> ConceptLink:
    key, label, aliases, local_names, craft_id = row
    return ConceptLink(
        key=key, label=label, names=(*(aliases or ()), *(local_names or ())), craft_id=str(craft_id)
    )
