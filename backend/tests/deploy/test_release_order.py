import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

from .fake_box import REPO
from .git_history import GIT_ENV, History, committed, git, made_history

pytestmark = pytest.mark.skipif(
    sys.platform == "win32", reason="the release order runs under Linux bash on the runner"
)

ORDER = REPO / ".github" / "scripts" / "release_order.sh"
WORKFLOWS = REPO / ".github" / "workflows"
NOT_HELD = "d" * 40
ROLLBACK = "sudo kv-blue-green rollback <release>"


@dataclass(frozen=True)
class Said:
    code: int
    out: str
    err: str


@pytest.fixture
def history(tmp_path: Path) -> History:
    return made_history(tmp_path)


def order(history: History, live: str, *arguments: str) -> Said:
    env = {
        **os.environ,
        **GIT_ENV,
        "PATH": f"{history.root / 'bin'}{os.pathsep}{os.environ['PATH']}",
        "API_BASE_URL": "https://api.example.org",
        "LIVE_RELEASE": live,
    }
    done = subprocess.run(
        ["bash", str(ORDER), *arguments],
        cwd=history.checkout,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    return Said(done.returncode, done.stdout, done.stderr)


def beside(history: History) -> str:
    git(history.work, "checkout", "-q", "-b", "beside", history.first)
    side = committed(history.work, {"backend/app/kilns.py": "KILNS = ('updraft',)\n"})
    git(history.work, "push", "-q", history.origin, "beside")
    git(history.checkout, "fetch", "-q", "origin", "beside")
    return side


def test_a_deploy_goes_on_for_the_release_production_serves_or_a_commit_after_it(history: History) -> None:
    assert order(history, history.first, "descends", history.web).code == 0
    assert order(history, history.api, "descends", history.web).code == 0
    again = order(history, history.api, "descends", history.api)
    assert again.code == 0, again.err
    assert "serves" in again.err


def test_a_deploy_of_a_commit_before_the_release_production_serves_is_refused(history: History) -> None:
    for older in (history.first, history.api):
        refused = order(history, history.web, "descends", older)
        assert refused.code == 1, older
        assert f"::error::{older} does not come after {history.web}" in refused.err
        assert ROLLBACK in refused.err


def test_a_deploy_of_a_commit_beside_the_release_production_serves_is_refused(history: History) -> None:
    side = beside(history)
    assert order(history, history.web, "descends", side).code == 1
    assert order(history, side, "descends", history.web).code == 1
    assert order(history, history.first, "descends", side).code == 0


def test_a_deploy_is_refused_when_production_serves_a_commit_the_repository_lacks(history: History) -> None:
    refused = order(history, NOT_HELD, "descends", history.web)
    assert refused.code == 1
    assert f"production serves {NOT_HELD}, which this repository does not hold" in refused.err


def test_a_deploy_goes_on_with_a_warning_when_the_api_names_no_release(history: History) -> None:
    for live in ("dev", "unreachable", ""):
        said = order(history, live, "descends", history.first)
        assert said.code == 0, live
        assert "::warning::" in said.err, live


def test_the_releases_before_are_the_one_production_serves_and_the_base(history: History) -> None:
    assert order(history, history.first, "before", "main").out.split() == [history.first, history.web]
    assert order(history, history.first, "before", history.api).out.split() == [history.first, history.api]


def test_a_base_production_already_serves_is_read_once(history: History) -> None:
    assert order(history, history.web, "before", "main").out.split() == [history.web]
    assert order(history, history.api, "before", history.api).out.split() == [history.api]


def test_only_the_base_is_read_when_the_api_names_no_release(history: History) -> None:
    for live in ("dev", "unreachable"):
        said = order(history, live, "before", "main")
        assert said.code == 0, said.err
        assert said.out.split() == [history.web], live
        assert "::warning::" in said.err, live


def test_a_base_origin_lacks_stops_the_check(history: History) -> None:
    said = order(history, history.first, "before", "round99")
    assert said.code == 1
    assert "origin has no branch 'round99'" in said.err


def workflow_steps(name: str) -> list[str]:
    text = (WORKFLOWS / name).read_text(encoding="utf-8")
    return re.findall(r"^      - name: (.+)$", text, re.MULTILINE)


def test_deploy_backend_refuses_an_older_commit_before_it_changes_anything() -> None:
    text = (WORKFLOWS / "deploy-backend.yml").read_text(encoding="utf-8")
    checkout = text.split("      - name: Check out the commit to deploy\n", 1)[1].split("\n\n", 1)[0]
    assert "          fetch-depth: 0" in checkout.splitlines()
    names = workflow_steps("deploy-backend.yml")
    guard = names.index("Refuse a commit older than the release production serves")
    assert names.index("Name the release") < guard < names.index("Assume the deploy role")
    assert '        run: bash .github/scripts/release_order.sh descends "$SHA"\n' in text


def test_backend_checks_reads_the_migrated_database_under_every_release_before() -> None:
    text = (WORKFLOWS / "backend-checks.yml").read_text(encoding="utf-8")
    step = text.split("      - name: The releases before read and write the migrated database\n", 1)[1]
    assert "          API_BASE_URL: ${{ vars.API_BASE_URL }}\n" in step
    assert 'releases="$(bash ../.github/scripts/release_order.sh before "$BASE_REF")"' in step
    assert 'PREVIOUS_RELEASE_BACKEND="$RUNNER_TEMP/release-$release/backend"' in step


def test_the_web_build_reads_the_release_production_serves_through_the_release_order() -> None:
    gate = (REPO / ".github" / "actions" / "build-web-app" / "api_ready.sh").read_text(encoding="utf-8")
    assert 'live="$(bash "$ORDER" live)"' in gate
    assert "/health" not in gate
