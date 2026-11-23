from __future__ import annotations

import asyncio
import logging
from collections import Counter
from collections.abc import AsyncIterable, Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from itertools import batched
from typing import Any

from app.core.errors import AppError, spend_refusal
from app.core.logging import request_id_scope
from app.research.structured import StructuredModel
from app.research.vocabulary import CANONICAL_LANGUAGE

from .golden import GENERATED_VERSION, GeneratedQuestion, GeneratedSet
from .question_writing import (
    COPIED,
    FACTS_PER_CRAFT,
    GENERATION_SEED,
    NOT_TRANSLATED,
    REWRITER_SYSTEM_PROMPT,
    WRITER_SYSTEM_PROMPT,
    WRITING_BATCH,
    Copied,
    CraftFacts,
    EvalFact,
    Written,
    WrittenQuestion,
    in_its_script,
    rewriting_message,
    writing_message,
    writing_schema,
    written_questions,
)

__all__ = [
    "GENERATION_CAP_USD",
    "GENERATION_TAG",
    "WRITING_CONCURRENCY",
    "WRITING_RESERVE_USD",
    "GenerationOutcome",
    "GenerationPlan",
    "WritingTools",
    "generate_questions",
    "generated_question",
]

logger = logging.getLogger(__name__)

GENERATION_TAG = "eval-questions-"
GENERATION_CAP_USD = Decimal("3.00")
WRITING_RESERVE_USD = Decimal("0.05")
WRITING_CONCURRENCY = 4
SPEND_STOP = "the spend cap was reached"
WRITER_FAILED = "the writer did not reply"
UNWRITTEN = "the spend cap was reached before the fact was written"
AGAIN_SUFFIX = "-again"
SHARE_DIGITS = 4


@dataclass(frozen=True)
class GenerationPlan:
    seed: int = GENERATION_SEED
    per_craft: int = FACTS_PER_CRAFT
    batch: int = WRITING_BATCH
    cap_usd: Decimal = GENERATION_CAP_USD
    concurrency: int = WRITING_CONCURRENCY


@dataclass(frozen=True)
class WritingTools:
    write: StructuredModel
    spent: Callable[[], Awaitable[Decimal]]
    tag: str


@dataclass
class GenerationOutcome:
    questions: list[GeneratedQuestion] = field(default_factory=list)
    crafts: int = 0
    facts: int = 0
    reused: int = 0
    batches: int = 0
    asked: int = 0
    kept_english: int = 0
    retried: int = 0
    rewritten: int = 0
    dropped: Counter[str] = field(default_factory=Counter)
    stopped: str | None = None
    model: str | None = None

    @property
    def kept_share(self) -> float | None:
        return round(self.kept_english / self.asked, SHARE_DIGITS) if self.asked else None

    def kept(self, craft_slug: str, written: Sequence[WrittenQuestion]) -> None:
        self.questions += [generated_question(craft_slug, one) for one in written]
        self.kept_english += sum(1 for one in written if one.language == CANONICAL_LANGUAGE)

    def generated(self, plan: GenerationPlan, *, revision: int, at: datetime) -> GeneratedSet:
        return GeneratedSet(
            version=GENERATED_VERSION,
            revision=revision,
            generated_at=at,
            model=self.model,
            seed=plan.seed,
            facts_per_craft=plan.per_craft,
            questions=tuple(sorted(self.questions, key=lambda question: (question.craft_slug, question.key))),
        )

    def summary(self) -> dict[str, Any]:
        return {
            "crafts": self.crafts,
            "facts": self.facts,
            "questions": len(self.questions),
            "reused": self.reused,
            "batches": self.batches,
            "asked": self.asked,
            "keptEnglish": self.kept_english,
            "keptShare": self.kept_share,
            "askedAgain": self.retried,
            "rewritten": self.rewritten,
            "dropped": dict(sorted(self.dropped.items())),
            "stopped": self.stopped,
            "model": self.model,
        }


def generated_question(craft_slug: str, written: WrittenQuestion) -> GeneratedQuestion:
    fact = written.fact
    return GeneratedQuestion(
        key=f"{fact.id}-{written.language}",
        craft_slug=craft_slug,
        question=written.question,
        expected=((str(fact.id), *(str(other) for other in fact.restatements)),),
        field=fact.field,
        fact=fact.id,
        language=written.language,
    )


async def generate_questions(
    crafts: AsyncIterable[CraftFacts],
    tools: WritingTools,
    plan: GenerationPlan,
    previous: GeneratedSet | None = None,
) -> GenerationOutcome:
    writing = _Writing(GenerationOutcome(), tools, plan, asyncio.Semaphore(plan.concurrency))
    kept = _previous_by_fact(previous)
    used: set[str] = set()
    try:
        async with asyncio.TaskGroup() as group:
            async for craft in crafts:
                fresh = [fact for fact in craft.sampled if str(fact.id) not in used]
                used.update(str(fact.id) for fact in fresh)
                writing.outcome.crafts += 1
                writing.outcome.facts += len(fresh)
                for batch in batched(_reused(writing.outcome, craft, fresh, kept), plan.batch, strict=False):
                    group.create_task(_paced(writing, craft, batch))
    except ExceptionGroup as failed:
        raise failed.exceptions[0] from None
    return writing.outcome


@dataclass(frozen=True)
class _Writing:
    outcome: GenerationOutcome
    tools: WritingTools
    plan: GenerationPlan
    gate: asyncio.Semaphore


async def _paced(writing: _Writing, craft: CraftFacts, batch: Sequence[EvalFact]) -> None:
    async with writing.gate:
        if await _affordable(writing):
            await _written(writing, craft, batch)
        else:
            writing.outcome.dropped[UNWRITTEN] += len(batch)


async def _affordable(writing: _Writing) -> bool:
    outcome = writing.outcome
    if outcome.stopped is None and writing.plan.cap_usd - await writing.tools.spent() < WRITING_RESERVE_USD:
        outcome.stopped = SPEND_STOP
    return outcome.stopped is None


def _previous_by_fact(previous: GeneratedSet | None) -> dict[tuple[str, str], list[GeneratedQuestion]]:
    found: dict[tuple[str, str], list[GeneratedQuestion]] = {}
    for question in previous.questions if previous is not None else ():
        found.setdefault((question.craft_slug, str(question.fact)), []).append(question)
    return found


def _reused(
    outcome: GenerationOutcome,
    craft: CraftFacts,
    fresh: Sequence[EvalFact],
    kept: dict[tuple[str, str], list[GeneratedQuestion]],
) -> list[EvalFact]:
    waiting: list[EvalFact] = []
    for fact in fresh:
        earlier = _in_their_scripts(outcome, kept.get((craft.slug, str(fact.id)), []))
        if not earlier:
            waiting.append(fact)
            continue
        outcome.reused += len(earlier)
        outcome.questions += [_refreshed(question, fact) for question in earlier]
    return waiting


def _in_their_scripts(
    outcome: GenerationOutcome, earlier: Sequence[GeneratedQuestion]
) -> list[GeneratedQuestion]:
    kept: list[GeneratedQuestion] = []
    for question in earlier:
        if in_its_script(question.question, question.language):
            kept.append(question)
        else:
            outcome.dropped[NOT_TRANSLATED] += 1
    return kept


def _refreshed(question: GeneratedQuestion, fact: EvalFact) -> GeneratedQuestion:
    rejected = {str(claim) for claim in question.rejected}
    known = [str(fact.id), *(str(other) for other in fact.restatements), *question.facts[0]]
    alternatives = tuple(claim for claim in dict.fromkeys(known) if claim not in rejected)
    return question.model_copy(update={"expected": (alternatives,), "field": fact.field})


async def _written(writing: _Writing, craft: CraftFacts, batch: Sequence[EvalFact]) -> None:
    outcome = writing.outcome
    outcome.batches += 1
    request_id = f"{writing.tools.tag}-b{outcome.batches:05d}"
    user = writing_message(craft, batch, seed=writing.plan.seed)
    first = await _reply(writing, craft, batch, _Ask(WRITER_SYSTEM_PROMPT, user, request_id))
    if isinstance(first, str):
        outcome.dropped[first] += len(batch)
        return
    outcome.asked += len(batch)
    outcome.kept(craft.slug, first.questions)
    outcome.dropped.update(problem for problem in first.dropped if problem != COPIED)
    if first.copied:
        await _rewritten(writing, craft, first.copied, f"{request_id}{AGAIN_SUFFIX}")


async def _rewritten(writing: _Writing, craft: CraftFacts, copied: Sequence[Copied], request_id: str) -> None:
    outcome = writing.outcome
    pairs = {(item.fact.id, item.language) for item in copied}
    outcome.retried += len(pairs)
    again: Written | str = UNWRITTEN
    if await _affordable(writing):
        user = rewriting_message(craft, copied, seed=writing.plan.seed)
        facts = tuple(dict.fromkeys(item.fact for item in copied))
        again = await _reply(writing, craft, facts, _Ask(REWRITER_SYSTEM_PROMPT, user, request_id))
    found = [] if isinstance(again, str) else [q for q in again.questions if (q.fact.id, q.language) in pairs]
    outcome.kept(craft.slug, found)
    outcome.rewritten += len(found)
    if missed := len(pairs) - len(found):
        outcome.dropped[COPIED] += missed


@dataclass(frozen=True)
class _Ask:
    system: str
    user: str
    request_id: str


async def _reply(writing: _Writing, craft: CraftFacts, facts: Sequence[EvalFact], ask: _Ask) -> Written | str:
    try:
        with request_id_scope(ask.request_id):
            reply = await writing.tools.write(system=ask.system, user=ask.user, schema=writing_schema())
        written = written_questions(reply, craft, facts, seed=writing.plan.seed)
    except AppError as error:
        if spend_refusal(error):
            writing.outcome.stopped = SPEND_STOP
            return UNWRITTEN
        logger.warning("the questions of %s were not written: %s", craft.slug, error)
        return WRITER_FAILED
    writing.outcome.model = reply.model or writing.outcome.model
    return written
