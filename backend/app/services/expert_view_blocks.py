from __future__ import annotations

import logging
import uuid
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from itertools import combinations

from pydantic import ValidationError

from app.composer.expert_takes import ProposedDifference
from app.research.blocks import ExplainerSentence
from app.research.blocks_people import ExpertDifference, ExpertViewBlock, expert_pairing_problems
from app.research.vocabulary import FACT_LEVELS

from .answer_events import CitedClaims
from .expert_subjects import Subjects
from .knowledge_view import ClaimView
from .section_blocks import KeptSentence, explainer_sentence

__all__ = [
    "PanelClaims",
    "Take",
    "could_differ",
    "difference_refusal",
    "expert_views",
    "seated_takes",
    "source_ids",
    "stored_fact",
]

logger = logging.getLogger(__name__)

Take = tuple[KeptSentence, ...]


@dataclass(frozen=True)
class PanelClaims:
    cited: CitedClaims
    subjects: Subjects


@dataclass(frozen=True)
class _Panel:
    takes: Mapping[str, Take]
    differences: tuple[ProposedDifference, ...]
    agreeing: Mapping[str, tuple[str, ...]]
    cited: CitedClaims


def stored_fact(claim: str, cited: CitedClaims) -> ClaimView | None:
    try:
        view = cited.views.get(uuid.UUID(claim))
    except ValueError:
        return None
    return view if view is not None and view.level in FACT_LEVELS else None


def source_ids(view: ClaimView) -> set[str]:
    return {str(citation["sourceId"]) for citation in view.citations}


def could_differ(offered: Iterable[str], claims: PanelClaims) -> bool:
    views = [view for claim in offered if (view := stored_fact(claim, claims.cited)) is not None]
    return any(
        claims.subjects.same(one.concept_id, other.concept_id) and not source_ids(one) & source_ids(other)
        for one, other in combinations(views, 2)
    )


def difference_refusal(
    proposal: ProposedDifference, seats: Collection[str], claims: PanelClaims
) -> str | None:
    if proposal.seat == proposal.other_seat:
        return "an expert does not differ with itself"
    if proposal.seat not in seats or proposal.other_seat not in seats:
        return "both experts give a view"
    mine, theirs = stored_fact(proposal.claim, claims.cited), stored_fact(proposal.other_claim, claims.cited)
    if mine is None or theirs is None:
        return "both statements are stored claims the section rests on"
    if mine.id == theirs.id:
        return "a statement does not differ with itself"
    shared = source_ids(mine) & source_ids(theirs)
    if shared:
        return f"both statements cite {', '.join(sorted(shared))}"
    if not claims.subjects.same(mine.concept_id, theirs.concept_id):
        return "the statements concern different subjects"
    return None


def seated_takes(
    takes: Mapping[str, Take],
    differences: Sequence[ProposedDifference],
    claims: PanelClaims,
    shown: Collection[str],
) -> dict[str, Take]:
    kept = _kept_differences(differences, takes, claims)
    differing = {seat for difference in kept for seat in (difference.seat, difference.other_seat)}
    return {
        seat: take for seat, take in takes.items() if seat in differing or _adds_a_claim(seat, take, shown)
    }


def expert_views(
    section_id: str,
    takes: Mapping[str, Take],
    differences: Sequence[ProposedDifference],
    claims: PanelClaims,
) -> list[ExpertViewBlock]:
    kept = _kept_differences(differences, takes, claims)
    panel = _Panel(takes, kept, _agreements(takes, kept), claims.cited)
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


def _adds_a_claim(seat: str, take: Take, shown: Collection[str]) -> bool:
    if any(str(claim) not in shown for sentence in take for claim in sentence.claim_ids):
        return True
    logger.info("the %s view only restates what its section shows, so it is not shown", seat)
    return False


def _kept_differences(
    proposals: Sequence[ProposedDifference], takes: Mapping[str, Take], claims: PanelClaims
) -> tuple[ProposedDifference, ...]:
    kept: list[ProposedDifference] = []
    paired: set[frozenset[str]] = set()
    for proposal in proposals:
        pair = frozenset({proposal.seat, proposal.other_seat})
        refusal = difference_refusal(proposal, takes, claims)
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
