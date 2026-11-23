from __future__ import annotations

import logging
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from app.core.errors import InvalidInput
from app.research.blocks import ExplainerSentence, ProseBlock
from app.research.blocks_lede import LEDE_BLOCK_ID, LedeBlock
from app.research.composition import LEDE_SENTENCES_MAX, LEDE_SENTENCES_MIN, ComposedAnswer
from app.research.planning import OPEN_QUESTION_LEVEL
from app.research.quotes import unsupported_figures
from app.research.vocabulary import FACT_LEVELS, weakest_level

from .answer_events import CitedClaims
from .knowledge_view import ClaimView
from .stated_names import unstated_names
from .write_back_plan import composed_sentences

__all__ = [
    "BlockRefused",
    "DroppedSentence",
    "KeptSentence",
    "SectionSentences",
    "cited_sentence",
    "explainer_sentence",
    "kept_sentences",
    "lede_block",
    "prose_block",
    "prose_problems",
    "section_sentences",
]

logger = logging.getLogger(__name__)


class BlockRefused(InvalidInput):
    def __init__(self, block_id: str, problems: Sequence[str]) -> None:
        super().__init__(f"block {block_id} is refused: {'; '.join(problems)}")
        self.block_id = block_id
        self.problems = tuple(problems)


@dataclass(frozen=True)
class KeptSentence:
    text: str
    claim_ids: tuple[uuid.UUID, ...]
    evidence_ids: tuple[str, ...]
    open_question: bool
    quotes: tuple[str, ...] = ()
    written: tuple[uuid.UUID, ...] = ()


@dataclass(frozen=True)
class DroppedSentence:
    sentence: KeptSentence
    problems: tuple[str, ...]


@dataclass(frozen=True)
class SectionSentences:
    facts: tuple[KeptSentence, ...]
    open_questions: tuple[KeptSentence, ...]
    dropped: tuple[DroppedSentence, ...] = ()


def kept_sentences(composed: ComposedAnswer, claims_of: Sequence[Sequence[uuid.UUID]]) -> list[KeptSentence]:
    pairs = list(composed_sentences(composed))
    if len(pairs) != len(claims_of):
        raise InvalidInput(f"{len(claims_of)} claim lists were given for {len(pairs)} sentences")
    return [
        KeptSentence(
            sentence.text,
            tuple(claim_ids),
            tuple(sentence.evidence_ids),
            heading is None,
            quotes=tuple(span.text for span in sentence.spans),
            written=tuple(claim for claim in claim_ids if claim not in sentence.claim_ids),
        )
        for (sentence, heading), claim_ids in zip(pairs, claims_of, strict=True)
    ]


def section_sentences(sentences: Sequence[KeptSentence], cited: CitedClaims) -> SectionSentences:
    facts: list[KeptSentence] = []
    open_questions: list[KeptSentence] = []
    dropped: list[DroppedSentence] = []
    for sentence in sentences:
        views = _views(sentence, cited)
        if _level(views) == OPEN_QUESTION_LEVEL:
            problems = _named_problems(sentence, views)
            shown = open_questions
        else:
            problems = _sentence_problems(sentence, views)
            shown = facts
        if problems:
            logger.warning("dropped a sentence alone: %s", "; ".join(problems))
            dropped.append(DroppedSentence(sentence, tuple(problems)))
        else:
            shown.append(sentence)
    return SectionSentences(tuple(facts), tuple(open_questions), tuple(dropped))


def prose_problems(sentences: Sequence[KeptSentence], cited: CitedClaims) -> list[str]:
    return [
        f"sentence {number} {problem}"
        for number, sentence in enumerate(sentences, start=1)
        for problem in _sentence_problems(sentence, _views(sentence, cited))
    ]


def prose_block(block_id: str, sentences: Sequence[KeptSentence], cited: CitedClaims) -> ProseBlock:
    problems = prose_problems(sentences, cited) if sentences else ["the block has no sentence"]
    if problems:
        raise BlockRefused(block_id, problems)
    return ProseBlock(
        id=block_id,
        kind="prose",
        version=1,
        reuse=None,
        sentences=[
            explainer_sentence(f"{block_id}.{n}", sentence, cited)
            for n, sentence in enumerate(sentences, start=1)
        ],
    )


def lede_block(question: str, sentences: Sequence[KeptSentence], cited: CitedClaims) -> LedeBlock:
    if not sentences:
        raise BlockRefused(LEDE_BLOCK_ID, ["the lede has no answer sentence"])
    answer, *others = sentences
    refused = prose_problems([answer], cited)
    if refused:
        raise BlockRefused(LEDE_BLOCK_ID, [f"the answer, {problem}" for problem in refused])
    kept = [answer]
    for sentence in others:
        problems = prose_problems([sentence], cited)
        if problems:
            logger.warning("dropped a lede sentence: %s", "; ".join(problems))
        else:
            kept.append(sentence)
    if len(kept) < LEDE_SENTENCES_MIN:
        raise BlockRefused(LEDE_BLOCK_ID, [f"{len(kept)} sentence(s) pass, not {LEDE_SENTENCES_MIN} or more"])
    return LedeBlock(
        id=LEDE_BLOCK_ID,
        kind="lede",
        version=1,
        reuse=None,
        headline=question,
        sentences=[
            explainer_sentence(f"{LEDE_BLOCK_ID}.{n}", sentence, cited)
            for n, sentence in enumerate(kept[:LEDE_SENTENCES_MAX], start=1)
        ],
        figure=None,
    )


def explainer_sentence(sentence_id: str, sentence: KeptSentence, cited: CitedClaims) -> ExplainerSentence:
    return ExplainerSentence.model_validate(
        cited_sentence(sentence_id, sentence, cited) | {"terms": []} | _differing(_views(sentence, cited))
    )


def cited_sentence(sentence_id: str, sentence: KeptSentence, cited: CitedClaims) -> dict[str, Any]:
    views = _views(sentence, cited)
    return {
        "id": sentence_id,
        "text": sentence.text,
        "level": _level(views),
        "citations": _citations(views),
    }


def _sentence_problems(sentence: KeptSentence, views: Sequence[ClaimView]) -> list[str]:
    if not _citations(views):
        return ["cites no stored claim"]
    problems = [] if _level(views) in FACT_LEVELS else ["is not a fact"]
    figures = unsupported_figures(sentence.text, _supports(views))
    if figures:
        problems.append(f"states {', '.join(figures)}, which no cited claim or quote holds")
    return problems + _named_problems(sentence, views)


def _named_problems(sentence: KeptSentence, views: Sequence[ClaimView]) -> list[str]:
    stated = [
        *(view.text for view in views if view.id not in sentence.written),
        *_quotes(views),
        *sentence.quotes,
    ]
    unstated = unstated_names(sentence.text, stated)
    return [f"names {', '.join(unstated)}, which no cited claim or quote states"] if unstated else []


def _views(sentence: KeptSentence, cited: CitedClaims) -> list[ClaimView]:
    return [cited.views[claim_id] for claim_id in sentence.claim_ids if claim_id in cited.views]


def _supports(views: Sequence[ClaimView]) -> list[str]:
    return [*(view.text for view in views), *_quotes(views)]


def _quotes(views: Sequence[ClaimView]) -> list[str]:
    return [citation["quote"] for citation in _citations(views) if citation["quote"]]


def _differing(views: Sequence[ClaimView]) -> dict[str, Any]:
    flagged = [view for view in views if view.sources_differ]
    if not flagged:
        return {}
    named = (view.differs_on.strip() for view in flagged if view.differs_on)
    about = next((on for on in named if on), None)
    return {"sourcesDiffer": True} | ({"differsOn": about} if about else {})


def _level(views: Sequence[ClaimView]) -> str | None:
    return weakest_level(view.level for view in views) if views else None


def _citations(views: Sequence[ClaimView]) -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    for view in views:
        for citation in view.citations:
            seen.setdefault(citation["id"], citation)
    return list(seen.values())
