from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.composer.candidates import compose_request
from app.planner.policy import SEAT_LIVE_SHARE, SEAT_SENTENCES_MAX
from app.research.composition import ComposedAnswer, ComposeFocus, ComposeRequest
from app.research.evidence_pack import EvidencePack, ResearchTrail
from app.research.expert_panel import SeatBrief
from app.research.explainer import Block
from app.research.planning import PlanRequest, ResearchShare
from app.research.sections import DISCIPLINE_TITLES, SectionSpec
from app.research.stream import ResearchProgress, StatusStep

from .answer_events import CitedClaims
from .builder_interface import BuildAsk
from .research_ledger import ResearchLedger

if TYPE_CHECKING:
    from .answer_sections import SectionContext, SectionStore

__all__ = ["BuildAsk", "GapResearch", "gap_research", "seat_request", "seat_share", "section_ask"]

Research = Callable[[PlanRequest, ResearchProgress, ResearchTrail], Awaitable[EvidencePack]]
Compose = Callable[[ComposeRequest], Awaitable[ComposedAnswer]]


@dataclass(frozen=True)
class GapResearch:
    answer_id: uuid.UUID
    base: PlanRequest
    ledger: ResearchLedger
    research: Research
    compose: Compose
    store: SectionStore
    trail: ResearchTrail

    async def __call__(self, brief: SeatBrief, discipline: str) -> CitedClaims:
        share = seat_share(self.ledger)
        if share is None:
            return CitedClaims()
        try:
            pack = await self.research(seat_request(self.base, brief, discipline, share), _quiet, self.trail)
        except BaseException:
            self.ledger.give_back(share)
            raise
        self.ledger.settle(share, pack)
        if not pack.documents:
            return CitedClaims()
        focus = ComposeFocus(
            discipline=discipline, title=DISCIPLINE_TITLES[discipline], sentences_max=SEAT_SENTENCES_MAX
        )
        composed = await self.compose(compose_request(pack, self.base.question, focus=focus))
        kept = await self.store.keep(self.answer_id, pack, composed)
        return await self.store.cited(claim for claims in kept for claim in claims)


def gap_research(context: SectionContext) -> GapResearch:
    tools = context.tools
    return GapResearch(
        answer_id=context.answer_id,
        base=context.base,
        ledger=context.ledger,
        research=tools.research,
        compose=tools.compose,
        store=tools.store,
        trail=context.stream.trail,
    )


def section_ask(
    context: SectionContext, spec: SectionSpec, blocks: tuple[Block, ...], cited: CitedClaims
) -> BuildAsk:
    return BuildAsk(context.answer_id, spec, context.base, blocks, cited, research=gap_research(context))


def seat_share(ledger: ResearchLedger) -> ResearchShare | None:
    granted = ledger.take(SEAT_LIVE_SHARE)
    if granted.queries >= SEAT_LIVE_SHARE.queries and granted.fetches >= SEAT_LIVE_SHARE.fetches:
        return granted
    ledger.give_back(granted)
    return None


def seat_request(base: PlanRequest, brief: SeatBrief, discipline: str, share: ResearchShare) -> PlanRequest:
    changes = {"focus": discipline, "share": share.model_dump(), "fresh": True, "seats": [brief.seat]}
    return PlanRequest.model_validate(base.model_dump() | changes)


async def _quiet(step: StatusStep, count: int) -> None:
    return None
