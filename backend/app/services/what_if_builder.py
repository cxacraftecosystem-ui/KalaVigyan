from __future__ import annotations

import logging

from app.composer.what_if import choose_what_if
from app.science.what_if_check import what_if_problems

from .builder_evidence import sources_beyond
from .builder_interface import BuildAsk, BuilderTools, Built
from .craft_matter import section_sentences
from .what_if_block import what_if_block
from .what_if_evidence import what_if_evidence
from .what_if_offers import group_concepts, named_groups, what_if_brief, what_if_inputs

__all__ = ["WHAT_IF_FIELDS", "WHAT_IF_WAIT_SECONDS", "WhatIfBuilder"]

logger = logging.getLogger(__name__)

WHAT_IF_WAIT_SECONDS = 20.0
WHAT_IF_FIELDS = frozenset({"PROCESS", "CHEMISTRY", "GEOGRAPHY"})


class WhatIfBuilder:
    def __init__(self, tools: BuilderTools) -> None:
        self._tools = tools

    async def build(self, ask: BuildAsk) -> Built:
        if ask.request.craft is None:
            return Built()
        matter = await ask.matter.read(self._tools.sessions, ask.request.craft)
        if matter is None:
            return Built()
        groups = named_groups(matter, section_sentences(ask.blocks))
        if not groups:
            return Built()
        evidence = await what_if_evidence(self._tools.sessions, group_concepts(groups))
        inputs = what_if_inputs(groups, matter, evidence, ask.cited)
        if not inputs:
            return Built()
        choice = await choose_what_if(self._tools.plan_model, what_if_brief(ask, inputs))
        block = what_if_block(choice, inputs, block_id=f"{ask.section.id}.whatif")
        if block is None:
            return Built()
        problems = what_if_problems(block, matter.records)
        if problems:
            logger.warning("the what-if of section %s is refused: %s", ask.section.id, "; ".join(problems))
            return Built()
        known = {**matter.records.sources, **evidence.sources}
        return Built((block,), sources_beyond([block], known, ask.cited))
