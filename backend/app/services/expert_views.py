from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from itertools import combinations

from pydantic import ValidationError

from app.composer.candidates import stored_claim_candidate
from app.composer.expert_differences import DifferenceAsk, compose_differences
from app.composer.expert_takes import ProposedDifference, SeatAsk, SeatTake, compose_take
from app.research.blocks import ExplainerSentence
from app.research.blocks_people import ExpertDifference, ExpertViewBlock, expert_pairing_problems
from app.research.composition import ComposeCandidate, ComposeFocus
from app.research.expert_panel import EXPERT_PANEL, SeatBrief, speaking_seats, voiced_seats
from app.research.explainer import Block
from app.research.vocabulary import FACT_LEVELS

from .answer_events import CitedClaims, joined_claims
from .artisan_seat import Heard, VoiceSearch, artisan_take, stored_voices
from .builder_interface import BuildAsk, BuilderTools, Built
from .knowledge_view import ClaimView
from .seat_search import SeatEvidence, SeatSearch, stored_seat_search
from .section_blocks import KeptSentence, explainer_sentence, prose_problems

__all__ = [
    "EXPERT_VIEW_WAIT_SECONDS",
    "ExpertPanelBuilder",
    "difference_refusal",
    "expert_views",
    "kept_takes",
    "panel_candidates",
    "seated_takes",
]

logger = logging.getLogger(__name__)

EXPERT_VIEW_WAIT_SECONDS = 90.0

Take = tuple[KeptSentence, ...]
Offers = Mapping[str, tuple[ComposeCandidate, ...]]


class ExpertPanelBuilder:
    def __init__(
        self, tools: BuilderTools, *, search: SeatSearch | None = None, voices: VoiceSearch | None = None
    ) -> None:
        self._model = tools.compose_model
        self._search = search or stored_seat_search(tools)
        self._voices = voices or stored_voices(tools)

    async def build(self, ask: BuildAsk) -> Built:
        request, section = ask.request, ask.section
        seats = speaking_seats(section.discipline, request.seats, depth=request.depth)
        voiced = voiced_seats(section.discipline, request.seats, depth=request.depth)
        if not ask.blocks or not (seats or voiced):
            return Built()
        shown = _shown_claims(ask.blocks)
        briefs = tuple(EXPERT_PANEL[seat] for seat in seats)
        evidence, heard = await asyncio.gather(self._evidence(ask, briefs, shown), self._heard(ask, voiced))
        cited = joined_claims(ask.cited, evidence.cited, heard.cited)
        offers = _offers(ask, briefs, evidence, cited, shown)
        takes = kept_takes(await self._takes(ask, offers), cited)
        differences = await self._differences(ask, offers, takes, cited)
        takes = seated_takes(takes, differences, cited, shown)
        voice = artisan_take(heard, shown)
        if voice:
            takes = {**takes, voiced[0]: voice}
        return _built(section.id, expert_views(section.id, takes, differences, cited), cited)

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

    async def _takes(self, ask: BuildAsk, offers: Offers) -> list[SeatTake]:
        focus = ComposeFocus(discipline=ask.section.discipline, title=ask.section.title)
        asks = [
            SeatAsk(ask.request.question, ask.request.craft, focus, EXPERT_PANEL[seat], candidates)
            for seat, candidates in offers.items()
        ]
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

    async def _differences(
        self, ask: BuildAsk, offers: Offers, takes: Mapping[str, Take], cited: CitedClaims
    ) -> tuple[ProposedDifference, ...]:
        offered = {c.id: c for seat in takes for c in offers.get(seat, ())}
        if len(takes) < 2 or not _could_differ(offered, cited):
            return ()
        focus = ComposeFocus(discipline=ask.section.discipline, title=ask.section.title)
        briefs = tuple(EXPERT_PANEL[seat] for seat in takes)
        compared = DifferenceAsk(
            ask.request.question, ask.request.craft, focus, briefs, tuple(offered.values())
        )
        try:
            return await compose_differences(self._model, compared)
        except Exception as error:
            logger.warning("experts differ is not asked for %s: %s", ask.section.id, error)
            return ()


@dataclass(frozen=True)
class _Panel:
    takes: Mapping[str, Take]
    differences: tuple[ProposedDifference, ...]
    agreeing: Mapping[str, tuple[str, ...]]
    cited: CitedClaims


def panel_candidates(cited: CitedClaims, blocks: Sequence[Block]) -> list[ComposeCandidate]:
    shown = dict.fromkeys(citation.claim_id for block in blocks for citation in block.citations())
    rest = sorted(str(claim_id) for claim_id in cited.views if str(claim_id) not in shown)
    views = [_stored(claim, cited) for claim in [*rest, *shown]]
    return [_candidate(view) for view in views if view is not None]


def kept_takes(takes: Sequence[SeatTake], cited: CitedClaims) -> dict[str, Take]:
    return {take.seat: kept for take in takes if (kept := _kept_take(take, cited)) is not None}


def seated_takes(
    takes: Mapping[str, Take],
    differences: Sequence[ProposedDifference],
    cited: CitedClaims,
    shown: Collection[str],
) -> dict[str, Take]:
    kept = _kept_differences(differences, takes, cited)
    differing = {seat for difference in kept for seat in (difference.seat, difference.other_seat)}
    return {
        seat: take for seat, take in takes.items() if seat in differing or _adds_a_claim(seat, take, shown)
    }


def expert_views(
    section_id: str,
    takes: Mapping[str, Take],
    differences: Sequence[ProposedDifference],
    cited: CitedClaims,
) -> list[ExpertViewBlock]:
    kept = _kept_differences(differences, takes, cited)
    panel = _Panel(takes, kept, _agreements(takes, kept), cited)
    try:
        views = [_view(f"{section_id}.{seat.lower().replace('_', '-')}", seat, panel) for seat in takes]
    except ValidationError as refused:
        logger.warning("the expert views of %s are refused: %s", section_id, refused)
        return []
    problems = expert_pairing_problems(views)
    if problems:
        logger.warning("the expert views of %s are refused: %s", section_id, "; ".join(problems))
        return []
    return views


def difference_refusal(
    proposal: ProposedDifference, seats: Collection[str], cited: CitedClaims
) -> str | None:
    if proposal.seat == proposal.other_seat:
        return "an expert does not differ with itself"
    if proposal.seat not in seats or proposal.other_seat not in seats:
        return "both experts give a view"
    mine, theirs = _stored(proposal.claim, cited), _stored(proposal.other_claim, cited)
    if mine is None or theirs is None:
        return "both statements are stored claims the section rests on"
    if mine.id == theirs.id:
        return "a statement does not differ with itself"
    shared = _source_ids(mine) & _source_ids(theirs)
    if shared:
        return f"both statements cite {', '.join(sorted(shared))}"
    if mine.concept_id is None or mine.concept_id != theirs.concept_id:
        return "the statements concern different subjects"
    return None


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


def _could_differ(offered: Mapping[str, ComposeCandidate], cited: CitedClaims) -> bool:
    views = [view for claim in offered if (view := _stored(claim, cited)) is not None]
    return any(
        one.concept_id is not None
        and one.concept_id == other.concept_id
        and not _source_ids(one) & _source_ids(other)
        for one, other in combinations(views, 2)
    )


def _built(section_id: str, views: Sequence[ExpertViewBlock], cited: CitedClaims) -> Built:
    wanted = dict.fromkeys(source_id for view in views for source_id in view.cited_source_ids())
    missing = [source_id for source_id in wanted if source_id not in cited.sources]
    if missing:
        logger.warning("the expert views of %s cite unknown sources %s", section_id, missing)
        return Built()
    return Built(tuple(views), {source_id: cited.sources[source_id] for source_id in wanted})


def _kept_take(take: SeatTake, cited: CitedClaims) -> Take | None:
    problems = [
        f"{s.raw_text!r}: {'; '.join(s.problems) or 'unreadable'}" for s in take.sentences if not s.passes
    ]
    if not take.sentences or problems:
        logger.warning("the %s view is dropped: %s", take.seat, " | ".join(problems) or "no sentence")
        return None
    kept = tuple(
        KeptSentence(s.sentence.text, tuple(s.sentence.claim_ids), tuple(s.sentence.evidence_ids), False)
        for s in take.sentences
        if s.sentence is not None
    )
    checked = prose_problems(kept, cited)
    if checked:
        logger.warning("the %s view is dropped: %s", take.seat, "; ".join(checked))
        return None
    return kept


def _adds_a_claim(seat: str, take: Take, shown: Collection[str]) -> bool:
    if any(str(claim) not in shown for sentence in take for claim in sentence.claim_ids):
        return True
    logger.info("the %s view only restates what its section shows, so it is not shown", seat)
    return False


def _shown_claims(blocks: Sequence[Block]) -> set[str]:
    return {claim for block in blocks for claim in block.cited_claim_ids()}


def _kept_differences(
    proposals: Sequence[ProposedDifference], takes: Mapping[str, Take], cited: CitedClaims
) -> tuple[ProposedDifference, ...]:
    kept: list[ProposedDifference] = []
    paired: set[frozenset[str]] = set()
    for proposal in proposals:
        pair = frozenset({proposal.seat, proposal.other_seat})
        refusal = difference_refusal(proposal, takes, cited)
        if refusal is None and pair in paired:
            refusal = "the two experts already differ"
        if refusal is not None:
            logger.info("experts differ is refused for %s: %s", "+".join(sorted(pair)), refusal)
            continue
        paired.add(pair)
        kept.append(proposal)
    return tuple(kept)


def _agreements(
    takes: Mapping[str, Take], differences: Sequence[ProposedDifference]
) -> dict[str, tuple[str, ...]]:
    differing = {frozenset({d.seat, d.other_seat}) for d in differences}
    claims = {seat: {claim for s in take for claim in s.claim_ids} for seat, take in takes.items()}
    agreeing: dict[str, list[str]] = {seat: [] for seat in takes}
    for one, other in combinations(takes, 2):
        if frozenset({one, other}) not in differing and claims[one] & claims[other]:
            agreeing[one].append(other)
            agreeing[other].append(one)
    return {seat: tuple(seats) for seat, seats in agreeing.items()}


def _view(block_id: str, seat: str, panel: _Panel) -> ExpertViewBlock:
    take = [
        explainer_sentence(f"{block_id}.{n}", sentence, panel.cited)
        for n, sentence in enumerate(panel.takes[seat], 1)
    ]
    differs: list[ExpertDifference] = []
    for other, mine, theirs in _sides(seat, panel.differences):
        number = len(take) + 2 * len(differs)
        differs.append(
            ExpertDifference(
                seat=other,
                this_view=_claim_sentence(f"{block_id}.{number + 1}", mine, panel.cited),
                other_view=_claim_sentence(f"{block_id}.{number + 2}", theirs, panel.cited),
            )
        )
    return ExpertViewBlock(
        id=block_id,
        kind="expert_view",
        version=1,
        reuse=None,
        seat=seat,
        take=take,
        agrees_with=list(panel.agreeing[seat]),
        differs=differs,
    )


def _sides(seat: str, differences: Sequence[ProposedDifference]) -> list[tuple[str, str, str]]:
    sides = []
    for difference in differences:
        if difference.seat == seat:
            sides.append((difference.other_seat, difference.claim, difference.other_claim))
        elif difference.other_seat == seat:
            sides.append((difference.seat, difference.other_claim, difference.claim))
    return sides


def _claim_sentence(sentence_id: str, claim: str, cited: CitedClaims) -> ExplainerSentence:
    view = cited.views[uuid.UUID(claim)]
    return explainer_sentence(sentence_id, KeptSentence(view.text, (view.id,), (), False), cited)


def _stored(claim: str, cited: CitedClaims) -> ClaimView | None:
    try:
        view = cited.views.get(uuid.UUID(claim))
    except ValueError:
        return None
    return view if view is not None and view.level in FACT_LEVELS else None


def _candidate(view: ClaimView) -> ComposeCandidate:
    quotes = list(dict.fromkeys(c["quote"] for c in view.citations if c.get("quote")))
    return stored_claim_candidate(view.id, view.text, view.level).model_copy(update={"quotes": quotes})


def _source_ids(view: ClaimView) -> set[str]:
    return {str(citation["sourceId"]) for citation in view.citations}
