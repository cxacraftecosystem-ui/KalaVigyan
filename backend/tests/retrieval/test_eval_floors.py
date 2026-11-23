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

MARGIN = 0.05
ENGLISH, OTHERS = 58, 111
FUSED_ENGLISH, FUSED_OTHERS = 142, 120
GENERATED_RERANKED = (
    (ENGLISH * 1.000 + OTHERS * 0.991) / (ENGLISH + OTHERS),
    (ENGLISH * 0.855 + OTHERS * 0.950) / (ENGLISH + OTHERS),
)
GENERATED_FUSED = (
    (FUSED_ENGLISH * 0.9507 + FUSED_OTHERS * 0.9917) / (FUSED_ENGLISH + FUSED_OTHERS),
    (FUSED_ENGLISH * 0.7505 + FUSED_OTHERS * 0.9435) / (FUSED_ENGLISH + FUSED_OTHERS),
)
LIVE = {
    ("handWritten", "reranked"): (0.987, 0.982),
    ("handWritten", "fused"): (1.000, 0.932),
    ("generated", "reranked"): GENERATED_RERANKED,
    ("generated", "fused"): GENERATED_FUSED,
    ("releaseSample", "reranked"): (1.000, 0.9104),
    ("releaseSample", "fused"): (0.9508, 0.7767),
}
FLOORS = {
    ("handWritten", "reranked"): {"recallAt5": 0.93, "meanReciprocalRank": 0.93},
    ("handWritten", "fused"): {"recallAt5": 0.95, "meanReciprocalRank": 0.88},
    ("generated", "reranked"): {"recallAt5": 0.94, "meanReciprocalRank": 0.86},
    ("generated", "fused"): {"recallAt5": 0.91, "meanReciprocalRank": 0.78},
    ("releaseSample", "reranked"): {"recallAt5": 0.95, "meanReciprocalRank": 0.86},
    ("releaseSample", "fused"): {"recallAt5": 0.90, "meanReciprocalRank": 0.72},
}
SHOWN_ONCE_RUBRIC_LOWEST = 0.872
LIVE_ANSWERS = {"judgeMean": 0.815, "rubricMean": SHOWN_ONCE_RUBRIC_LOWEST}
ANSWER_FLOORS = {"judgeMean": 0.76, "rubricMean": 0.82}


def rounded_down_below(live: float, floor: float) -> bool:
    return live - MARGIN - 0.01 < floor <= live - MARGIN + 1e-9


def test_each_set_and_order_starts_at_its_live_numbers_less_a_margin_rounded_down() -> None:
    floors = eval_floors()
    for (name, order), expected in FLOORS.items():
        assert floors.retrieval_floors(name, order) == expected, (name, order)
        recall, rank = LIVE[(name, order)]
        assert rounded_down_below(recall, expected["recallAt5"]), (name, order)
        assert rounded_down_below(rank, expected["meanReciprocalRank"]), (name, order)
    assert json.loads(FLOORS_FILE.read_text(encoding="utf-8"))["version"] == 2


def test_the_answer_floors_start_at_the_claude_judge_s_numbers_less_a_margin() -> None:
    assert eval_floors().answers.named() == ANSWER_FLOORS
    for name, floor in ANSWER_FLOORS.items():
        assert rounded_down_below(LIVE_ANSWERS[name], floor), name


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


def test_the_floors_file_names_floors_per_set_and_order_and_only_known_ones() -> None:
    plain = {"version": 2, "retrieval": {"handWritten": {"reranked": {"recallAt5": 0.5}}}, "answers": {}}
    parsed = parse_floors(plain)
    assert parsed.retrieval_floors("handWritten", "reranked") == {"recallAt5": 0.5}
    assert parsed.retrieval_floors("handWritten", "fused") == {}
    assert parsed.retrieval_floors("releaseSample", "reranked") == {}
    with pytest.raises(InvalidInput, match="orders reranked, fused"):
        parsed.retrieval_floors("handWritten", "vector")
    with pytest.raises(InvalidInput, match="version 2"):
        parse_floors({**plain, "version": 3})
    with pytest.raises(InvalidInput, match="malformed"):
        parse_floors({**plain, "retrieval": {"someOther": {"fused": {"recallAt5": 0.5}}}})
    with pytest.raises(InvalidInput, match="malformed"):
        parse_floors({**plain, "retrieval": {"handWritten": {"vector": {"recallAt5": 0.5}}}})
    with pytest.raises(InvalidInput, match="malformed"):
        parse_floors({**plain, "retrieval": {"handWritten": {"fused": {"recallAt5": 1.5}}}})


def test_a_version_1_file_is_migrated_with_its_floors_on_the_fused_order() -> None:
    first = {
        "version": 1,
        "about": "kept",
        "retrieval": {"handWritten": {"recallAt5": 0.82, "meanReciprocalRank": 0.64}, "generated": {}},
        "answers": {"judgeMean": 0.85},
    }
    migrated = parse_floors(first)
    assert (migrated.version, migrated.about) == (2, "kept")
    assert migrated.retrieval_floors("handWritten", "fused") == {
        "recallAt5": 0.82,
        "meanReciprocalRank": 0.64,
    }
    assert migrated.retrieval_floors("handWritten", "reranked") == {}
    assert migrated.retrieval_floors("generated", "fused") == {}
    assert migrated.answers.named() == {"judgeMean": 0.85}
    with pytest.raises(InvalidInput, match="per question set"):
        parse_floors({**first, "retrieval": ["handWritten"]})
