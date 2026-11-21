import json

import pytest

from app.core.errors import InvalidInput
from app.retrieval.eval_floors import (
    FLOORS_FILE,
    FloorCheck,
    broken,
    eval_floors,
    floor_checks,
    parse_floors,
)

LIVE_RECALL_AT_5 = 0.87
LIVE_MEAN_RECIPROCAL_RANK = 0.69
MARGIN = 0.05


def test_the_floors_start_at_the_live_numbers_less_a_margin() -> None:
    floors = eval_floors()
    assert floors.retrieval_floors("handWritten") == {
        "recallAt5": pytest.approx(LIVE_RECALL_AT_5 - MARGIN),
        "meanReciprocalRank": pytest.approx(LIVE_MEAN_RECIPROCAL_RANK - MARGIN),
    }
    assert floors.retrieval_floors("handWritten") == {"recallAt5": 0.82, "meanReciprocalRank": 0.64}
    assert floors.retrieval_floors("generated") == {}
    assert floors.answers.named() == {"judgeMean": 0.85, "rubricMean": 0.85}
    assert json.loads(FLOORS_FILE.read_text(encoding="utf-8"))["version"] == 1


def test_a_floor_holds_at_or_above_its_value_after_rounding() -> None:
    assert FloorCheck("m", 0.82, 0.82).held
    assert FloorCheck("m", 0.82, 0.819996).held
    assert not FloorCheck("m", 0.82, 0.8199).held
    assert not FloorCheck("m", 0.82, None).held


def test_only_the_named_floors_are_checked_and_a_missing_value_breaks_its_floor() -> None:
    checks = floor_checks({"recallAt5": 0.9, "meanReciprocalRank": None}, {"recallAt5": 0.82}, prefix="set.")
    assert [(check.measure, check.held) for check in checks] == [("set.recallAt5", True)]
    checks = floor_checks({"recallAt5": 0.9}, {"recallAt5": 0.82, "meanReciprocalRank": 0.64})
    assert [check.measure for check in broken(checks)] == ["meanReciprocalRank"]
    assert checks[0].as_dict() == {"measure": "recallAt5", "floor": 0.82, "value": 0.9, "held": True}


def test_the_floors_file_is_versioned_and_names_only_known_sets() -> None:
    plain = {"version": 1, "retrieval": {"handWritten": {"recallAt5": 0.5}}, "answers": {}}
    assert parse_floors(plain).retrieval_floors("handWritten") == {"recallAt5": 0.5}
    with pytest.raises(InvalidInput, match="version 1"):
        parse_floors({**plain, "version": 2})
    with pytest.raises(InvalidInput, match="malformed"):
        parse_floors({**plain, "retrieval": {"someOther": {"recallAt5": 0.5}}})
    with pytest.raises(InvalidInput, match="malformed"):
        parse_floors({**plain, "retrieval": {"handWritten": {"recallAt5": 1.5}}})
