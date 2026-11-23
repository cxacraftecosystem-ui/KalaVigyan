from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any, Protocol

from alembic.runtime.migration import RevisionStep
from alembic.util import CommandError

__all__ = [
    "CONFIRM_STEPS_VARIABLE",
    "PRODUCTION_STEPS",
    "PlannedMigration",
    "planned_downgrade",
    "refuse_long_downgrade",
]

CONFIRM_STEPS_VARIABLE = "CONFIRM_DOWNGRADE_STEPS"
PRODUCTION_STEPS = 1
DESTINATION_OPTION = "destination_rev"
PLAN_OPTION = "fn"


class PlannedMigration(Protocol):
    opts: dict[str, Any]

    def get_current_heads(self) -> tuple[str, ...]: ...


def planned_downgrade(migration: PlannedMigration) -> tuple[str, ...]:
    plan = migration.opts.get(PLAN_OPTION)
    if plan is None or DESTINATION_OPTION not in migration.opts:
        return ()
    return _undone(plan(migration.get_current_heads(), migration))


def _undone(steps: Iterable[object]) -> tuple[str, ...]:
    return tuple(
        step.revision.revision for step in steps if isinstance(step, RevisionStep) and step.is_downgrade
    )


def refuse_long_downgrade(undone: Sequence[str], *, production: bool, confirmed_steps: int | None) -> None:
    count = len(undone)
    if not production or count <= PRODUCTION_STEPS or confirmed_steps == count:
        return
    raise CommandError(
        f"This downgrade would undo {count} revisions, from {undone[0]} back to {undone[-1]}, and each "
        "one commits on its own, so the tables they added are dropped with their rows. In production a "
        f"downgrade undoes at most {PRODUCTION_STEPS} revision: run `alembic downgrade -1` from the "
        f"release that added it. To undo all {count} on purpose, run it again with "
        f"{CONFIRM_STEPS_VARIABLE}={count}."
    )
