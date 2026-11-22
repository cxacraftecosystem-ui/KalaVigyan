from collections import Counter
from typing import Any

from app.research.judge_eval import (
    JudgeCases,
    duplicate_asks,
    duplicate_scores,
    floor_checks,
    novelty_asks,
    novelty_scores,
)
from app.services.judge_eval import judge_cases, judge_report

from .fakes import JUDGE_MODEL, FakeJudge
from .judge_replies import compared, verdict

CLEARED_ON_2026_11_22 = {
    "sanganer-monsoon-effects",
    "sanganer-hari-sarana-drying",
    "sanganer-dhawai-beside-madder",
    "sanganer-oldenlandia-beside-madder",
    "sanganer-two-findings-of-one-study",
}


def test_the_shipped_set_holds_the_sanganeri_cases_with_their_labels_and_its_floors() -> None:
    cases = judge_cases()
    assert Counter(case.label for case in cases.duplicate) == {"DISTINCT": 8, "DIFFERS": 3, "SAME": 2}
    assert Counter(case.label for case in cases.novelty) == {"ADDS": 4, "NOT_ADDS": 3}
    labelled = {case.key: case.label for case in cases.duplicate}
    assert {labelled[key] for key in CLEARED_ON_2026_11_22} == {"DISTINCT"}
    assert {case.key: case.label for case in cases.novelty}["sanganer-indigofera"] == "ADDS"
    floors = cases.floors
    assert (floors.duplicate_accuracy, floors.distinct_kept, floors.novelty_accuracy) == (0.8, 0.85, 0.8)


def test_scores_are_shares_of_cases_judged_as_labelled() -> None:
    cases = judge_cases()
    found = {case.key: case.label for case in cases.duplicate}
    found["sanganer-monsoon-effects"] = "DIFFERS"
    scores = duplicate_scores(cases.duplicate, found)
    assert scores.measures == {"duplicate.accuracy": 0.9231, "duplicate.distinctKept": 0.875}
    assert list(scores.wrong) == [
        {"key": "sanganer-monsoon-effects", "label": "DISTINCT", "judged": "DIFFERS"}
    ]
    novelty = novelty_scores(cases.novelty, {case.key: True for case in cases.novelty})
    assert novelty.measures == {"novelty.accuracy": 0.5714}
    checks = floor_checks({**scores.measures, **novelty.measures}, cases.floors)
    assert [(check.measure, check.held) for check in checks] == [
        ("duplicate.accuracy", True),
        ("duplicate.distinctKept", True),
        ("novelty.accuracy", False),
    ]


def labelled_replies(cases: JudgeCases, relation: dict[str, str] | None = None) -> list[dict[str, Any]]:
    comparisons = [
        compared(ask.candidate.ref, ask.held[0].id, (relation or {}).get(case.key, case.label))
        for case, ask in zip(cases.duplicate, duplicate_asks(cases.duplicate), strict=True)
    ]
    verdicts = [
        verdict(ask.candidate.ref, adds=case.label == "ADDS", reason=case.why)
        for case, ask in zip(cases.novelty, novelty_asks(cases.novelty), strict=True)
    ]
    return [{"comparisons": comparisons}, {"verdicts": verdicts}]


async def test_a_judge_that_answers_as_labelled_holds_every_floor() -> None:
    cases = judge_cases()
    report = await judge_report(cases, (FakeJudge(*labelled_replies(cases)),))
    assert (report["ok"], report["belowFloor"], report["wrong"]) == (True, False, [])
    assert report["measures"] == {
        "duplicate.accuracy": 1.0,
        "duplicate.distinctKept": 1.0,
        "novelty.accuracy": 1.0,
    }
    assert report["models"] == {"duplicate": JUDGE_MODEL, "novelty": JUDGE_MODEL}


async def test_a_judge_that_calls_compatible_facts_a_disagreement_breaks_the_floor() -> None:
    cases = judge_cases()
    every_differs = {case.key: "DIFFERS" for case in cases.duplicate}
    report = await judge_report(cases, (FakeJudge(*labelled_replies(cases, every_differs)),))
    assert report["belowFloor"] is True
    assert report["measures"]["duplicate.distinctKept"] == 0.0
    assert report["measures"]["duplicate.accuracy"] == 0.2308


async def test_a_judge_that_cannot_answer_is_a_failed_run_not_a_score() -> None:
    report = await judge_report(judge_cases(), (FakeJudge({"comparisons": []}),))
    assert (report["ok"], report["belowFloor"]) == (False, False)
    assert "unanswered" in report["error"]
