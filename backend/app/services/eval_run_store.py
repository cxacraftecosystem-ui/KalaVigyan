from __future__ import annotations

import logging
import re
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import session_scope
from app.core.errors import AppError
from app.models import EvalRun
from app.models.evaluation import EVAL_RUN_KINDS
from app.research.base import ContractModel
from app.research.coverage_eval import EvalReport
from app.retrieval.eval_floors import JUDGE_MEAN, RUBRIC_MEAN, FloorCheck, broken
from app.retrieval.eval_runs import WeeklyRun, set_measures
from app.retrieval.release_check import ReleaseCheck

from .coverage_eval import answer_checks, floors_applied, floors_hold

__all__ = [
    "ANSWERS",
    "EVAL_RUN_KINDS",
    "RELEASE_CHECK",
    "RETRIEVAL",
    "EvalKind",
    "EvalRunRecord",
    "RunTimes",
    "answers_record",
    "keep_run",
    "latest_eval_runs",
    "release_check_record",
    "release_commit",
    "store_eval_run",
    "weekly_record",
]

logger = logging.getLogger(__name__)

FINISHED = "SUCCEEDED"
SUMMARY_VERSION = 1
COMMIT = re.compile(r"^[0-9a-f]{40}$")

EvalKind = Literal["ANSWERS", "RETRIEVAL", "RELEASE_CHECK"]
ANSWERS: EvalKind = "ANSWERS"
RETRIEVAL: EvalKind = "RETRIEVAL"
RELEASE_CHECK: EvalKind = "RELEASE_CHECK"
KINDS: Mapping[str, EvalKind] = {kind: kind for kind in (ANSWERS, RETRIEVAL, RELEASE_CHECK)}


class StoredFloor(ContractModel):
    measure: str
    floor: float
    value: float | None


class RunSummary(ContractModel):
    schema_version: Literal[1] = SUMMARY_VERSION
    means: dict[str, float]
    floors: list[StoredFloor]


@dataclass(frozen=True)
class RunTimes:
    started_at: datetime
    finished_at: datetime
    release: str | None


@dataclass(frozen=True)
class EvalRunRecord:
    kind: EvalKind
    times: RunTimes
    spent_usd: Decimal
    cap_usd: Decimal | None
    means: Mapping[str, float]
    floors: Sequence[FloorCheck]
    floors_held: bool | None
    fresh: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "run": self.kind,
            "startedAt": self.times.started_at.isoformat(),
            "finishedAt": self.times.finished_at.isoformat(),
            "release": self.times.release,
            "spentUsd": str(self.spent_usd),
            "capUsd": None if self.cap_usd is None else str(self.cap_usd),
            "fresh": self.fresh,
            "floorsHeld": self.floors_held,
            "means": dict(self.means),
        }


def release_commit(release: str) -> str | None:
    return release if COMMIT.match(release) else None


def answers_record(report: EvalReport, times: RunTimes, *, whole: bool, fresh: bool) -> EvalRunRecord:
    checks = answer_checks(report)
    means = {JUDGE_MEAN: report.judge_mean, RUBRIC_MEAN: report.rubric_mean}
    return EvalRunRecord(
        kind=ANSWERS,
        times=times,
        spent_usd=Decimal(report.spent_usd),
        cap_usd=Decimal(report.cap_usd),
        means={name: value for name, value in means.items() if value is not None},
        floors=checks,
        floors_held=floors_hold(report, checks) if floors_applied(report, whole=whole) else None,
        fresh=fresh,
    )


def weekly_record(run: WeeklyRun, times: RunTimes, *, spent_usd: Decimal, cap_usd: Decimal) -> EvalRunRecord:
    return EvalRunRecord(
        kind=RETRIEVAL,
        times=times,
        spent_usd=spent_usd,
        cap_usd=cap_usd,
        means=set_measures(run.reports),
        floors=run.checks,
        floors_held=not run.below_floor,
    )


def release_check_record(check: ReleaseCheck, times: RunTimes, *, spent_usd: Decimal) -> EvalRunRecord:
    return EvalRunRecord(
        kind=RELEASE_CHECK,
        times=times,
        spent_usd=spent_usd,
        cap_usd=None,
        means=set_measures(check.reports),
        floors=check.checks,
        floors_held=not broken(check.checks) if check.complete else None,
    )


async def store_eval_run(session: AsyncSession, record: EvalRunRecord) -> uuid.UUID:
    summary = RunSummary(
        means=dict(record.means),
        floors=[StoredFloor(measure=c.measure, floor=c.floor, value=c.value) for c in record.floors],
    )
    row = EvalRun(
        suite=record.kind,
        gitSha=record.times.release,
        status=FINISHED,
        budgetUsd=record.cap_usd,
        costUsd=record.spent_usd,
        summary=summary.model_dump(mode="json", by_alias=True),
        startedAt=record.times.started_at,
        finishedAt=record.times.finished_at,
        floorsHeld=record.floors_held,
        fresh=record.fresh,
    )
    session.add(row)
    await session.flush()
    return row.id


async def keep_run(record: EvalRunRecord) -> dict[str, str | None]:
    try:
        async with session_scope() as session:
            run_id = await store_eval_run(session, record)
    except (AppError, SQLAlchemyError, OSError) as error:
        logger.error("the %s evaluation run was not stored: %s", record.kind, error)
        return {"storedRunId": None, "storeError": type(error).__name__}
    return {"storedRunId": str(run_id)}


async def latest_eval_runs(session: AsyncSession) -> dict[str, EvalRunRecord]:
    rows = await session.scalars(
        select(EvalRun)
        .where(EvalRun.suite.in_(EVAL_RUN_KINDS), EvalRun.status == FINISHED, EvalRun.finishedAt.is_not(None))
        .order_by(EvalRun.suite, EvalRun.finishedAt.desc())
        .distinct(EvalRun.suite)
    )
    found = (_record(row) for row in rows)
    return {record.kind: record for record in found if record is not None}


def _record(row: EvalRun) -> EvalRunRecord | None:
    try:
        summary = RunSummary.model_validate(row.summary)
    except ValidationError as error:
        logger.error("evaluation run %s keeps a summary off its shape and is left out: %s", row.id, error)
        return None
    kind = KINDS.get(row.suite)
    if row.startedAt is None or row.finishedAt is None or kind is None:
        return None
    return EvalRunRecord(
        kind=kind,
        times=RunTimes(started_at=row.startedAt, finished_at=row.finishedAt, release=row.gitSha),
        spent_usd=row.costUsd,
        cap_usd=row.budgetUsd,
        means=summary.means,
        floors=tuple(FloorCheck(floor.measure, floor.floor, floor.value) for floor in summary.floors),
        floors_held=row.floorsHeld,
        fresh=row.fresh,
    )
