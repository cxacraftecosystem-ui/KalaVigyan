from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from app.composer.candidates import stored_claim_candidate
from app.research.composition import SECTION_SENTENCES_LIMIT, ComposeRequest, RefusedSentence
from app.research.sections import SectionSpec

from .answer_events import CitedClaims, joined_claims
from .section_blocks import DroppedSentence, KeptSentence, SectionSentences, kept_sentences, section_sentences
from .section_context import SectionContext
from .write_back_plan import composed_sentences

__all__ = ["DROP_REASONS", "Written", "drop_reasons", "rewrite_request", "rewritten"]

logger = logging.getLogger(__name__)

DROP_REASONS = ("cites no stored claim", "is not a fact", "states", "names")


@dataclass(frozen=True)
class Written:
    split: SectionSentences
    cited: CitedClaims


async def rewritten(
    spec: SectionSpec,
    context: SectionContext,
    request: ComposeRequest,
    sentences: Sequence[KeptSentence],
    cited: CitedClaims,
) -> Written:
    split = section_sentences(sentences, cited)
    if split.dropped:
        logger.warning(
            "section %s dropped %d sentence(s) after its write-back: %s",
            spec.id,
            len(split.dropped),
            drop_reasons(split.dropped),
        )
    late = [dropped for dropped in split.dropped if dropped.sentence.evidence_ids]
    again = rewrite_request(request, late, cited)
    if again is None:
        return Written(split, cited)
    composed = await context.tools.compose(again)
    claims_of = tuple(tuple(sentence.claim_ids) for sentence, _ in composed_sentences(composed))
    found = await context.tools.store.cited(claim for claims in claims_of for claim in claims)
    joined = joined_claims(cited, found)
    shown = {sentence.text for sentence in split.facts}
    fresh = context.deepening_of(spec.id).unshown(kept_sentences(composed, claims_of))
    more = section_sentences([sentence for sentence in fresh if sentence.text not in shown], joined)
    logger.info("section %s rewrote %d of %d refused sentence(s)", spec.id, len(more.facts), len(late))
    facts = (*split.facts, *more.facts)
    return Written(
        SectionSentences(facts, (*split.open_questions, *more.open_questions), split.dropped), joined
    )


def rewrite_request(
    request: ComposeRequest, late: Sequence[DroppedSentence], cited: CitedClaims
) -> ComposeRequest | None:
    if not late or request.focus is None:
        return None
    claims = [candidate for candidate in request.candidates if candidate.kind == "CLAIM"]
    known = {candidate.id for candidate in claims}
    claims += [
        stored_claim_candidate(view.id, view.text, view.level)
        for view in cited.views.values()
        if str(view.id) not in known
    ]
    if not claims:
        return None
    refused = [
        RefusedSentence(text=dropped.sentence.text, problems=list(dropped.problems))
        for dropped in late[:SECTION_SENTENCES_LIMIT]
    ]
    return ComposeRequest(
        question=request.question,
        craft=request.craft,
        candidates=claims,
        searched=request.searched,
        focus=request.focus,
        style=request.style,
        refused=refused,
    )


def drop_reasons(dropped: Sequence[DroppedSentence]) -> dict[str, int]:
    counted = Counter(_reason(problem) for one in dropped for problem in one.problems)
    return dict(sorted(counted.items()))


def _reason(problem: str) -> str:
    return next((reason for reason in DROP_REASONS if problem.startswith(reason)), problem)
