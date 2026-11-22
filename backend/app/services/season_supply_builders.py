from __future__ import annotations

import logging
import uuid
from collections.abc import Awaitable, Callable, Collection, Mapping, Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.composer.supply_map import choose_supply_links
from app.core.errors import ExternalFailure, NotConfigured
from app.geo.rainfall import DistrictRainfall
from app.models import Concept
from app.research.blocks_place import SupplyLink
from app.research.retrieval import EVERY_CHUNK_ACLS
from app.science.records import ProcessRecords
from app.sources.reference.wikidata import WikidataAdapter

from .builder_evidence import section_facts, sources_beyond
from .builder_interface import BuildAsk, BuilderTools, Built
from .craft_matter import craft_matter
from .craft_process import process_records
from .knowledge_view import resolve_craft
from .monthly_rain import district_rainfall
from .place_offers import district_refs, mapped_districts
from .season_rows import SeasonOffer, rain_only_block, season_facts, seasons_block, stage_claims
from .supply_links import OriginPlace, supply_links, supply_map_block, supply_offer
from .supply_places import PlaceFinder, origin_places

__all__ = [
    "RAIN_ONLY_FIELDS",
    "SUPPLY_MAP_WAIT_SECONDS",
    "SeasonsBuilder",
    "SupplyMapBuilder",
    "craft_rainfall",
]

logger = logging.getLogger(__name__)

SUPPLY_MAP_WAIT_SECONDS = 30.0
RAIN_ONLY_FIELDS = frozenset({"CLIMATE"})

Places = Callable[[], Awaitable[PlaceFinder]]


@dataclass(frozen=True)
class _StoredSeasons:
    records: ProcessRecords
    rainfall: DistrictRainfall | None
    subjects: Mapping[uuid.UUID, str]


class SeasonsBuilder:
    def __init__(self, tools: BuilderTools) -> None:
        self._tools = tools

    async def build(self, ask: BuildAsk) -> Built:
        craft = ask.request.craft
        if craft is None:
            return Built()
        facts = section_facts(ask.blocks, ask.cited)
        concepts = {fact.id: view.concept_id for fact in facts if (view := ask.cited.views.get(fact.id))}
        async with self._tools.sessions() as session:
            stored = await _stored_seasons(session, craft.slug, concepts)
        if stored is None:
            return Built()
        offer = SeasonOffer(
            stages=stage_claims(stored.records),
            facts=season_facts(facts, stored.subjects),
            rainfall=stored.rainfall,
        )
        block_id = f"{ask.section.id}.seasons"
        block = seasons_block(offer, block_id=block_id)
        if block is None and ask.section.discipline in RAIN_ONLY_FIELDS:
            block = rain_only_block(stored.rainfall, block_id=block_id)
        if block is None:
            return Built()
        return Built((block,), sources_beyond([block], stored.records.sources, ask.cited))


class SupplyMapBuilder:
    def __init__(self, tools: BuilderTools, *, places: Places | None = None) -> None:
        self._tools = tools
        self._places = places or (lambda: tools.live.reference(tools.sessions, WikidataAdapter))

    async def build(self, ask: BuildAsk) -> Built:
        if ask.request.craft is None:
            return Built()
        matter = await craft_matter(self._tools.sessions, ask.request.craft)
        offer = supply_offer(matter, ask.blocks, ask.cited) if matter is not None else None
        if matter is None or offer is None:
            return Built()
        block_id = f"{ask.section.id}.supply"
        choices = await choose_supply_links(self._tools.plan_model, offer.brief())
        links = supply_links(offer, choices, block_id=block_id)
        if not links:
            return Built()
        block = supply_map_block(links, await self._placed(links), block_id=block_id)
        if block is None:
            return Built()
        return Built((block,), sources_beyond([block], matter.records.sources, ask.cited))

    async def _placed(self, links: Sequence[SupplyLink]) -> dict[str, OriginPlace]:
        try:
            return await origin_places(await self._places(), links)
        except (ExternalFailure, NotConfigured) as failure:
            logger.warning("supply origins are listed without places: %s", failure)
            return {}


async def craft_rainfall(session: AsyncSession, district_lgds: Sequence[int]) -> DistrictRainfall | None:
    named = await district_refs(session, district_lgds)
    for district_lgd in district_lgds:
        district = named.get(district_lgd)
        if district is None:
            logger.warning("district %s has no register row, so its rainfall is not shown", district_lgd)
            continue
        found = await district_rainfall(session, district)
        if found is not None:
            return found
    return None


async def _stored_seasons(
    session: AsyncSession, craft_slug: str, concepts: Mapping[uuid.UUID, uuid.UUID | None]
) -> _StoredSeasons | None:
    craft = await resolve_craft(session, craft_slug)
    if craft is None:
        return None
    records = await process_records(session, craft, acls=EVERY_CHUNK_ACLS)
    rainfall = await craft_rainfall(session, await mapped_districts(session, craft))
    names = await _concept_names(session, {cid for cid in concepts.values() if cid is not None})
    subjects = {claim: names[cid] for claim, cid in concepts.items() if cid is not None and cid in names}
    return _StoredSeasons(records, rainfall, subjects)


async def _concept_names(session: AsyncSession, concept_ids: Collection[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not concept_ids:
        return {}
    rows = await session.execute(select(Concept.id, Concept.name).where(Concept.id.in_(list(concept_ids))))
    return dict(rows.tuples().all())
