import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from .fake_box import REPO
from .git_history import GIT_ENV, History, made_history

pytestmark = pytest.mark.skipif(
    sys.platform == "win32", reason="the gate runs under Linux bash on the runner"
)

GATE = REPO / ".github" / "actions" / "build-web-app" / "api_ready.sh"
ACTION = REPO / ".github" / "actions" / "build-web-app" / "action.yml"
AWAIT = REPO / ".github" / "actions" / "await-build" / "action.yml"
HAND_OFF = "Hand the web build to Deploy backend"
WORKFLOWS = REPO / ".github" / "workflows"


@pytest.fixture
def history(tmp_path: Path) -> History:
    return made_history(tmp_path)


def gate(history: History, live: str) -> tuple[str, str]:
    output = history.root / "github-output"
    output.write_text("", encoding="utf-8")
    env = {
        **os.environ,
        **GIT_ENV,
        "PATH": f"{history.root / 'bin'}{os.pathsep}{os.environ['PATH']}",
        "API_BASE_URL": "https://api.example.org",
        "GITHUB_OUTPUT": str(output),
        "LIVE_RELEASE": live,
    }
    done = subprocess.run(
        ["bash", str(GATE)],
        cwd=history.checkout,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert done.returncode == 0, done.stdout + done.stderr
    return output.read_text(encoding="utf-8").strip(), done.stdout


def test_a_web_only_push_builds_at_once_when_the_api_it_needs_answers(history: History) -> None:
    assert gate(history, history.api)[0] == "api=live"
    assert gate(history, history.web)[0] == "api=live"


def test_a_web_only_push_waits_while_an_earlier_api_push_has_not_shipped(history: History) -> None:
    decided, said = gate(history, history.first)
    assert decided == "api=waiting"
    assert f"main ({history.web}) changes the API since {history.first}" in said


def test_an_api_that_names_no_release_or_does_not_answer_holds_the_build(history: History) -> None:
    for live in ("dev", "unreachable"):
        decided, said = gate(history, live)
        assert decided == "api=waiting", live
        assert "::warning::" in said


def test_every_web_build_goes_through_the_gate_first() -> None:
    action = ACTION.read_text(encoding="utf-8")
    assert action.index('run: bash "$GITHUB_ACTION_PATH/api_ready.sh"') < action.index(
        "VERCEL_DEPLOY_HOOK_URL"
    )
    assert "      if: steps.ready.outputs.api == 'live'\n" in action
    calls = "uses: ./.github/actions/build-web-app\n        with:\n          api-base-url: ${{ vars.API_BASE_URL }}\n"
    for workflow in ("deploy-web.yml", "deploy-backend.yml"):
        text = (WORKFLOWS / workflow).read_text(encoding="utf-8")
        assert text.count(calls) == 1, workflow
        assert "VERCEL_DEPLOY_HOOK_URL" not in text, workflow


def built_by(steps: list[tuple[str, str | None]]) -> str:
    program = re.search(r"--jq '([^']+)'", AWAIT.read_text(encoding="utf-8"))
    assert program is not None
    jobs = {"jobs": [{"steps": [{"name": name, "conclusion": done} for name, done in steps]}]}
    done = subprocess.run(
        ["jq", "-r", program.group(1)], input=json.dumps(jobs), capture_output=True, text=True, check=True
    )
    return done.stdout.strip()


def test_a_deploy_that_leaves_the_build_to_deploy_backend_reads_as_no_build() -> None:
    build = "Build the web app once the API it needs is live"
    assert built_by([(build, "success"), (HAND_OFF, "success")]) == "none"
    assert built_by([(build, "success"), (HAND_OFF, "skipped")]) == "success"
    assert built_by([(build, "failure"), (HAND_OFF, "skipped")]) == "failure"
    assert built_by([("Assume the deploy role", "success")]) == "none"


def test_both_deploys_name_the_hand_off_when_the_gate_waits() -> None:
    assert "    value: ${{ steps.ready.outputs.api }}\n" in ACTION.read_text(encoding="utf-8")
    for workflow in ("deploy-web.yml", "deploy-backend.yml"):
        text = (WORKFLOWS / workflow).read_text(encoding="utf-8")
        assert "        id: build\n        uses: ./.github/actions/build-web-app\n" in text, workflow
        assert f"      - name: {HAND_OFF}\n        if: steps.build.outputs.api == 'waiting'\n" in text, (
            workflow
        )
