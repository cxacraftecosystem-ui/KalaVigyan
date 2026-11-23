from __future__ import annotations

import logging
import uuid
from collections.abc import Mapping

from sqlalchemy.ext.asyncio import AsyncSession

from app.composer.region_story import choose_region_story
from app.geo.layers import map_layer
from app.geo.section_layers import map_layer_block
from app.models import Craft
from app.models.enums import EXPLAINER_DEPTHS
from app.research.blocks import stated_texts
from app.research.knowledge_pieces import placed_block
from app.research.piece_reuse import usable_region_stories
from app.research.retrieval import EVERY_CHUNK_ACLS
from app.science.records import KnownClaim

from .builder_interface import BuildAsk, BuilderTools, Built
from .craft_matter import section_sentences
from .knowledge_view import resolve_craft
from .piece_lookup import claim_states
from .place_claims import PlaceAsk, PlaceClaims, district_place_claims
from .place_offers import region_offer, section_map_layer
from .region_pieces import region_story_pieces
from .region_story import RegionOffer, region_story_block, story_brief, story_statements
from .river_store import rivers_loaded

__all__ = ["REGION_STORY_WAIT_SECONDS", "MapLayerBuilder", "RegionStoryBuilder", "with_place_claims"]

logger = logging.getLogger(__name__)

REGION_STORY_WAIT_SECONDS = 20.0
REGION_STORY_KIND = "region_story"


class RegionStoryBuilder:
    def __init__(self, tools: BuilderTools) -> None:
        self._tools = tools
        self._unloaded_noted = False

    async def build(self, ask: BuildAsk) -> Built:
        craft = ask.request.craft
        if craft is None or any(block.kind == REGION_STORY_KIND for block in ask.blocks):
            return Built()
        section = story_statements(ask.blocks, ask.cited)
        if not section:
            return Built()
        async with self._tools.sessions() as session:
            stored = await resolve_craft(session, craft.slug)
            if stored is None:
                return Built()
            reused = await current_story(session, stored, ask)
            if reused is not None:
                return reused
            offered = await self._offered(session, stored, ask, section)
        if offered is None:
            return Built()
        offer, statements, place = offered
        choice = await choose_region_story(self._tools.plan_model, story_brief(offer, statements))
        block = region_story_block(offer, statements, choice, block_id=f"{ask.section.id}.region")
        return Built((block,), place.sources) if block is not None else Built()

    async def _offered(
        self, session: AsyncSession, craft: Craft, ask: BuildAsk, section: Mapping[str, KnownClaim]
    ) -> tuple[RegionOffer, dict[str, KnownClaim], PlaceClaims] | None:
        if not await rivers_loaded(session):
            self._note_unloaded()
            return None
        texts = [claim.text for claim in section.values()]
        offer = await region_offer(session, craft.slug, texts=texts)
        if offer is None:
            return None
        districts = [offer.districts[lgd] for lgd in offer.craft_districts if lgd in offer.districts]
        held = [claim.id for claim in section.values()]
        place = await district_place_claims(session, craft, districts, _place_ask(ask, held))
        return offer, with_place_claims(section, place.claims), place

    def _note_unloaded(self) -> None:
        if not self._unloaded_noted:
            self._unloaded_noted = True
            logger.info("river lines are not loaded yet, so no region story is built")


async def current_story(session: AsyncSession, craft: Craft, ask: BuildAsk) -> Built | None:
    stories = await region_story_pieces(session, craft, [ask.section.discipline])
    if not stories:
        return None
    states, cited = await claim_states(session, stories, acls=EVERY_CHUNK_ACLS)
    depth = ask.request.depth or EXPLAINER_DEPTHS[-1]
    usable = usable_region_stories(stories, facet=ask.section.discipline, depth=depth, current=states)
    if not usable:
        return None
    block = placed_block(usable[0], f"{ask.section.id}.region")
    sources = {sid: cited.sources[sid] for sid in block.cited_source_ids() if sid in cited.sources}
    return Built((block,), sources)


def with_place_claims(
    section: Mapping[str, KnownClaim], place: tuple[KnownClaim, ...]
) -> dict[str, KnownClaim]:
    held = {claim.id for claim in section.values()}
    added = list({claim.id: claim for claim in place if claim.id not in held}.values())
    return {**section, **{f"c{n}": claim for n, claim in enumerate(added, start=len(section) + 1)}}


def _place_ask(ask: BuildAsk, held: list[uuid.UUID]) -> PlaceAsk:
    return PlaceAsk(
        question=ask.request.english_question or ask.request.question, mode=ask.request.mode, held=held
    )


class MapLayerBuilder:
    def __init__(self, tools: BuilderTools) -> None:
        self._tools = tools

    async def build(self, ask: BuildAsk) -> Built:
        craft = ask.request.craft
        if craft is None:
            return Built()
        texts = [stated_texts(sentence)[0] for sentence in section_sentences(ask.blocks)]
        async with self._tools.sessions() as session:
            found = await section_map_layer(session, craft.slug, ask.section.discipline, texts)
        if found is None:
            return Built()
        block = map_layer_block(map_layer(found.values), found.highlighted, block_id=f"{ask.section.id}.map")
        return Built((block,))
