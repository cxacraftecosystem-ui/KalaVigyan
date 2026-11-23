from __future__ import annotations

import uuid
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass, replace
from itertools import batched
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.errors import AppError
from app.core.logging import redact_secrets
from app.models import Claim
from app.research.embedding import TextEmbedder, checked_vectors
from app.research.reranking import Reranker
from app.research.retrieval import HIDDEN_CLAIM_STATUSES, VISIBLE_SENSITIVITY

from .deadline import Deadline
from .eval_floors import (
    GENERATED,
    HAND_WRITTEN,
    MEAN_RECIPROCAL_RANK,
    RECALL_AT_5,
    RELEASE_SAMPLE,
    EvalFloors,
    FloorCheck,
    broken,
    floor_checks,
)
from .evaluation import EvalPace, GoldenQuestion, RetrievalReport, SetReport, evaluate_golden
from .golden import GeneratedSet
from .hybrid import SessionScopedSearch
from .indexing import EMBED_BATCH
from .miss_judging import (
    JudgeTools,
    MissDecision,
    judged_misses,
    miss_asks,
    next_revision,
    texts_to_read,
    with_decisions,
)
from .release_check import NO_GENERATED, ReleaseCheck, release_sample, rerank_warnings
from .text import query_text

__all__ = [
    "EVAL_CONCURRENCY",
    "READ_CHUNK",
    "EvalTools",
    "QuestionSets",
    "WeeklyRun",
    "claim_texts",
    "prefetched_embedder",
    "release_run",
    "scored",
    "set_checks",
    "set_measures",
    "visible_claims",
    "weekly_run",
]

EVAL_CONCURRENCY = 4
READ_CHUNK = 5000


@dataclass(frozen=True)
class EvalTools:
    sessions: async_sessionmaker[AsyncSession]
    embed: TextEmbedder
    rerank: Reranker
    claim_id: Callable[[str], uuid.UUID]
    concurrency: int = EVAL_CONCURRENCY


@dataclass(frozen=True)
class QuestionSets:
    hand_written: tuple[GoldenQuestion, ...]
    generated: GeneratedSet | None


@dataclass(frozen=True)
class WeeklyRun:
    reports: Mapping[str, SetReport]
    decisions: tuple[MissDecision, ...]
    judge_stopped: str | None
    revised: GeneratedSet | None
    checks: tuple[FloorCheck, ...]

    @property
    def below_floor(self) -> bool:
        return bool(broken(self.checks))

    @property
    def warnings(self) -> tuple[str, ...]:
        return rerank_warnings(self.reports)

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": True,
            "sets": {name: report.as_dict() for name, report in self.reports.items()},
            "judged": [decision.as_dict() for decision in self.decisions],
            "judgeStopped": self.judge_stopped,
            "generatedRevision": self.revised.revision if self.revised is not None else None,
            "floors": [check.as_dict() for check in self.checks],
            "belowFloor": self.below_floor,
            "warnings": list(self.warnings),
        }


async def prefetched_embedder(embed: TextEmbedder, questions: Sequence[str]) -> TextEmbedder:
    vectors: dict[str, list[float]] = {}

    async def fill(texts: Sequence[str]) -> None:
        for chunk in batched(texts, EMBED_BATCH, strict=False):
            vectors.update(
                zip(chunk, checked_vectors(await embed(list(chunk)), expected=len(chunk)), strict=True)
            )

    await fill(list(dict.fromkeys(query_text(question) for question in questions)))

    async def cached(texts: list[str]) -> list[list[float]]:
        await fill([text for text in dict.fromkeys(texts) if text not in vectors])
        return [vectors[text] for text in texts]

    return cached


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


async def scored(tools: EvalTools, questions: Sequence[GoldenQuestion], pace: EvalPace) -> SetReport:
    ids = {key: tools.claim_id(key) for question in questions for fact in question.facts for key in fact}
    async with tools.sessions() as session:
        present = await visible_claims(session, ids.values())
    embed = await prefetched_embedder(tools.embed, [question.question for question in questions])
    retriever = SessionScopedSearch(tools.sessions, embed=embed, rerank=tools.rerank)
    return await evaluate_golden(retriever, questions, claim_id=ids.__getitem__, present=present, pace=pace)


def set_checks(reports: Mapping[str, SetReport], floors: EvalFloors) -> tuple[FloorCheck, ...]:
    return tuple(
        check
        for name, report in reports.items()
        for order, found in report.compared().items()
        for check in floor_checks(
            _order_measures(found), floors.retrieval_floors(name, order), prefix=_prefix(name, order)
        )
    )


def set_measures(reports: Mapping[str, SetReport]) -> dict[str, float]:
    return {
        f"{_prefix(name, order)}{measure}": value
        for name, report in reports.items()
        for order, found in report.compared().items()
        for measure, value in _order_measures(found).items()
        if value is not None
    }


def _order_measures(found: RetrievalReport) -> dict[str, float | None]:
    return {RECALL_AT_5: found.recall_at_depth, MEAN_RECIPROCAL_RANK: found.mean_reciprocal_rank}


def _prefix(name: str, order: str) -> str:
    return f"{name}.{order}."


async def weekly_run(
    tools: EvalTools, sets: QuestionSets, *, judge: JudgeTools | None, floors: EvalFloors
) -> WeeklyRun:
    pace = EvalPace(concurrency=tools.concurrency)
    reports = {HAND_WRITTEN: await scored(tools, sets.hand_written, pace)}
    decisions: list[MissDecision] = []
    stopped, revised = None, None
    if sets.generated is not None:
        report = await scored(tools, sets.generated.questions, pace)
        if judge is not None:
            decisions, stopped = await _judged(tools, report.reranked, sets.generated, judge)
        reports[GENERATED] = _with_decisions(report, decisions)
        revised = next_revision(sets.generated, decisions)
    return WeeklyRun(reports, tuple(decisions), stopped, revised, set_checks(reports, floors))


async def release_run(
    tools: EvalTools, sets: QuestionSets, *, floors: EvalFloors, deadline: Deadline
) -> ReleaseCheck:
    pace = EvalPace(concurrency=tools.concurrency, deadline=deadline)
    generated = sets.generated.questions if sets.generated is not None else ()
    sample = release_sample(generated, hand_written=len(sets.hand_written))
    warnings = (NO_GENERATED,) if not sample else ()
    try:
        reports = {HAND_WRITTEN: await scored(tools, sets.hand_written, pace)}
        if sample:
            reports[RELEASE_SAMPLE] = await scored(tools, sample, pace)
    except AppError as error:
        return ReleaseCheck(warnings=warnings, error=f"{type(error).__name__}: {redact_secrets(str(error))}")
    return ReleaseCheck(reports=reports, checks=set_checks(reports, floors), warnings=warnings)


def _with_decisions(report: SetReport, decisions: Sequence[MissDecision]) -> SetReport:
    return replace(
        report,
        reranked=with_decisions(report.reranked, decisions),
        fused=with_decisions(report.fused, decisions),
    )


async def _judged(
    tools: EvalTools, report: RetrievalReport, generated: GeneratedSet, judge: JudgeTools
) -> tuple[list[MissDecision], str | None]:
    questions = {question.key: question for question in generated.questions}
    async with tools.sessions() as session:
        texts = await claim_texts(session, texts_to_read(report, questions))
    return await judged_misses(miss_asks(report, questions, texts), judge)
