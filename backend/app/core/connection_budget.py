from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

__all__ = [
    "API",
    "BLUE_GREEN_SLOTS",
    "BUDGETS",
    "CONTRIBUTIONS",
    "FETCHER",
    "NO_DATABASE",
    "POOLER_HEADROOM",
    "POOLER_SESSIONS",
    "PROCESS_VARIABLE",
    "RUN_CONNECTIONS",
    "SCRIPT",
    "UNNAMED_COUNTING",
    "WORKER",
    "PoolBudget",
    "ProcessBudget",
    "most_runs",
    "peak_sessions",
    "process_role",
]

POOLER_SESSIONS = 30
POOLER_HEADROOM = 4
BLUE_GREEN_SLOTS = 2
RUN_CONNECTIONS = 2
PROCESS_VARIABLE = "KV_PROCESS"

API = "api"
CONTRIBUTIONS = "contributions"
FETCHER = "fetcher"
SCRIPT = "script"
WORKER = "worker"


@dataclass(frozen=True)
class PoolBudget:
    kept: int
    burst: int

    def __post_init__(self) -> None:
        if self.kept < 1 or self.burst < 0:
            raise ValueError(f"a pool keeps at least one connection and bursts by none or more: {self}")

    @property
    def most(self) -> int:
        return self.kept + self.burst


@dataclass(frozen=True)
class ProcessBudget:
    main: PoolBudget
    counting: PoolBudget

    @property
    def most(self) -> int:
        return self.main.most + self.counting.most


BUDGETS: Mapping[str, ProcessBudget] = MappingProxyType(
    {
        API: ProcessBudget(main=PoolBudget(kept=2, burst=3), counting=PoolBudget(kept=1, burst=1)),
        CONTRIBUTIONS: ProcessBudget(main=PoolBudget(kept=1, burst=3), counting=PoolBudget(kept=1, burst=0)),
        WORKER: ProcessBudget(main=PoolBudget(kept=1, burst=1), counting=PoolBudget(kept=1, burst=0)),
        SCRIPT: ProcessBudget(main=PoolBudget(kept=1, burst=2), counting=PoolBudget(kept=1, burst=0)),
    }
)
NO_DATABASE = frozenset({FETCHER})
UNNAMED_COUNTING = PoolBudget(kept=2, burst=6)


def process_role(named: str | None, *, production: bool) -> str | None:
    role = (named or "").strip()
    if not role:
        return SCRIPT if production else None
    if role in NO_DATABASE:
        raise ValueError(f"the {role} process has no database and no connection budget")
    if role not in BUDGETS:
        raise ValueError(
            f"{PROCESS_VARIABLE}={role!r} names no connection budget; known: {', '.join(BUDGETS)}"
        )
    return role


def peak_sessions(instances: Mapping[str, int]) -> int:
    return sum(BUDGETS[role].most * count for role, count in instances.items() if role not in NO_DATABASE)


def most_runs(pool: PoolBudget) -> int:
    return max(1, pool.most // RUN_CONNECTIONS)
