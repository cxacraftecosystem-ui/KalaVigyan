from __future__ import annotations

import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from itertools import batched
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.errors import AppError
from app.core.logging import redact_secrets
from app.research.embedding import TextEmbedder, checked_vectors

from .deadline import Deadline
from .eval_floors import (
    GENERATED,
    HAND_WRITTEN,
    MEAN_RECIPROCAL_RANK,
    RECALL_AT_5,
    EvalFloors,
    FloorCheck,
    broken,
    floor_checks,
)
from .evaluation import (
    EvalPace,
    GoldenQuestion,
    RetrievalReport,
    claim_texts,
    evaluate_golden,
    visible_claims,
)
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
from .release_check import NO_GENERATED, ReleaseCheck, release_sample
from .text import query_text

__all__ = [
    "EVAL_CONCURRENCY",
    "EvalTools",
    "QuestionSets",
    "WeeklyRun",
    "prefetched_embedder",
    "release_run",
    "scored",
    "set_checks",
    "weekly_run",
]

EVAL_CONCURRENCY = 4


@dataclass(frozen=True)
class EvalTools:
    sessions: async_sessionmaker[AsyncSession]
    embed: TextEmbedder
    claim_id: Callable[[str], uuid.UUID]
    concurrency: int = EVAL_CONCURRENCY


@dataclass(frozen=True)
class QuestionSets:
    hand_written: tuple[GoldenQuestion, ...]
    generated: GeneratedSet | None


@dataclass(frozen=True)
class WeeklyRun:
    reports: Mapping[str, RetrievalReport]
    decisions: tuple[MissDecision, ...]
    judge_stopped: str | None
    revised: GeneratedSet | None
    checks: tuple[FloorCheck, ...]

    @property
    def below_floor(self) -> bool:
        return bool(broken(self.checks))

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": True,
            "sets": {name: report.as_dict() for name, report in self.reports.items()},
            "judged": [decision.as_dict() for decision in self.decisions],
            "judgeStopped": self.judge_stopped,
            "generatedRevision": self.revised.revision if self.revised is not None else None,
            "floors": [check.as_dict() for check in self.checks],
            "belowFloor": self.below_floor,
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


async def scored(tools: EvalTools, questions: Sequence[GoldenQuestion], pace: EvalPace) -> RetrievalReport:
    ids = {key: tools.claim_id(key) for question in questions for fact in question.facts for key in fact}
    async with tools.sessions() as session:
        present = await visible_claims(session, ids.values())
    embed = await prefetched_embedder(tools.embed, [question.question for question in questions])
    retriever = SessionScopedSearch(tools.sessions, embed=embed)
    return await evaluate_golden(retriever, questions, claim_id=ids.__getitem__, present=present, pace=pace)


def set_checks(reports: Mapping[str, RetrievalReport], floors: EvalFloors) -> tuple[FloorCheck, ...]:
    return tuple(
        check
        for name, report in reports.items()
        for check in floor_checks(
            {RECALL_AT_5: report.recall_at_depth, MEAN_RECIPROCAL_RANK: report.mean_reciprocal_rank},
            floors.retrieval_floors(name),
            prefix=f"{name}.",
        )
    )


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
            decisions, stopped = await _judged(tools, report, sets.generated, judge)
        reports[GENERATED] = with_decisions(report, decisions)
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
            reports[GENERATED] = await scored(tools, sample, pace)
    except AppError as error:
        return ReleaseCheck(warnings=warnings, error=f"{type(error).__name__}: {redact_secrets(str(error))}")
    return ReleaseCheck(reports=reports, checks=set_checks(reports, floors), warnings=warnings)


async def _judged(
    tools: EvalTools, report: RetrievalReport, generated: GeneratedSet, judge: JudgeTools
) -> tuple[list[MissDecision], str | None]:
    questions = {question.key: question for question in generated.questions}
    async with tools.sessions() as session:
        texts = await claim_texts(session, texts_to_read(report, questions))
    return await judged_misses(miss_asks(report, questions, texts), judge)
