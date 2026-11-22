from __future__ import annotations

import logging
import uuid
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import Literal, Self

from pydantic import ValidationError, model_validator

from .base import ContractModel
from .blocks import BlockBase, ExplainerSentence, named_in
from .blocks_learning import QUIZ_MAX_QUESTIONS, QUIZ_OPTIONS_MAX, QuizBlock, QuizQuestion, quiz_prompt
from .blocks_play import hidden_block
from .citations import SourceRef, cited_source_ids
from .explainer import Explainer
from .offered_facts import sentence_claim_ids
from .terms import TermSpan
from .vocabulary import FACT_LEVELS, AnswerLanguage

__all__ = [
    "QUIZ_BLOCK_ID",
    "QUIZ_DISTRACTORS_MAX",
    "QUIZ_DISTRACTORS_MIN",
    "QUIZ_SCHEMA_VERSION",
    "QUIZ_TERM_MIN_CHARS",
    "ExplainerQuiz",
    "explainer_quiz",
    "quiz_block",
    "quiz_sentences",
    "still_cited",
]

logger = logging.getLogger(__name__)

QUIZ_SCHEMA_VERSION = 1
QUIZ_BLOCK_ID = "quiz"
QUIZ_TERM_MIN_CHARS = 3
QUIZ_DISTRACTORS_MIN = 2
QUIZ_DISTRACTORS_MAX = QUIZ_OPTIONS_MAX - 2
UNQUIZZED_KINDS = frozenset({"quiz"})


class ExplainerQuiz(ContractModel):
    schema_version: Literal[1]
    answer_id: uuid.UUID
    language: AnswerLanguage
    quiz: QuizBlock
    sources: list[SourceRef]

    @model_validator(mode="after")
    def _sources_as_cited(self) -> Self:
        if [source.id for source in self.sources] != cited_source_ids(self.quiz.cited_sentences()):
            raise ValueError("a quiz lists every source it cites once, in order of first citation")
        return self


@dataclass(frozen=True)
class _Placed:
    section: int
    sentence: ExplainerSentence


def quiz_sentences(explainer: Explainer, section_ids: Sequence[str] = ()) -> list[list[ExplainerSentence]]:
    by_id = {section.id: section for section in explainer.sections}
    chosen = [by_id[section_id] for section_id in section_ids] if section_ids else explainer.sections
    asked = [_quizzed(section.blocks) for section in chosen]
    if section_ids or explainer.lede is None:
        return asked
    return [_quizzed([explainer.lede]), *asked]


def _quizzed(blocks: Sequence[BlockBase]) -> list[ExplainerSentence]:
    return [
        sentence
        for block in blocks
        if block.kind not in UNQUIZZED_KINDS and not hidden_block(block)
        for sentence in block.cited_sentences()
        if isinstance(sentence, ExplainerSentence)
    ]


def still_cited(sentence: ExplainerSentence, visible_claim_ids: frozenset[str]) -> bool:
    return sentence_claim_ids(sentence) <= visible_claim_ids


def explainer_quiz(
    explainer: Explainer, *, visible_claim_ids: frozenset[str], section_ids: Sequence[str] = ()
) -> ExplainerQuiz | None:
    sections = [
        [sentence for sentence in shown if still_cited(sentence, visible_claim_ids)]
        for shown in quiz_sentences(explainer, section_ids)
    ]
    block = quiz_block(sections, block_id=QUIZ_BLOCK_ID)
    if block is None:
        return None
    known = {source.id: source for source in explainer.sources}
    return ExplainerQuiz(
        schema_version=QUIZ_SCHEMA_VERSION,
        answer_id=explainer.answer_id,
        language=explainer.understood.language,
        quiz=block,
        sources=[known[source_id] for source_id in cited_source_ids(block.cited_sentences())],
    )


def quiz_block(
    sections: Sequence[Sequence[ExplainerSentence]], *, block_id: str, limit: int = QUIZ_MAX_QUESTIONS
) -> QuizBlock | None:
    pool = _pool(sections)
    questions: list[QuizQuestion] = []
    keyed: set[str] = set()
    for position in _round_robin(pool):
        if len(questions) >= limit:
            break
        found = _question(pool, position, keyed, f"{block_id}.q{len(questions) + 1}")
        if found is not None and all(found[0].prompt != asked.prompt for asked in questions):
            keyed.add(found[1])
            questions.append(found[0])
    if not questions:
        return None
    return QuizBlock(id=block_id, kind="quiz", version=1, reuse=None, questions=questions)


def _pool(sections: Sequence[Sequence[ExplainerSentence]]) -> list[_Placed]:
    seen: set[str] = set()
    pool: list[_Placed] = []
    for number, sentences in enumerate(sections):
        for sentence in sentences:
            if sentence.level not in FACT_LEVELS or sentence.text in seen:
                continue
            seen.add(sentence.text)
            pool.append(_Placed(number, sentence))
    return pool


def _round_robin(pool: Sequence[_Placed]) -> Iterator[int]:
    by_section: dict[int, list[int]] = {}
    for position, placed in enumerate(pool):
        if placed.sentence.terms:
            by_section.setdefault(placed.section, []).append(position)
    queues = list(by_section.values())
    for turn in range(max((len(queue) for queue in queues), default=0)):
        for queue in queues:
            if turn < len(queue):
                yield queue[turn]


def _question(
    pool: Sequence[_Placed], position: int, keyed: set[str], prefix: str
) -> tuple[QuizQuestion, str] | None:
    sentence = pool[position].sentence
    for key in sentence.terms:
        if key.term_key in keyed or len(key.text) < QUIZ_TERM_MIN_CHARS:
            continue
        distractors = _distractors(pool, position, key)
        if len(distractors) < QUIZ_DISTRACTORS_MIN:
            continue
        question = _built(sentence, key, distractors, prefix)
        if question is not None:
            return question, key.term_key
    return None


def _distractors(
    pool: Sequence[_Placed], position: int, key: TermSpan
) -> list[tuple[ExplainerSentence, TermSpan]]:
    keyed = pool[position].sentence
    claims = sentence_claim_ids(keyed)
    keys = {key.term_key}
    texts = {key.text.casefold()}
    chosen: list[tuple[ExplainerSentence, TermSpan]] = []
    for offset in range(1, len(pool)):
        other = pool[(position + offset) % len(pool)].sentence
        if sentence_claim_ids(other) & claims:
            continue
        span = next((s for s in other.terms if _fits(s, keyed, keys, texts)), None)
        if span is None:
            continue
        chosen.append((other, span))
        keys.add(span.term_key)
        texts.add(span.text.casefold())
        if len(chosen) == QUIZ_DISTRACTORS_MAX:
            break
    return chosen


def _fits(span: TermSpan, keyed: ExplainerSentence, keys: set[str], texts: set[str]) -> bool:
    if span.term_key in keys or span.text.casefold() in texts or len(span.text) < QUIZ_TERM_MIN_CHARS:
        return False
    return not named_in(span.text, keyed)


def _built(
    sentence: ExplainerSentence,
    key: TermSpan,
    distractors: Sequence[tuple[ExplainerSentence, TermSpan]],
    prefix: str,
) -> QuizQuestion | None:
    options = sorted([(sentence, key), *distractors], key=lambda o: (o[1].text.casefold(), o[1].term_key))
    try:
        return QuizQuestion.model_validate(
            {
                "prompt": quiz_prompt(sentence.text, key.text),
                "options": [
                    {
                        "termKey": span.term_key,
                        "text": span.text,
                        "sentence": shown.model_copy(update={"id": f"{prefix}.{number}"}),
                    }
                    for number, (shown, span) in enumerate(options, start=1)
                ],
                "answer": options.index((sentence, key)),
            }
        )
    except (ValidationError, ValueError) as refused:
        logger.warning("a quiz question on %r is dropped: %s", key.text, refused)
        return None
