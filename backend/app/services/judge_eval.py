from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from app.core.errors import AppError
from app.research.candidate_judge import (
    comparison_request,
    novelty_request,
    parsed_comparisons,
    parsed_novelty,
)
from app.research.judge_eval import (
    JudgeCases,
    duplicate_asks,
    duplicate_scores,
    floor_checks,
    novelty_asks,
    novelty_scores,
)
from app.research.structured import StructuredModel

from .candidate_gates import asked_judges

__all__ = ["JUDGE_CASES_FILE", "judge_cases", "judge_report"]

JUDGE_CASES_FILE = Path(__file__).resolve().parents[1] / "data" / "eval" / "judge_cases.json"


def judge_cases(path: Path = JUDGE_CASES_FILE) -> JudgeCases:
    return JudgeCases.model_validate_json(path.read_text(encoding="utf-8"))


async def judge_report(cases: JudgeCases, ladder: Sequence[StructuredModel]) -> dict[str, Any]:
    try:
        relations, compare_model = await _relations(cases, ladder)
        adds, novelty_model = await _novelty(cases, ladder)
    except AppError as error:
        return {"ok": False, "error": str(error), "belowFloor": False}
    duplicate = duplicate_scores(cases.duplicate, relations)
    novelty = novelty_scores(cases.novelty, adds)
    measures = {**duplicate.measures, **novelty.measures}
    checks = floor_checks(measures, cases.floors)
    return {
        "ok": True,
        "belowFloor": any(not check.held for check in checks),
        "models": {"duplicate": compare_model, "novelty": novelty_model},
        "cases": {"duplicate": len(cases.duplicate), "novelty": len(cases.novelty)},
        "measures": measures,
        "floors": [
            {"measure": check.measure, "value": check.value, "floor": check.floor, "held": check.held}
            for check in checks
        ],
        "wrong": [*duplicate.wrong, *novelty.wrong],
    }


async def _relations(
    cases: JudgeCases, ladder: Sequence[StructuredModel]
) -> tuple[dict[str, str], str | None]:
    asks = duplicate_asks(cases.duplicate)
    compared, model = await asked_judges(
        ladder, comparison_request(asks), lambda reply: parsed_comparisons(reply, asks)
    )
    return {key: found[0].relation for key, found in compared.items()}, model


async def _novelty(
    cases: JudgeCases, ladder: Sequence[StructuredModel]
) -> tuple[dict[str, bool], str | None]:
    asks = novelty_asks(cases.novelty)
    verdicts, model = await asked_judges(
        ladder, novelty_request(asks), lambda reply: parsed_novelty(reply, asks)
    )
    return {key: verdict.adds for key, verdict in verdicts.items()}, model
