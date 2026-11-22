from __future__ import annotations

import logging

from app.composer.region_story import choose_region_story
from app.geo.layers import map_layer
from app.geo.section_layers import map_layer_block
from app.research.blocks import stated_texts

from .builder_interface import BuildAsk, BuilderTools, Built
from .craft_matter import section_sentences
from .place_offers import region_offer, section_map_layer
from .region_story import region_story_block, story_brief, story_statements
from .river_store import rivers_loaded

__all__ = ["REGION_STORY_WAIT_SECONDS", "MapLayerBuilder", "RegionStoryBuilder"]

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
        statements = story_statements(ask.blocks, ask.cited)
        if not statements:
            return Built()
        async with self._tools.sessions() as session:
            loaded = await rivers_loaded(session)
            texts = [claim.text for claim in statements.values()]
            offer = await region_offer(session, craft.slug, texts=texts) if loaded else None
        if not loaded:
            self._note_unloaded()
            return Built()
        if offer is None:
            return Built()
        choice = await choose_region_story(self._tools.plan_model, story_brief(offer, statements))
        block = region_story_block(offer, statements, choice, block_id=f"{ask.section.id}.region")
        return Built((block,)) if block is not None else Built()

    def _note_unloaded(self) -> None:
        if not self._unloaded_noted:
            self._unloaded_noted = True
            logger.info("river lines are not loaded yet, so no region story is built")


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
