import pytest

from tests.db.shards import Shard, dealt, parse_shard

COLLECTED = ["a", "b", "c", "d", "e", "f", "g"]


@pytest.mark.parametrize(
    ("index", "expected"),
    [(1, ["a", "d", "g"]), (2, ["b", "e"]), (3, ["c", "f"])],
)
def test_tests_are_dealt_in_turn_to_each_shard(index: int, expected: list[str]) -> None:
    assert dealt(COLLECTED, Shard(index, 3)) == expected


def test_every_test_lands_in_exactly_one_shard() -> None:
    collected = [f"tests/db/test_{index:02d}.py::test_case" for index in range(40)]
    placed = [test for index in (1, 2, 3) for test in dealt(collected, Shard(index, 3))]
    assert sorted(placed) == sorted(collected)
    assert len(placed) == len(set(placed))


def test_one_shard_keeps_every_test() -> None:
    assert dealt(COLLECTED, Shard(1, 1)) == COLLECTED


def test_a_shard_is_named_by_its_index_and_the_total() -> None:
    assert parse_shard("2/3") == Shard(2, 3)


@pytest.mark.parametrize("value", ["0/3", "4/3", "1/0", "1", "a/3", "-1/3", "1/3/5", ""])
def test_a_shard_outside_the_split_is_refused(value: str) -> None:
    with pytest.raises(ValueError, match="DB_TEST_SHARD"):
        parse_shard(value)
