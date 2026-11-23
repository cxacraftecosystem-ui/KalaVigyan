from __future__ import annotations

import json
from pathlib import Path

import pytest

from hygiene.baseline import BaselineError, RatchetStep, compare, read_baseline, write_baseline

COUNTS = {"oversizedFiles": 3, "longFunctions": 10, "wideFunctions": 0, "registerEntries": 7}


def test_written_baseline_reads_back(tmp_path: Path) -> None:
    path = tmp_path / "baseline.json"
    write_baseline(path, COUNTS)
    assert read_baseline(path) == COUNTS


def test_written_file_is_lf_utf8_json(tmp_path: Path) -> None:
    path = tmp_path / "baseline.json"
    write_baseline(path, COUNTS)
    raw = path.read_bytes()
    assert b"\r" not in raw and raw.endswith(b"}\n")
    assert json.loads(raw) == {"schemaVersion": 2, "counts": COUNTS}


def test_missing_baseline_fails_loudly(tmp_path: Path) -> None:
    with pytest.raises(BaselineError, match="--update-baseline"):
        read_baseline(tmp_path / "absent.json")


def test_a_schema_version_1_baseline_without_the_register_count_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "baseline.json"
    budgets = {"oversizedFiles": 3, "longFunctions": 10, "wideFunctions": 0}
    path.write_text(json.dumps({"schemaVersion": 1, "counts": budgets}), encoding="utf-8")
    with pytest.raises(BaselineError, match="schemaVersion 2"):
        read_baseline(path)


@pytest.mark.parametrize(
    "payload",
    [
        {"schemaVersion": 1, "counts": COUNTS},
        {"schemaVersion": 3, "counts": COUNTS},
        {"counts": COUNTS},
        {"schemaVersion": 2, "counts": {"oversizedFiles": 1}},
        {
            "schemaVersion": 2,
            "counts": {key: value for key, value in COUNTS.items() if key != "registerEntries"},
        },
        {"schemaVersion": 2, "counts": {**COUNTS, "extra": 1}},
        {"schemaVersion": 2, "counts": {**COUNTS, "wideFunctions": -1}},
        {"schemaVersion": 2, "counts": {**COUNTS, "registerEntries": -1}},
        {"schemaVersion": 2, "counts": {**COUNTS, "wideFunctions": True}},
        {"schemaVersion": 2, "counts": {**COUNTS, "wideFunctions": "2"}},
        [],
    ],
)
def test_malformed_baseline_is_refused(tmp_path: Path, payload: object) -> None:
    path = tmp_path / "baseline.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(BaselineError):
        read_baseline(path)


def test_compare_marks_rises_and_falls() -> None:
    current = {"oversizedFiles": 4, "longFunctions": 9, "wideFunctions": 0, "registerEntries": 6}
    steps = compare(COUNTS, current)
    assert [(step.name, step.rose, step.fell) for step in steps] == [
        ("oversizedFiles", True, False),
        ("longFunctions", False, True),
        ("wideFunctions", False, False),
        ("registerEntries", False, True),
    ]


@pytest.mark.parametrize(
    ("step", "holds"),
    [
        (RatchetStep("longFunctions", 10, 10), True),
        (RatchetStep("longFunctions", 10, 11), False),
        (RatchetStep("longFunctions", 10, 9), False),
        (RatchetStep("registerEntries", 7, 7), True),
        (RatchetStep("registerEntries", 7, 8), False),
        (RatchetStep("registerEntries", 7, 6), True),
    ],
)
def test_a_budget_must_equal_its_baseline_and_the_register_may_only_fall(
    step: RatchetStep, holds: bool
) -> None:
    assert step.holds is holds
