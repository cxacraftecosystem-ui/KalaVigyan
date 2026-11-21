from datetime import UTC, datetime

from app.research.coverage_eval import EvalReport
from app.retrieval.eval_floors import parse_floors
from app.services.coverage_eval import floor_report

FLOORS = parse_floors({"version": 1, "retrieval": {}, "answers": {"judgeMean": 0.85, "rubricMean": 0.85}})


def report(*, judge: float | None, rubric: float | None, stopped: str | None = None) -> EvalReport:
    return EvalReport(
        started_at=datetime(2026, 11, 22, tzinfo=UTC),
        cap_usd="30.00",
        spent_usd="12.0000",
        stopped=stopped,
        asked=24,
        answered=24,
        rubric_mean=rubric,
        judge_mean=judge,
        questions=[],
    )


def test_a_whole_run_below_a_floor_is_reported_below_it() -> None:
    found = floor_report(report(judge=0.8, rubric=0.9), whole=True, floors=FLOORS)
    assert found["floorsApplied"] and found["belowFloor"]
    assert found["floors"] == [
        {"measure": "judgeMean", "floor": 0.85, "value": 0.8, "held": False},
        {"measure": "rubricMean", "floor": 0.85, "value": 0.9, "held": True},
    ]


def test_a_whole_run_at_its_floors_holds_them() -> None:
    found = floor_report(report(judge=0.85, rubric=0.85), whole=True, floors=FLOORS)
    assert found["floorsApplied"] and not found["belowFloor"]


def test_a_partial_or_stopped_run_is_never_compared() -> None:
    assert not floor_report(report(judge=0.1, rubric=0.1), whole=False, floors=FLOORS)["belowFloor"]
    stopped = floor_report(
        report(judge=0.1, rubric=0.1, stopped="the spend cap was reached"), whole=True, floors=FLOORS
    )
    assert (stopped["floorsApplied"], stopped["belowFloor"]) == (False, False)


def test_a_run_the_judge_never_scored_breaks_the_judge_floor() -> None:
    found = floor_report(report(judge=None, rubric=0.9), whole=True, floors=FLOORS)
    assert found["belowFloor"] and found["floors"][0]["value"] is None


def test_the_kept_floors_are_those_answer_quality_compares() -> None:
    found = floor_report(report(judge=0.86, rubric=0.86), whole=True)
    assert [check["floor"] for check in found["floors"]] == [0.85, 0.85]
