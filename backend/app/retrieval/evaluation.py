from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Callable, Collection, Hashable, Mapping, Sequence
from dataclasses import dataclass
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

__all__ = [
    "ALTERNATIVES_JOIN",
    "EVAL_DEPTH",
    "EVAL_MODE",
    "RECALL_DEPTH",
    "ExpectedFact",
    "GoldenQuestion",
    "QuestionResult",
    "RetrievalReport",
    "evaluate_golden",
    "fact_alternatives",
    "recall_at",
    "reciprocal_rank",
    "visible_claims",
]

RECALL_DEPTH = 5
EVAL_DEPTH = 10
EVAL_MODE = "HYBRID"
DIGITS = 4
ALTERNATIVES_JOIN = " or "

ExpectedFact = str | tuple[str, ...]


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
    recall: float
    reciprocal_rank: float
    missed: tuple[str, ...]
    field: str | None = None


@dataclass(frozen=True)
class RetrievalReport:
    results: tuple[QuestionResult, ...]
    absent: tuple[str, ...] = ()

    @property
    def recall_at_depth(self) -> float | None:
        return fmean(result.recall for result in self.results) if self.results else None

    @property
    def mean_reciprocal_rank(self) -> float | None:
        return fmean(result.reciprocal_rank for result in self.results) if self.results else None

    def by_field(self) -> dict[str, float]:
        recalls: dict[str, list[float]] = defaultdict(list)
        for result in self.results:
            if result.field is not None:
                recalls[result.field].append(result.recall)
        return {field: round(fmean(values), DIGITS) for field, values in sorted(recalls.items())}

    def as_dict(self) -> dict[str, Any]:
        return {
            "questions": len(self.results),
            f"recallAt{RECALL_DEPTH}": _rounded(self.recall_at_depth),
            "meanReciprocalRank": _rounded(self.mean_reciprocal_rank),
            "absent": list(self.absent),
            "misses": {result.key: list(result.missed) for result in self.results if result.missed},
            "recallByField": self.by_field(),
        }


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
) -> RetrievalReport:
    results: list[QuestionResult] = []
    absent: list[str] = []
    for question in golden:
        facts = [{claim_id(key): key for key in fact} for fact in question.facts]
        if present is not None:
            absent += [key for fact in facts for found, key in fact.items() if found not in present]
            facts = [kept for fact in facts if (kept := {f: k for f, k in fact.items() if f in present})]
        if facts:
            results.append(await _asked(retriever, question, facts))
    return RetrievalReport(tuple(results), tuple(absent))


async def visible_claims(session: AsyncSession, claim_ids: Collection[uuid.UUID]) -> set[uuid.UUID]:
    found = await session.scalars(
        select(Claim.id).where(
            Claim.id.in_(list(claim_ids)),
            Claim.status.not_in(HIDDEN_CLAIM_STATUSES),
            Claim.sensitivity == VISIBLE_SENSITIVITY,
        )
    )
    return set(found)


async def _asked(
    retriever: KnowledgeRetriever, question: GoldenQuestion, facts: Sequence[Mapping[uuid.UUID, str]]
) -> QuestionResult:
    query = KnowledgeQuery(
        craft_slug=question.craft_slug,
        text=question.question,
        mode=EVAL_MODE,
        fields=question.fields,
        limit=EVAL_DEPTH,
    )
    ranked = [hit.claim_id for hit in (await retriever.search(query)).claims]
    top = set(ranked[:RECALL_DEPTH])
    return QuestionResult(
        key=question.key,
        recall=recall_at(ranked, facts, RECALL_DEPTH),
        reciprocal_rank=reciprocal_rank(ranked, facts),
        missed=tuple(ALTERNATIVES_JOIN.join(fact.values()) for fact in facts if not top & set(fact)),
        field=question.field,
    )


def _rounded(value: float | None) -> float | None:
    return None if value is None else round(value, DIGITS)
