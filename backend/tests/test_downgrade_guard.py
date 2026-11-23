from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import pytest
from alembic.runtime.migration import MigrationStep, RevisionStep
from alembic.script import ScriptDirectory
from alembic.util import CommandError

from app.core.config import Settings
from app.core.downgrade_guard import CONFIRM_STEPS_VARIABLE, planned_downgrade, refuse_long_downgrade

MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations"
SCRIPTS = ScriptDirectory(str(MIGRATIONS))
HEAD = "0092_readings_layers_categories"
RUNBOOK_TARGET = "0028_roles_and_contributions"
REVISIONS_SINCE_0028 = 50
TWO = ("0092_readings_layers_categories", "0090_answer_leftovers")


class Migration:
    def __init__(self, heads: tuple[str, ...], plan: Callable[..., Sequence[object]], **opts: Any) -> None:
        self.opts: dict[str, Any] = {"fn": plan, **opts}
        self._heads = heads

    def get_current_heads(self) -> tuple[str, ...]:
        return self._heads


def downgrade_to(destination: str) -> Callable[..., list[RevisionStep]]:
    def plan(heads: tuple[str, ...], context: object) -> list[RevisionStep]:
        found = SCRIPTS.iterate_revisions(heads, destination, select_for_downgrade=True)
        return [MigrationStep.downgrade_from_script(SCRIPTS.revision_map, script) for script in found]

    return plan


def upgrade_to(destination: str) -> Callable[..., list[RevisionStep]]:
    def plan(heads: tuple[str, ...], context: object) -> list[RevisionStep]:
        found = reversed(list(SCRIPTS.iterate_revisions(destination, heads)))
        return [MigrationStep.upgrade_from_script(SCRIPTS.revision_map, script) for script in found]

    return plan


def downgrading(destination: str) -> Migration:
    return Migration((HEAD,), downgrade_to(destination), destination_rev=destination)


def test_the_runbook_s_old_undo_would_have_undone_fifty_revisions_from_today_s_head() -> None:
    undone = planned_downgrade(downgrading(RUNBOOK_TARGET))
    assert len(undone) == REVISIONS_SINCE_0028
    assert (undone[0], undone[-1]) == (HEAD, "0029_unlimited_ai_use")


def test_one_step_back_undoes_the_head_alone() -> None:
    assert planned_downgrade(downgrading("-1")) == (HEAD,)
    assert planned_downgrade(downgrading("-2")) == TWO


def test_an_upgrade_and_a_command_without_a_destination_undo_nothing() -> None:
    upgrade = Migration(("0090_answer_leftovers",), upgrade_to(HEAD), destination_rev=HEAD)
    assert planned_downgrade(upgrade) == ()

    def never(heads: tuple[str, ...], context: object) -> list[RevisionStep]:
        raise AssertionError("a command without a destination is never planned twice")

    assert planned_downgrade(Migration((HEAD,), never)) == ()


def test_one_step_is_allowed_in_production() -> None:
    refuse_long_downgrade((HEAD,), production=True, confirmed_steps=None)


def test_two_steps_are_refused_in_production_and_the_refusal_names_how_many() -> None:
    with pytest.raises(CommandError) as refused:
        refuse_long_downgrade(TWO, production=True, confirmed_steps=None)
    assert "would undo 2 revisions" in str(refused.value)
    assert f"{CONFIRM_STEPS_VARIABLE}=2" in str(refused.value)


def test_two_steps_are_allowed_in_production_only_when_exactly_two_are_confirmed() -> None:
    refuse_long_downgrade(TWO, production=True, confirmed_steps=2)
    for confirmed in (1, 3):
        with pytest.raises(CommandError):
            refuse_long_downgrade(TWO, production=True, confirmed_steps=confirmed)


def test_any_downgrade_goes_outside_production() -> None:
    undone = planned_downgrade(downgrading("base"))
    refuse_long_downgrade(undone, production=False, confirmed_steps=None)
    assert len(undone) > REVISIONS_SINCE_0028


def test_the_confirmation_is_read_from_its_environment_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(CONFIRM_STEPS_VARIABLE, "50")
    monkeypatch.setenv("APP_ENV", "production")
    settings = Settings(_env_file=None)
    assert (settings.is_production, settings.confirm_downgrade_steps) == (True, 50)
