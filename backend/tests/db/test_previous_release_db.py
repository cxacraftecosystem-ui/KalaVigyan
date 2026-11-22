import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.db

PROBE = Path(__file__).with_name("previous_release_probe.py")
THIS_RELEASE = Path(__file__).resolve().parents[2]
PREVIOUS_RELEASE = os.environ.get("PREVIOUS_RELEASE_BACKEND")
PROBE_SECONDS = 600


def probed(backend: Path | str) -> dict[str, Any]:
    env = {**os.environ, "PYTHONPATH": str(backend)}
    done = subprocess.run(
        [sys.executable, str(PROBE)],
        env=env,
        capture_output=True,
        text=True,
        timeout=PROBE_SECONDS,
        check=False,
    )
    assert done.returncode == 0, done.stderr[-4000:]
    report: dict[str, Any] = json.loads(done.stdout.splitlines()[-1])
    return report


def problems(report: dict[str, Any]) -> dict[str, list[str]]:
    return {name: report[name] for name in ("unreadable", "refusedLabels", "unwritable") if report[name]}


def test_this_release_reads_and_writes_every_table_of_the_migrated_database() -> None:
    report = probed(THIS_RELEASE)
    assert report["tables"] > 0
    assert problems(report) == {}


@pytest.mark.skipif(
    PREVIOUS_RELEASE is None, reason="Backend checks names the release before in PREVIOUS_RELEASE_BACKEND"
)
def test_the_release_before_reads_and_writes_every_table_of_the_migrated_database() -> None:
    assert PREVIOUS_RELEASE is not None
    report = probed(PREVIOUS_RELEASE)
    assert report["tables"] > 0
    assert problems(report) == {}
