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

from .golden import GENERATED_VERSION, GeneratedQuestion, GeneratedSet
from .question_writing import (
    FACTS_PER_CRAFT,
    GENERATION_SEED,
    WRITER_SYSTEM_PROMPT,
    WRITING_BATCH,
    CraftFacts,
    EvalFact,
    WrittenQuestion,
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
    dropped: Counter[str] = field(default_factory=Counter)
    stopped: str | None = None
    model: str | None = None

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
        earlier = kept.get((craft.slug, str(fact.id)))
        if not earlier:
            waiting.append(fact)
            continue
        outcome.reused += len(earlier)
        outcome.questions += [_refreshed(question, fact) for question in earlier]
    return waiting


def _refreshed(question: GeneratedQuestion, fact: EvalFact) -> GeneratedQuestion:
    rejected = {str(claim) for claim in question.rejected}
    known = [str(fact.id), *(str(other) for other in fact.restatements), *question.facts[0]]
    alternatives = tuple(claim for claim in dict.fromkeys(known) if claim not in rejected)
    return question.model_copy(update={"expected": (alternatives,), "field": fact.field})


async def _written(writing: _Writing, craft: CraftFacts, batch: Sequence[EvalFact]) -> None:
    outcome, seed = writing.outcome, writing.plan.seed
    outcome.batches += 1
    try:
        with request_id_scope(f"{writing.tools.tag}-b{outcome.batches:05d}"):
            reply = await writing.tools.write(
                system=WRITER_SYSTEM_PROMPT,
                user=writing_message(craft, batch, seed=seed),
                schema=writing_schema(),
            )
        written = written_questions(reply, craft, batch, seed=seed)
    except AppError as error:
        if spend_refusal(error):
            outcome.stopped = SPEND_STOP
            outcome.dropped[UNWRITTEN] += len(batch)
            return
        logger.warning("the questions of %s were not written: %s", craft.slug, error)
        outcome.dropped[WRITER_FAILED] += len(batch)
        return
    outcome.model = reply.model or outcome.model
    outcome.questions += [generated_question(craft.slug, one) for one in written.questions]
    outcome.dropped.update(written.dropped)
