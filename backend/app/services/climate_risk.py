from __future__ import annotations

import logging
import re
from collections.abc import Mapping, Sequence

from app.composer.climate_meaning import MEANING_MAX, choose_climate_meaning
from app.core.errors import AppError
from app.geo.climate import ClimateTrends
from app.research.blocks_climate import ClimateRiskBlock
from app.research.explainer import Block
from app.science.records import KnownClaim

from .answer_events import CitedClaims
from .builder_evidence import fact_sentence, section_facts
from .builder_interface import BuildAsk, BuilderTools, Built
from .climate_store import craft_climate

__all__ = [
    "CLIMATE_RISK_WAIT_SECONDS",
    "MEANING_OFFERED_MAX",
    "MEANING_WORDS",
    "ClimateRiskBuilder",
    "climate_risk_block",
    "meaning_statements",
]

logger = logging.getLogger(__name__)

CLIMATE_RISK_WAIT_SECONDS = 15.0
MEANING_OFFERED_MAX = 12
MEANING_WORDS = re.compile(
    r"\b(?:water\w*|rain\w*|monsoon\w*|drought\w*|groundwater|wells?|rivers?|floods?|flooding|heat\w*|hot|"
    r"temperatures?|humid\w*|climate\w*|aquifers?|salin\w*|arid|dry|dries|drying)\b",
    re.IGNORECASE,
)


class ClimateRiskBuilder:
    def __init__(self, tools: BuilderTools) -> None:
        self._tools = tools

    async def build(self, ask: BuildAsk) -> Built:
        craft = ask.request.craft
        if craft is None:
            return Built()
        async with self._tools.sessions() as session:
            climate = await craft_climate(session, craft.slug)
        if not climate.trends and not climate.groundwater:
            return Built()
        statements = meaning_statements(ask.blocks, ask.cited)
        chosen = await self._chosen(statements)
        return Built((climate_risk_block(climate, statements, chosen, block_id=f"{ask.section.id}.climate"),))

    async def _chosen(self, statements: Mapping[str, KnownClaim]) -> list[str]:
        if not statements:
            return []
        texts = {ref: claim.text for ref, claim in statements.items()}
        try:
            return await choose_climate_meaning(self._tools.plan_model, texts)
        except AppError as failure:
            logger.warning("climate trends are shown without what they mean for the craft: %s", failure)
            return []


def meaning_statements(blocks: Sequence[Block], cited: CitedClaims) -> dict[str, KnownClaim]:
    facts = [fact for fact in section_facts(blocks, cited) if MEANING_WORDS.search(fact.text)]
    return {f"c{n}": fact for n, fact in enumerate(facts[:MEANING_OFFERED_MAX], start=1)}


def climate_risk_block(
    climate: ClimateTrends, statements: Mapping[str, KnownClaim], chosen: Sequence[str], *, block_id: str
) -> ClimateRiskBlock:
    picked = [statements[ref] for ref in dict.fromkeys(chosen) if ref in statements][:MEANING_MAX]
    return ClimateRiskBlock(
        id=block_id,
        kind="climate_risk",
        version=1,
        reuse=None,
        trends=list(climate.trends),
        groundwater=list(climate.groundwater),
        meaning=[fact_sentence(claim, f"{block_id}.{n}") for n, claim in enumerate(picked, start=1)],
        datasets=list(climate.datasets),
    )
