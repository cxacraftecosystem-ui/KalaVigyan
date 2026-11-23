import re
from collections import Counter
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.core.connection_budget import (
    API,
    BLUE_GREEN_SLOTS,
    BUDGETS,
    CONTRIBUTIONS,
    FETCHER,
    POOLER_HEADROOM,
    POOLER_SESSIONS,
    RUN_CONNECTIONS,
    SCRIPT,
    UNNAMED_COUNTING,
    WORKER,
    PoolBudget,
    most_runs,
    peak_sessions,
    process_role,
)
from app.core.db import process_pools
from app.scripts.contribution_worker import runs_at_once

REPO = Path(__file__).resolve().parents[2]
UNITS = REPO / "infra/deploy/units"
APP_ENV_FILE = "EnvironmentFile=/opt/kalavigyan/.env"
PROCESS_LINE = re.compile(r"^Environment=KV_PROCESS=(\S+)$", re.MULTILINE)


def unit_roles() -> dict[str, str]:
    roles: dict[str, str] = {}
    for path in sorted(UNITS.glob("*.service")):
        found = PROCESS_LINE.search(path.read_text(encoding="utf-8"))
        if found:
            roles[path.name] = found.group(1)
    return roles


def box_instances() -> Counter[str]:
    instances: Counter[str] = Counter()
    for unit, role in unit_roles().items():
        instances[role] += BLUE_GREEN_SLOTS if unit.endswith("@.service") else 1
    instances[SCRIPT] += 1
    return instances


def test_every_unit_that_reads_the_database_settings_names_a_budgeted_process() -> None:
    roles = unit_roles()
    reading = [p.name for p in UNITS.glob("*.service") if APP_ENV_FILE in p.read_text(encoding="utf-8")]
    assert reading
    for unit in reading:
        assert roles.get(unit) in BUDGETS, f"{unit} reads the database settings but names no budgeted process"


def test_the_box_at_its_busiest_stays_inside_the_pooler_with_headroom() -> None:
    instances = box_instances()
    assert instances == {API: 2, CONTRIBUTIONS: 1, WORKER: 1, FETCHER: 1, SCRIPT: 1}
    assert peak_sessions(instances) == 2 * (10 + 2) + (8 + 1) + (2 + 1) + (3 + 1)
    assert peak_sessions(instances) + POOLER_HEADROOM <= POOLER_SESSIONS


def test_a_process_added_at_any_budget_breaks_the_sum() -> None:
    smallest = min(budget.most for budget in BUDGETS.values())
    assert peak_sessions(box_instances()) + smallest + POOLER_HEADROOM > POOLER_SESSIONS


def test_the_contribution_unit_runs_no_more_gates_than_its_connections_carry() -> None:
    unit = (UNITS / "kv-contributions.service").read_text(encoding="utf-8")
    found = re.search(r"^Environment=CONTRIBUTION_WORKERS=(\d+)$", unit, re.MULTILINE)
    assert found is not None
    assert int(found.group(1)) * RUN_CONNECTIONS <= BUDGETS[CONTRIBUTIONS].main.most
    assert most_runs(BUDGETS[CONTRIBUTIONS].main) == 4


@pytest.mark.parametrize(("asked", "allowed", "runs"), [(4, 2, 2), (2, 2, 2), (1, 2, 1), (0, 2, 1)])
def test_a_concurrency_above_the_budget_runs_what_the_budget_carries(
    asked: int, allowed: int, runs: int
) -> None:
    assert runs_at_once(asked, allowed) == runs


def test_a_process_on_the_box_that_names_no_role_is_a_script() -> None:
    assert process_role(None, production=True) == SCRIPT
    assert process_role("  ", production=True) == SCRIPT
    assert process_role("api", production=True) == API


def test_a_process_off_the_box_that_names_no_role_keeps_its_own_settings() -> None:
    assert process_role(None, production=False) is None
    settings = get_settings().model_copy(
        update={"process_name": None, "app_env": "test", "database_pool_size": 7, "database_max_overflow": 3}
    )
    pools = process_pools(settings)
    assert (pools.main, pools.counting) == (PoolBudget(kept=7, burst=3), UNNAMED_COUNTING)


def test_a_named_process_takes_its_budget_whatever_the_settings_say() -> None:
    settings = get_settings().model_copy(
        update={"process_name": "worker", "app_env": "production", "database_pool_size": 12}
    )
    assert process_pools(settings) == BUDGETS[WORKER]


@pytest.mark.parametrize("named", ["fetcher", "nightly", "API"])
def test_a_role_without_a_budget_is_refused(named: str) -> None:
    with pytest.raises(ValueError, match="budget"):
        process_role(named, production=True)


def test_a_pool_keeps_at_least_one_connection() -> None:
    with pytest.raises(ValueError, match="at least one"):
        PoolBudget(kept=0, burst=4)
