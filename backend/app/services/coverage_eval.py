from __future__ import annotations

import logging
import uuid
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.core.errors import AppError
from app.core.logging import redact_secrets, request_id_scope
from app.data.craft_master_loader import DATA_DIR
from app.research.coverage_eval import (
    JUDGE_SYSTEM_PROMPT,
    AnswerMeasures,
    EvalQuestion,
    EvalQuestions,
    EvalReport,
    JudgeScores,
    QuestionResult,
    answer_measures,
    eval_report,
    judge_message,
    judge_schema,
    parsed_scores,
    rubric_score,
)
from app.research.explainer import Explainer
from app.research.structured import StructuredModel
from app.retrieval.eval_floors import JUDGE_MEAN, RUBRIC_MEAN, EvalFloors, broken, eval_floors, floor_checks

from .answer_runs import AnswerRun
from .answering import AnswerAsk

__all__ = [
    "EVAL_QUESTION_RESERVE_USD",
    "EVAL_SPEND_CAP_USD",
    "EVAL_TAG",
    "QUESTIONS_FILE",
    "EvalTools",
    "floor_report",
    "load_questions",
    "run_answer_eval",
]

logger = logging.getLogger(__name__)

EVAL_SPEND_CAP_USD = Decimal("30.00")
EVAL_QUESTION_RESERVE_USD = Decimal("2.50")
EVAL_TAG = "answer-eval-"
QUESTIONS_FILE = DATA_DIR / "eval" / "answer_questions.json"
BUDGET_STOP = "the spend cap was reached"
NO_EXPLAINER = "the answer keeps no explainer"
JUDGE_FAILED = "the judge did not score it"
ERROR_MAX_CHARS = 300
CENT = Decimal("0.0001")

SpentSince = Callable[[str, datetime], Awaitable[Decimal]]


@dataclass(frozen=True)
class EvalTools:
    answer: Callable[[AnswerAsk], Awaitable[AnswerRun]]
    explainer: Callable[[uuid.UUID], Awaitable[Explainer | None]]
    judge: StructuredModel
    spent: SpentSince
    off_question: Callable[[Explainer, str], Awaitable[int]] | None = None


@dataclass(frozen=True)
class _Run:
    tools: EvalTools
    tag: str
    started_at: datetime


@dataclass(frozen=True)
class _Scored:
    measures: AnswerMeasures | None = None
    scores: JudgeScores | None = None
    problem: str | None = None


def load_questions(path: Path = QUESTIONS_FILE) -> EvalQuestions:
    return EvalQuestions.model_validate_json(path.read_bytes().decode("utf-8"))


async def run_answer_eval(
    questions: Sequence[EvalQuestion], tools: EvalTools, *, started_at: datetime, cap_usd: Decimal
) -> EvalReport:
    capped = min(cap_usd, EVAL_SPEND_CAP_USD)
    run = _Run(tools, f"{EVAL_TAG}{uuid.uuid4().hex[:16]}", started_at)
    results: list[QuestionResult] = []
    stopped = None
    for number, question in enumerate(questions, start=1):
        if capped - await tools.spent(run.tag, started_at) < EVAL_QUESTION_RESERVE_USD:
            stopped = BUDGET_STOP
            break
        results.append(await _evaluated(run, question, f"{run.tag}-q{number:03d}"))
    spent = (await tools.spent(run.tag, started_at)).quantize(CENT)
    return eval_report(
        results, started_at=started_at, cap_usd=str(capped), spent_usd=str(spent), stopped=stopped
    )


async def _evaluated(run: _Run, question: EvalQuestion, tag: str) -> QuestionResult:
    answer_id: uuid.UUID | None = None
    try:
        with request_id_scope(tag):
            answered = await run.tools.answer(_ask(question))
            answer_id = answered.answer_id
            scored = await _scored(run, question, answered)
    except Exception as error:
        logger.warning("the evaluation question %s failed", question.id, exc_info=True)
        scored = _Scored(problem=f"{type(error).__name__}: {redact_secrets(str(error))}"[:ERROR_MAX_CHARS])
    spent = (await run.tools.spent(tag, run.started_at)).quantize(CENT)
    return QuestionResult(
        id=question.id,
        craft_slug=question.craft_slug,
        depth=question.depth,
        answer_id=answer_id,
        problem=scored.problem,
        measures=scored.measures,
        rubric=rubric_score(scored.measures) if scored.measures is not None else None,
        judge=scored.scores,
        judge_share=scored.scores.share() if scored.scores is not None else None,
        spent_usd=str(spent),
    )


async def _scored(run: _Run, question: EvalQuestion, answered: AnswerRun) -> _Scored:
    if answered.answer_id is None:
        return _Scored(problem=answered.problem)
    explainer = await run.tools.explainer(answered.answer_id)
    if explainer is None:
        return _Scored(problem=answered.problem or NO_EXPLAINER)
    found = run.tools.off_question
    off = await found(explainer, question.craft_slug) if found is not None else 0
    measures = answer_measures(explainer, question.fields, off_question=off)
    try:
        reply = await run.tools.judge(
            system=JUDGE_SYSTEM_PROMPT,
            user=judge_message(question.question, explainer, measures.expected),
            schema=judge_schema(),
        )
        scores = parsed_scores(reply)
    except AppError as error:
        logger.warning("the judge did not score %s: %s", question.id, error)
        return _Scored(
            measures=measures, problem=f"{JUDGE_FAILED}: {redact_secrets(str(error))}"[:ERROR_MAX_CHARS]
        )
    return _Scored(measures=measures, scores=scores, problem=answered.problem)


def floor_report(report: EvalReport, *, whole: bool, floors: EvalFloors | None = None) -> dict[str, Any]:
    applied = whole and report.stopped is None
    means = {JUDGE_MEAN: report.judge_mean, RUBRIC_MEAN: report.rubric_mean}
    checks = floor_checks(means, (floors or eval_floors()).answers.named())
    return {
        "floorsApplied": applied,
        "floors": [check.as_dict() for check in checks],
        "belowFloor": applied and bool(broken(checks)),
    }


def _ask(question: EvalQuestion) -> AnswerAsk:
    return AnswerAsk(question=question.question, depth=question.depth, craft_slug=question.craft_slug)
