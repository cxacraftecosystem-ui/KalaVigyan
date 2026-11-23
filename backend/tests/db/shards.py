from collections.abc import Mapping
from dataclasses import dataclass

__all__ = ["SHARD_VARIABLE", "Shard", "module_of", "parse_shard", "split_modules"]

SHARD_VARIABLE = "DB_TEST_SHARD"


@dataclass(frozen=True)
class Shard:
    index: int
    total: int


def parse_shard(value: str) -> Shard:
    index, separator, total = value.partition("/")
    if not separator or not index.isdigit() or not total.isdigit():
        raise ValueError(f"{SHARD_VARIABLE} must read <index>/<total>, got {value!r}")
    shard = Shard(int(index), int(total))
    if not 1 <= shard.index <= shard.total:
        raise ValueError(f"{SHARD_VARIABLE} {value!r} names no shard of {shard.total}")
    return shard


def module_of(node_id: str) -> str:
    return node_id.split("::", 1)[0]


def split_modules(weights: Mapping[str, int], total: int) -> list[list[str]]:
    shards: list[list[str]] = [[] for _ in range(total)]
    loads = [0] * total
    for module in sorted(weights, key=lambda name: (-weights[name], name)):
        lightest = min(range(total), key=lambda position: (loads[position], position))
        shards[lightest].append(module)
        loads[lightest] += weights[module]
    return [sorted(shard) for shard in shards]
