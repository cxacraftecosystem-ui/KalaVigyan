from collections.abc import Sequence
from dataclasses import dataclass

__all__ = ["SHARD_VARIABLE", "Shard", "dealt", "parse_shard"]

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


def dealt[T](items: Sequence[T], shard: Shard) -> list[T]:
    return list(items[shard.index - 1 :: shard.total])
