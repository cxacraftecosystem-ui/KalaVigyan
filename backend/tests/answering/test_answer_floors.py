from datetime import UTC, datetime

from app.research.coverage_eval import EvalReport, QuestionResult, eval_report
from app.retrieval.eval_floors import parse_floors
from app.services.coverage_eval import floor_report
from app.services.eval_run_store import RunTimes, answers_record

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
    found = floor_report(report(judge=0.8, rubric=0.92), whole=True)
    assert [check["floor"] for check in found["floors"]] == [0.76, 0.88]
    assert found["floorsApplied"] and not found["belowFloor"]


def scored(number: int, *, rubric: float | None, judge: float | None) -> QuestionResult:
    return QuestionResult(
        id=f"q{number:02d}",
        craft_slug="Kutch-Ajrakh",
        depth="DETAILED",
        problem=None if rubric is not None and judge is not None else "the answer did not finish",
        rubric=rubric,
        judge_share=judge,
        spent_usd="0.1000",
    )


def run_of(results: list[QuestionResult]) -> EvalReport:
    return eval_report(
        results,
        started_at=datetime(2026, 11, 24, tzinfo=UTC),
        cap_usd="30.00",
        spent_usd="9.0000",
        stopped=None,
    )


TIMES = RunTimes(datetime(2026, 11, 24, tzinfo=UTC), datetime(2026, 11, 24, 1, tzinfo=UTC), None)


def test_a_whole_run_whose_failed_answers_leave_passing_means_is_below_its_floor() -> None:
    answered = [scored(number, rubric=0.93, judge=0.81) for number in range(1, 15)]
    failed = [scored(number, rubric=None, judge=None) for number in range(15, 25)]
    found = run_of(answered + failed)
    assert (found.asked, found.answered, found.rubric_mean, found.judge_mean) == (24, 14, 0.93, 0.81)
    floors = floor_report(found, whole=True)
    assert [check["held"] for check in floors["floors"]] == [True, True]
    assert floors["unscored"] == [f"q{number:02d}" for number in range(15, 25)]
    assert floors["floorsApplied"] and floors["belowFloor"]
    assert answers_record(found, TIMES, whole=True, fresh=False).floors_held is False


def test_a_question_the_judge_did_not_score_breaks_the_floors_of_a_whole_run() -> None:
    found = run_of([scored(1, rubric=0.95, judge=0.9), scored(2, rubric=0.95, judge=None)])
    floors = floor_report(found, whole=True)
    assert (floors["unscored"], floors["belowFloor"]) == (["q02"], True)
    assert answers_record(found, TIMES, whole=True, fresh=False).floors_held is False


def test_a_whole_run_that_scored_every_question_at_its_floors_holds_them() -> None:
    found = run_of([scored(number, rubric=0.93, judge=0.81) for number in range(1, 25)])
    floors = floor_report(found, whole=True)
    assert (floors["unscored"], floors["floorsApplied"], floors["belowFloor"]) == ([], True, False)
    assert answers_record(found, TIMES, whole=True, fresh=False).floors_held is True


def test_a_partial_run_with_failed_answers_is_still_never_compared() -> None:
    found = run_of([scored(1, rubric=0.93, judge=0.81), scored(2, rubric=None, judge=None)])
    floors = floor_report(found, whole=False)
    assert (floors["unscored"], floors["floorsApplied"], floors["belowFloor"]) == (["q02"], False, False)
    assert answers_record(found, TIMES, whole=False, fresh=False).floors_held is None
