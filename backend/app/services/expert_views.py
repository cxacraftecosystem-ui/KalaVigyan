from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable, Mapping, Sequence

from app.composer.candidates import stored_claim_candidate
from app.composer.expert_differences import DifferenceAsk, compose_differences
from app.composer.expert_takes import ProposedDifference, SeatAsk, SeatTake, compose_take
from app.research.blocks_people import ExpertViewBlock
from app.research.composition import ComposeCandidate, ComposeFocus
from app.research.expert_panel import EXPERT_PANEL, SeatBrief, speaking_seats, voiced_seats
from app.research.explainer import Block

from .answer_events import CitedClaims, joined_claims
from .artisan_seat import Heard, VoiceSearch, artisan_take, stored_voices
from .builder_interface import BuildAsk, BuilderTools, Built
from .expert_seat_takes import kept_takes, retake_allowed, retaken_takes
from .expert_subjects import SubjectLookup, Subjects, stored_subjects
from .expert_view_blocks import PanelClaims, Take, could_differ, expert_views, seated_takes, stored_fact
from .knowledge_view import ClaimView
from .seat_search import SeatEvidence, SeatSearch, stored_seat_search

__all__ = ["EXPERT_VIEW_WAIT_SECONDS", "ExpertPanelBuilder", "panel_candidates"]

logger = logging.getLogger(__name__)

EXPERT_VIEW_WAIT_SECONDS = 90.0

Offers = Mapping[str, tuple[ComposeCandidate, ...]]


class ExpertPanelBuilder:
    def __init__(
        self,
        tools: BuilderTools,
        *,
        search: SeatSearch | None = None,
        voices: VoiceSearch | None = None,
        subjects: SubjectLookup | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._model = tools.compose_model
        self._search = search or stored_seat_search(tools)
        self._voices = voices or stored_voices(tools)
        self._subjects = subjects or stored_subjects(tools)
        self._clock = clock

    async def build(self, ask: BuildAsk) -> Built:
        started = self._clock()
        request, section = ask.request, ask.section
        seats = speaking_seats(section.discipline, request.seats, depth=request.depth)
        voiced = voiced_seats(section.discipline, request.seats, depth=request.depth)
        if not ask.blocks or not (seats or voiced):
            return Built()
        shown = _shown_claims(ask.blocks)
        briefs = tuple(EXPERT_PANEL[seat] for seat in seats)
        evidence, heard = await asyncio.gather(self._evidence(ask, briefs, shown), self._heard(ask, voiced))
        cited = joined_claims(ask.cited, evidence.cited, heard.cited)
        asks = _seat_asks(ask, _offers(ask, briefs, evidence, cited, shown))
        takes = await self._retaken(asks, await self._takes(ask, asks), cited, started)
        kept = kept_takes(takes, cited)
        claims = PanelClaims(cited, await self._linked(kept, asks, cited))
        differences = await self._differences(ask, asks, kept, claims)
        kept = seated_takes(kept, differences, claims, shown)
        voice = artisan_take(heard, shown)
        if voice:
            kept = {**kept, voiced[0]: voice}
        return _built(section.id, expert_views(section.id, kept, differences, claims), cited)

    async def _evidence(self, ask: BuildAsk, briefs: Sequence[SeatBrief], shown: set[str]) -> SeatEvidence:
        try:
            return await self._search(ask, briefs, shown)
        except Exception as error:
            logger.warning("the seats of %s search no evidence of their own: %s", ask.section.id, error)
            return SeatEvidence()

    async def _heard(self, ask: BuildAsk, voiced: Sequence[str]) -> Heard:
        if not voiced:
            return Heard()
        try:
            return await self._voices(ask)
        except Exception as error:
            logger.warning("the artisan seat of %s hears no field transcript: %s", ask.section.id, error)
            return Heard()

    async def _takes(self, ask: BuildAsk, asks: Sequence[SeatAsk]) -> list[SeatTake]:
        replies = await asyncio.gather(
            *(compose_take(self._model, one) for one in asks), return_exceptions=True
        )
        takes: list[SeatTake] = []
        for one, reply in zip(asks, replies, strict=True):
            if isinstance(reply, SeatTake):
                takes.append(reply)
            elif isinstance(reply, Exception):
                logger.warning("the %s view of %s is dropped: %s", one.seat.seat, ask.section.id, reply)
            else:
                raise reply
        return takes

    async def _retaken(
        self, asks: Sequence[SeatAsk], takes: Sequence[SeatTake], cited: CitedClaims, started: float
    ) -> list[SeatTake]:
        left = EXPERT_VIEW_WAIT_SECONDS - (self._clock() - started)
        if not retake_allowed(left):
            return list(takes)
        return await retaken_takes(self._model, asks, takes, cited)

    async def _linked(
        self, kept: Mapping[str, Take], asks: Sequence[SeatAsk], cited: CitedClaims
    ) -> Subjects:
        if len(kept) < 2:
            return Subjects()
        concepts = {view.concept_id for view in _offered(asks, kept, cited) if view.concept_id is not None}
        try:
            return await self._subjects(concepts)
        except Exception as error:
            logger.warning("the panel reads no glossary links between its subjects: %s", error)
            return Subjects()

    async def _differences(
        self, ask: BuildAsk, asks: Sequence[SeatAsk], kept: Mapping[str, Take], claims: PanelClaims
    ) -> tuple[ProposedDifference, ...]:
        offered = {c.id: c for one in asks if one.seat.seat in kept for c in one.candidates}
        if len(kept) < 2 or not could_differ(offered, claims):
            return ()
        focus = ComposeFocus(discipline=ask.section.discipline, title=ask.section.title)
        briefs = tuple(EXPERT_PANEL[seat] for seat in kept)
        compared = DifferenceAsk(
            ask.request.question, ask.request.craft, focus, briefs, tuple(offered.values())
        )
        try:
            return await compose_differences(self._model, compared)
        except Exception as error:
            logger.warning("experts differ is not asked for %s: %s", ask.section.id, error)
            return ()


def panel_candidates(cited: CitedClaims, blocks: Sequence[Block]) -> list[ComposeCandidate]:
    shown = dict.fromkeys(citation.claim_id for block in blocks for citation in block.citations())
    rest = sorted(str(claim_id) for claim_id in cited.views if str(claim_id) not in shown)
    views = [stored_fact(claim, cited) for claim in [*rest, *shown]]
    return [_candidate(view) for view in views if view is not None]


def _seat_asks(ask: BuildAsk, offers: Offers) -> list[SeatAsk]:
    focus = ComposeFocus(discipline=ask.section.discipline, title=ask.section.title)
    return [
        SeatAsk(ask.request.question, ask.request.craft, focus, EXPERT_PANEL[seat], candidates)
        for seat, candidates in offers.items()
    ]


def _offers(
    ask: BuildAsk, briefs: Sequence[SeatBrief], evidence: SeatEvidence, cited: CitedClaims, shown: set[str]
) -> dict[str, tuple[ComposeCandidate, ...]]:
    section = panel_candidates(ask.cited, ask.blocks)
    offers: dict[str, tuple[ComposeCandidate, ...]] = {}
    for brief in briefs:
        own = [_candidate(view) for view in evidence.found.get(brief.seat, ()) if view.id in cited.views]
        candidates = tuple({candidate.id: candidate for candidate in [*own, *section]}.values())
        if any(candidate.id not in shown for candidate in candidates):
            offers[brief.seat] = candidates
    return offers


def _offered(asks: Sequence[SeatAsk], kept: Mapping[str, Take], cited: CitedClaims) -> list[ClaimView]:
    claims = dict.fromkeys(c.id for one in asks if one.seat.seat in kept for c in one.candidates)
    return [view for claim in claims if (view := stored_fact(claim, cited)) is not None]


def _built(section_id: str, views: Sequence[ExpertViewBlock], cited: CitedClaims) -> Built:
    wanted = dict.fromkeys(source_id for view in views for source_id in view.cited_source_ids())
    missing = [source_id for source_id in wanted if source_id not in cited.sources]
    if missing:
        logger.warning("the expert views of %s cite unknown sources %s", section_id, missing)
        return Built()
    return Built(tuple(views), {source_id: cited.sources[source_id] for source_id in wanted})


def _shown_claims(blocks: Sequence[Block]) -> set[str]:
    return {claim for block in blocks for claim in block.cited_claim_ids()}


def _candidate(view: ClaimView) -> ComposeCandidate:
    quotes = list(dict.fromkeys(c["quote"] for c in view.citations if c.get("quote")))
    return stored_claim_candidate(view.id, view.text, view.level).model_copy(update={"quotes": quotes})
