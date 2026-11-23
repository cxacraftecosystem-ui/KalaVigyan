import pytest

from tests.db.shards import Shard, module_of, parse_shard, split_modules


def test_the_heaviest_module_goes_to_the_lightest_shard_first() -> None:
    weights = {"a": 5, "b": 4, "c": 3, "d": 3, "e": 1}
    assert split_modules(weights, 2) == [["a", "d"], ["b", "c", "e"]]


def test_every_module_lands_in_exactly_one_shard() -> None:
    weights = {f"tests/db/test_{index:02d}.py": index % 7 + 1 for index in range(40)}
    shards = split_modules(weights, 3)
    placed = [module for shard in shards for module in shard]
    assert sorted(placed) == sorted(weights)
    assert len(placed) == len(set(placed))


def test_the_split_does_not_depend_on_the_order_modules_were_collected() -> None:
    weights = {"x": 2, "y": 2, "z": 2, "w": 1}
    reordered = dict(reversed(list(weights.items())))
    assert split_modules(weights, 3) == split_modules(reordered, 3) == [["w", "x"], ["y"], ["z"]]


def test_a_shard_is_named_by_its_index_and_the_total() -> None:
    assert parse_shard("2/3") == Shard(2, 3)


@pytest.mark.parametrize("value", ["0/3", "4/3", "1/0", "1", "a/3", "-1/3", "1/3/5", ""])
def test_a_shard_outside_the_split_is_refused(value: str) -> None:
    with pytest.raises(ValueError, match="DB_TEST_SHARD"):
        parse_shard(value)


def test_a_test_belongs_to_the_file_before_its_first_separator() -> None:
    assert module_of("tests/db/test_flows.py::TestA::test_b[1::2]") == "tests/db/test_flows.py"
