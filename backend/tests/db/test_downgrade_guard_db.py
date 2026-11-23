import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.core.downgrade_guard import CONFIRM_STEPS_VARIABLE

pytestmark = pytest.mark.db

BACKEND = Path(__file__).resolve().parents[2]
ALEMBIC_SECONDS = 300


def alembic(*args: str, app_env: str) -> subprocess.CompletedProcess[str]:
    env = {key: value for key, value in os.environ.items() if key != CONFIRM_STEPS_VARIABLE}
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND,
        env={**env, "APP_ENV": app_env},
        capture_output=True,
        text=True,
        timeout=ALEMBIC_SECONDS,
        check=False,
    )


def current() -> str:
    found = alembic("current", app_env="test")
    assert found.returncode == 0, found.stderr[-4000:]
    return found.stdout.strip()


def test_a_two_step_downgrade_in_production_is_refused_before_any_step_runs() -> None:
    before = current()
    try:
        refused = alembic("downgrade", "-2", app_env="production")
        assert refused.returncode != 0
        assert "would undo 2 revisions" in " ".join((refused.stdout + refused.stderr).split())
        assert current() == before
    finally:
        alembic("upgrade", "head", app_env="test")
