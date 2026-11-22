from __future__ import annotations

import logging
import uuid
from collections.abc import Awaitable, Callable, Iterable, Mapping
from typing import Any

from app.composer.timeline_map import choose_timeline
from app.core.errors import ExternalFailure, NotConfigured
from app.geo.datasets import region_dataset
from app.research.blocks_journey import IMAGE_ZOOM_LEVELS, ZoomLevel, ZoomStoryBlock
from app.research.datasets import BOUNDARY_DATASET_CODE
from app.research.image_relevance import ClaimText
from app.research.vocabulary import FACT_LEVELS
from app.science.records import KnownClaim
from app.sources.reference.wikidata import WikidataAdapter

from .builder_evidence import section_facts
from .builder_interface import BuildAsk, BuilderTools, Built
from .craft_matter import CraftMatter, MaterialRows, craft_matter
from .matter_builders import MOLECULE_CANDIDATES_MAX, molecule_candidates
from .molecule_conformers import ConformerCache, ConformerObjects, ConformerSource, live_pubchem
from .object_store import media_bucket
from .place_register import KnownPointsLoader, stored_known_points
from .region_records import dataset_records
from .supply_places import PlaceFinder, named_places
from .timeline_story import ShownPlace, TimelineEntries, timeline_block, timeline_entries, timeline_offer
from .zoom_pictures import LevelPicture, PicturesAsk, ZoomPictures, fibre_named, zoom_pictures
from .zoom_story import (
    Captions,
    ZoomGround,
    district_level,
    molecule_level,
    picture_level_of,
    zoom_ground,
    zoom_story_block,
)

__all__ = [
    "TIMELINE_MAP_WAIT_SECONDS",
    "ZOOM_FACTS_MAX",
    "ZOOM_STORY_WAIT_SECONDS",
    "TimelineMapBuilder",
    "ZoomStoryBuilder",
]

logger = logging.getLogger(__name__)

ZOOM_STORY_WAIT_SECONDS = 20.0
TIMELINE_MAP_WAIT_SECONDS = 30.0
ZOOM_FACTS_MAX = 16
FIBRE_KIND = "FIBRE"

Bucket = Callable[[], ConformerObjects | None]
PubChem = Callable[[], Awaitable[ConformerSource]]
Pictures = Callable[[], Awaitable[ZoomPictures]]
Places = Callable[[], Awaitable[PlaceFinder]]


class ZoomStoryBuilder:
    def __init__(
        self,
        tools: BuilderTools,
        *,
        bucket: Bucket | None = None,
        pubchem: PubChem | None = None,
        pictures: Pictures | None = None,
    ) -> None:
        self._tools = tools
        self._bucket = bucket or media_bucket
        self._pubchem = pubchem or (lambda: live_pubchem(tools.live, tools.sessions))
        self._pictures = pictures or (lambda: zoom_pictures(tools.sessions, tools.live))

    async def build(self, ask: BuildAsk) -> Built:
        craft = ask.request.craft
        facts = section_facts(ask.blocks, ask.cited, limit=ZOOM_FACTS_MAX)
        if craft is None or not facts:
            return Built()
        matter = await craft_matter(self._tools.sessions, craft)
        if matter is None:
            return Built()
        fibres = [m for m in matter.materials if m.kind == FIBRE_KIND]
        own = _own_claims(matter, [*fibres, *_compound_materials(matter)])
        async with self._tools.sessions() as session:
            offered = [claim.id for claim in (*facts, *own)]
            ground = await zoom_ground(session, craft.slug, mode=ask.request.mode, offered=offered)
        if ground is None:
            return Built()
        captions = Captions.of(facts, ground.claims, own)
        levels: list[ZoomLevel | None] = [district_level(ground, captions)]
        fibre = fibre_named(surface for material in fibres for surface in material.surfaces())
        pictures = await self._level_pictures(_pictures_ask(craft.name, captions, fibre, ground))
        levels += [
            picture_level_of(pictures[level], captions) for level in IMAGE_ZOOM_LEVELS if level in pictures
        ]
        levels.append(await self._molecule(ask, matter, captions))
        block = zoom_story_block(levels, ground.boundary, block_id=f"{ask.section.id}.zoom")
        if block is None:
            return Built()
        return Built((block,), _zoom_sources(block, ask, ground, matter))

    async def _level_pictures(self, ask: PicturesAsk) -> dict[str, LevelPicture]:
        try:
            return await (await self._pictures()).pictures(ask)
        except (ExternalFailure, NotConfigured) as failure:
            logger.warning("the zoom shows no pictures: %s", failure)
            return {}

    async def _molecule(self, ask: BuildAsk, matter: CraftMatter, captions: Captions) -> ZoomLevel | None:
        objects = self._bucket()
        if objects is None:
            return None
        named = [c for c in molecule_candidates(matter, ask.blocks) if captions.names(c.compound.name)]
        if not named:
            return None
        cache = ConformerCache(objects=objects, source=await self._pubchem())
        for linked in named[:MOLECULE_CANDIDATES_MAX]:
            if await cache.conformer(linked.pubchem_cid) is not None:
                return molecule_level(linked, captions)
        return None


class TimelineMapBuilder:
    def __init__(
        self, tools: BuilderTools, *, places: Places | None = None, known: KnownPointsLoader | None = None
    ) -> None:
        self._tools = tools
        self._places = places or (lambda: tools.live.reference(tools.sessions, WikidataAdapter))
        self._known = known or stored_known_points(tools.sessions)

    async def build(self, ask: BuildAsk) -> Built:
        offer = timeline_offer(ask.blocks, ask.cited)
        if offer is None:
            return Built()
        async with self._tools.sessions() as session:
            record = (await dataset_records(session, [BOUNDARY_DATASET_CODE])).get(BOUNDARY_DATASET_CODE)
        if record is None:
            logger.warning(
                "no %s dataset row to draw beneath a timeline; none is built", BOUNDARY_DATASET_CODE
            )
            return Built()
        entries = timeline_entries(offer, await choose_timeline(self._tools.plan_model, offer.brief()))
        if not entries.points and not entries.routes:
            return Built()
        craft = ask.request.craft.slug if ask.request.craft is not None else None
        places = await self._placed(entries, craft)
        block = timeline_block(entries, places, region_dataset(record), block_id=f"{ask.section.id}.timeline")
        return Built((block,)) if block is not None else Built()

    async def _placed(self, entries: TimelineEntries, craft: str | None) -> dict[str, ShownPlace]:
        named = entries.places()
        known = await self._known(craft, [name for name, _ in named.values()])
        rest = {key: place for key, place in named.items() if not known.placed(key)}
        found: dict[str, ShownPlace] = {**known.curated, **known.register}
        try:
            return {**await named_places(await self._places(), rest), **found}
        except (ExternalFailure, NotConfigured) as failure:
            logger.warning("timeline places beyond the register are listed without pins: %s", failure)
            return found


def _compound_materials(matter: CraftMatter) -> list[MaterialRows]:
    return [material for material in matter.materials if material.compound is not None]


def _own_claims(matter: CraftMatter, materials: Iterable[MaterialRows]) -> list[KnownClaim]:
    found: dict[uuid.UUID, KnownClaim] = {}
    for material in materials:
        for claim_id in (claim_id for use in material.uses for claim_id in use.claim_ids):
            claim = matter.records.claims.get(claim_id)
            if claim is not None and claim.level in FACT_LEVELS and claim.citations:
                found.setdefault(claim.id, claim)
    return list(found.values())


def _pictures_ask(craft_name: str, captions: Captions, fibre: str | None, ground: ZoomGround) -> PicturesAsk:
    claims = tuple(ClaimText(claim.id, claim.text) for claim in captions.claims.values())
    return PicturesAsk(craft_name=craft_name, claims=claims, fibre=fibre, stored=ground.pictures)


def _zoom_sources(
    block: ZoomStoryBlock, ask: BuildAsk, ground: ZoomGround, matter: CraftMatter
) -> dict[str, Mapping[str, Any]]:
    stored = {sid: ref.model_dump(mode="json", by_alias=True) for sid, ref in matter.records.sources.items()}
    known = {**stored, **matter.record_sources, **ground.sources}
    return {
        sid: known[sid] for sid in block.cited_source_ids() if sid not in ask.cited.sources and sid in known
    }
