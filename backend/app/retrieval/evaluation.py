from __future__ import annotations

import asyncio
import uuid
from collections import defaultdict
from collections.abc import Callable, Collection, Hashable, Mapping, Sequence
from dataclasses import dataclass, replace
from itertools import batched
from statistics import fmean
from typing import Any

from pydantic import Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput
from app.models import Claim
from app.research.base import ContractModel
from app.research.crafts import QUESTION_MAX_CHARS
from app.research.retrieval import (
    HIDDEN_CLAIM_STATUSES,
    VISIBLE_SENSITIVITY,
    KnowledgeQuery,
    KnowledgeRetriever,
)
from app.research.vocabulary import Discipline

from .deadline import Deadline

__all__ = [
    "ALTERNATIVES_JOIN",
    "EVAL_DEPTH",
    "EVAL_MODE",
    "RECALL_DEPTH",
    "WIDE_DEPTH",
    "EvalPace",
    "ExpectedFact",
    "GoldenQuestion",
    "Measures",
    "QuestionResult",
    "RetrievalReport",
    "claim_texts",
    "evaluate_golden",
    "fact_alternatives",
    "measures",
    "recall_at",
    "reciprocal_rank",
    "visible_claims",
]

RECALL_DEPTH = 5
WIDE_DEPTH = 20
EVAL_DEPTH = WIDE_DEPTH
EVAL_MODE = "HYBRID"
DIGITS = 4
ALTERNATIVES_JOIN = " or "
READ_CHUNK = 5000

ExpectedFact = str | tuple[str, ...]
FactClaims = Mapping[uuid.UUID, str]


def fact_alternatives(fact: ExpectedFact) -> tuple[str, ...]:
    return (fact,) if isinstance(fact, str) else fact


class GoldenQuestion(ContractModel):
    key: str = Field(min_length=1, max_length=80)
    craft_slug: str | None = Field(min_length=1, max_length=200)
    question: str = Field(min_length=1, max_length=QUESTION_MAX_CHARS)
    expected: tuple[ExpectedFact, ...] = Field(min_length=1)
    field: Discipline | None = None
    fields: tuple[Discipline, ...] = ()

    @field_validator("expected")
    @classmethod
    def _distinct(cls, values: tuple[ExpectedFact, ...]) -> tuple[ExpectedFact, ...]:
        facts = [fact_alternatives(value) for value in values]
        if not all(facts):
            raise ValueError("Each expected fact names at least one claim that states it")
        claims = [claim for fact in facts for claim in fact]
        if len(set(claims)) != len(claims):
            raise ValueError("Each expected hit may appear once")
        return values

    @property
    def facts(self) -> tuple[tuple[str, ...], ...]:
        return tuple(fact_alternatives(value) for value in self.expected)


@dataclass(frozen=True)
class QuestionResult:
    key: str
    ranked: tuple[uuid.UUID, ...]
    facts: tuple[FactClaims, ...]
    field: str | None = None
    craft_slug: str | None = None

    @property
    def recall(self) -> float:
        return recall_at(self.ranked, self.facts, RECALL_DEPTH)

    @property
    def recall_wide(self) -> float:
        return recall_at(self.ranked, self.facts, WIDE_DEPTH)

    @property
    def reciprocal_rank(self) -> float:
        return reciprocal_rank(self.ranked, self.facts)

    @property
    def missed(self) -> tuple[str, ...]:
        top = set(self.ranked[:RECALL_DEPTH])
        return tuple(ALTERNATIVES_JOIN.join(fact.values()) for fact in self.facts if not top & set(fact))

    @property
    def first(self) -> uuid.UUID | None:
        return self.ranked[0] if self.ranked else None

    @property
    def expected_claims(self) -> frozenset[uuid.UUID]:
        return frozenset(claim for fact in self.facts for claim in fact)

    def answered_by(self, claim_id: uuid.UUID, key: str) -> QuestionResult:
        if not self.facts:
            raise InvalidInput(f"Question {self.key} has no fact a claim could also state")
        widened = {**self.facts[0], claim_id: key}
        return replace(self, facts=(widened, *self.facts[1:]))


@dataclass(frozen=True)
class Measures:
    questions: int
    recall_at5: float | None
    mean_reciprocal_rank: float | None
    recall_at20: float | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "questions": self.questions,
            f"recallAt{RECALL_DEPTH}": self.recall_at5,
            "meanReciprocalRank": self.mean_reciprocal_rank,
            f"recallAt{WIDE_DEPTH}": self.recall_at20,
        }


def measures(results: Sequence[QuestionResult]) -> Measures:
    if not results:
        return Measures(0, None, None, None)
    return Measures(
        questions=len(results),
        recall_at5=round(fmean(result.recall for result in results), DIGITS),
        mean_reciprocal_rank=round(fmean(result.reciprocal_rank for result in results), DIGITS),
        recall_at20=round(fmean(result.recall_wide for result in results), DIGITS),
    )


@dataclass(frozen=True)
class RetrievalReport:
    results: tuple[QuestionResult, ...]
    absent: tuple[str, ...] = ()
    skipped: int = 0

    @property
    def complete(self) -> bool:
        return self.skipped == 0

    @property
    def recall_at_depth(self) -> float | None:
        return fmean(result.recall for result in self.results) if self.results else None

    @property
    def mean_reciprocal_rank(self) -> float | None:
        return fmean(result.reciprocal_rank for result in self.results) if self.results else None

    @property
    def recall_wide(self) -> float | None:
        return fmean(result.recall_wide for result in self.results) if self.results else None

    def overall(self) -> Measures:
        return measures(self.results)

    def by_field(self) -> dict[str, dict[str, Any]]:
        return _grouped(self.results, lambda result: result.field)

    def by_craft(self) -> dict[str, dict[str, Any]]:
        return _grouped(self.results, lambda result: result.craft_slug)

    def as_dict(self) -> dict[str, Any]:
        return {
            **self.overall().as_dict(),
            "skipped": self.skipped,
            "absent": list(self.absent),
            "misses": {result.key: list(result.missed) for result in self.results if result.missed},
            "byField": self.by_field(),
            "byCraft": self.by_craft(),
        }


@dataclass(frozen=True)
class EvalPace:
    concurrency: int = 1
    deadline: Deadline | None = None

    def __post_init__(self) -> None:
        if self.concurrency < 1:
            raise InvalidInput("An evaluation asks at least one question at a time")


def recall_at[K: Hashable](ranked: Sequence[K], facts: Sequence[Collection[K]], depth: int) -> float:
    if not facts or not all(facts):
        raise InvalidInput("Recall needs at least one expected fact, each stated by at least one claim")
    top = set(ranked[:depth])
    return sum(1 for fact in facts if top & set(fact)) / len(facts)


def reciprocal_rank[K: Hashable](ranked: Sequence[K], facts: Sequence[Collection[K]]) -> float:
    wanted = {claim for fact in facts for claim in fact}
    if not wanted:
        raise InvalidInput("A reciprocal rank needs at least one expected hit")
    return next((1.0 / rank for rank, key in enumerate(ranked, start=1) if key in wanted), 0.0)


async def evaluate_golden(
    retriever: KnowledgeRetriever,
    golden: Sequence[GoldenQuestion],
    *,
    claim_id: Callable[[str], uuid.UUID],
    present: Collection[uuid.UUID] | None = None,
    pace: EvalPace | None = None,
) -> RetrievalReport:
    asked, absent = _expected(golden, claim_id, present)
    paced = pace or EvalPace()
    gate = asyncio.Semaphore(paced.concurrency)

    async def one(question: GoldenQuestion, facts: tuple[FactClaims, ...]) -> QuestionResult | None:
        async with gate:
            if paced.deadline is not None and paced.deadline.passed():
                return None
            return await _asked(retriever, question, facts)

    try:
        async with asyncio.TaskGroup() as group:
            tasks = [group.create_task(one(question, facts)) for question, facts in asked]
    except ExceptionGroup as failed:
        raise failed.exceptions[0] from None
    found = [task.result() for task in tasks]
    results = tuple(result for result in found if result is not None)
    return RetrievalReport(results, tuple(absent), skipped=len(found) - len(results))


async def visible_claims(session: AsyncSession, claim_ids: Collection[uuid.UUID]) -> set[uuid.UUID]:
    found: set[uuid.UUID] = set()
    for chunk in batched(sorted(set(claim_ids)), READ_CHUNK, strict=False):
        found |= set(
            await session.scalars(
                select(Claim.id).where(
                    Claim.id.in_(list(chunk)),
                    Claim.status.not_in(HIDDEN_CLAIM_STATUSES),
                    Claim.sensitivity == VISIBLE_SENSITIVITY,
                )
            )
        )
    return found


async def claim_texts(session: AsyncSession, claim_ids: Collection[uuid.UUID]) -> dict[uuid.UUID, str]:
    texts: dict[uuid.UUID, str] = {}
    for chunk in batched(sorted(set(claim_ids)), READ_CHUNK, strict=False):
        rows = await session.execute(select(Claim.id, Claim.text).where(Claim.id.in_(list(chunk))))
        texts |= {row.id: row.text for row in rows}
    return texts


def _expected(
    golden: Sequence[GoldenQuestion],
    claim_id: Callable[[str], uuid.UUID],
    present: Collection[uuid.UUID] | None,
) -> tuple[list[tuple[GoldenQuestion, tuple[FactClaims, ...]]], list[str]]:
    asked: list[tuple[GoldenQuestion, tuple[FactClaims, ...]]] = []
    absent: list[str] = []
    for question in golden:
        facts = [{claim_id(key): key for key in fact} for fact in question.facts]
        if present is not None:
            absent += [key for fact in facts for found, key in fact.items() if found not in present]
            facts = [kept for fact in facts if (kept := {f: k for f, k in fact.items() if f in present})]
        if facts:
            asked.append((question, tuple(facts)))
    return asked, absent


async def _asked(
    retriever: KnowledgeRetriever, question: GoldenQuestion, facts: tuple[FactClaims, ...]
) -> QuestionResult:
    query = KnowledgeQuery(
        craft_slug=question.craft_slug,
        text=question.question,
        mode=EVAL_MODE,
        fields=question.fields,
        limit=EVAL_DEPTH,
    )
    ranked = tuple(hit.claim_id for hit in (await retriever.search(query)).claims)
    return QuestionResult(
        key=question.key, ranked=ranked, facts=facts, field=question.field, craft_slug=question.craft_slug
    )


def _grouped(
    results: Sequence[QuestionResult], group_of: Callable[[QuestionResult], str | None]
) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[QuestionResult]] = defaultdict(list)
    for result in results:
        group = group_of(result)
        if group is not None:
            groups[group].append(result)
    return {group: measures(found).as_dict() for group, found in sorted(groups.items())}
