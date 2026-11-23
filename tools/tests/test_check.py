from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path, PurePosixPath

import pytest
from conftest import RepoBuilder, function_source, write_tree

from hygiene.baseline import BASELINE_SCHEMA_VERSION, BaselineError
from hygiene.check import BASELINE_FILE, project_files, render, run_check

SCRIPT = Path(__file__).resolve().parents[1] / "hygiene_check.py"

TWO_ENTRIES = "# Register\n\n## Area\n\n### First entry\n\n### Second entry\n"

CLEAN_TREE = {
    ".gitignore": "ignored/\n",
    "backend/app/__init__.py": "",
    "backend/app/core/db.py": "from app.models import User\n",
    "backend/app/services/audit.py": "from app.core.db import User\n",
    "backend/app/api/routes/auth.py": "from app.services import audit\n",
    "docs/TECH_DEBT.md": TWO_ENTRIES,
    "etl/long.py": function_source("long", 41),
    "frontend/app/page.tsx": "export default function Page() {\n  return null;\n}\n",
    "frontend/public/mark.png": b"\x00\x01\r\n",
    "ignored/bad.txt": b"\xef\xbb\xbfignored\r\n",
}

ONE_LONG = {"oversizedFiles": 0, "longFunctions": 1, "wideFunctions": 0, "registerEntries": 2}


def baseline(root: Path, counts: dict[str, int]) -> None:
    payload = {"schemaVersion": BASELINE_SCHEMA_VERSION, "counts": counts}
    write_tree(root, {str(BASELINE_FILE): json.dumps(payload) + "\n"})


def run_script(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root), *arguments],
        capture_output=True,
        text=True,
        check=False,
    )


def test_project_files_lists_untracked_files_and_skips_ignored_ones(make_repo: RepoBuilder) -> None:
    root = make_repo(CLEAN_TREE)
    files = project_files(root)
    assert PurePosixPath("etl/long.py") in files
    assert PurePosixPath("ignored/bad.txt") not in files


def test_clean_tree_at_its_baseline_passes(make_repo: RepoBuilder) -> None:
    root = make_repo(CLEAN_TREE)
    baseline(root, ONE_LONG)
    report = run_check(root, project_files(root))
    assert report.passed
    assert render(report)[-1] == "hygiene check passed"


def test_a_new_long_function_fails_and_names_every_offender(make_repo: RepoBuilder) -> None:
    root = make_repo({**CLEAN_TREE, "etl/other.py": function_source("other", 45)})
    baseline(root, ONE_LONG)
    report = run_check(root, project_files(root))
    assert not report.passed
    lines = render(report)
    assert "longFunctions: 2, above the baseline of 1" in lines
    assert "  etl/long.py:1: long is 41 (budget 40)" in lines
    assert "  etl/other.py:1: other is 45 (budget 40)" in lines


def test_a_lower_count_fails_until_the_baseline_is_updated(make_repo: RepoBuilder) -> None:
    root = make_repo(CLEAN_TREE)
    baseline(root, {**ONE_LONG, "longFunctions": 2})
    assert not run_check(root, project_files(root)).passed
    run_check(root, project_files(root), update_baseline=True)
    assert json.loads((root / BASELINE_FILE).read_text(encoding="utf-8"))["counts"] == ONE_LONG
    assert run_check(root, project_files(root)).passed


def test_update_refuses_to_raise_the_baseline(make_repo: RepoBuilder) -> None:
    root = make_repo(CLEAN_TREE)
    baseline(root, {**ONE_LONG, "longFunctions": 0})
    with pytest.raises(BaselineError, match="longFunctions 0 -> 1"):
        run_check(root, project_files(root), update_baseline=True)


def test_import_and_encoding_violations_fail_regardless_of_baseline(make_repo: RepoBuilder) -> None:
    root = make_repo(
        {
            **CLEAN_TREE,
            "backend/app/core/deps.py": "from app.api.routes import auth\n",
            "docs/notes.md": b"line\r\n",
            "etl/explained.py": "x = 1  # because\n",
        }
    )
    baseline(root, ONE_LONG)
    lines = render(run_check(root, project_files(root)))
    assert (
        "import direction: backend/app/core/deps.py:1: core imports app.api.routes (core may not import api)"
        in lines
    )
    assert "text encoding: docs/notes.md: has a carriage return; line endings must be LF" in lines
    assert "code comment: etl/explained.py:1: # because" in lines
    assert lines[-1] == "hygiene check FAILED"


def test_script_exit_codes_follow_the_report(make_repo: RepoBuilder) -> None:
    root = make_repo(CLEAN_TREE)
    missing = run_script(root)
    assert missing.returncode == 1
    assert "--update-baseline" in missing.stderr
    created = run_script(root, "--update-baseline")
    assert created.returncode == 0, created.stdout + created.stderr
    assert run_script(root).returncode == 0
    write_tree(root, {"etl/more.py": function_source("more", 50)})
    raised = run_script(root)
    assert raised.returncode == 1
    assert "longFunctions: 2, above the baseline of 1" in raised.stdout


def test_a_new_register_entry_fails_and_says_why(make_repo: RepoBuilder) -> None:
    root = make_repo({**CLEAN_TREE, "docs/TECH_DEBT.md": TWO_ENTRIES + "\n### Third entry\n"})
    baseline(root, ONE_LONG)
    report = run_check(root, project_files(root))
    assert not report.passed
    lines = render(report)
    assert "registerEntries: 3, above the baseline of 2" in lines
    assert (
        "  docs/TECH_DEBT.md gained entries; its count may only fall, so clear as many in the same change"
        in lines
    )


def test_a_cleared_register_entry_passes_and_the_update_lowers_the_baseline(make_repo: RepoBuilder) -> None:
    root = make_repo({**CLEAN_TREE, "docs/TECH_DEBT.md": "# Register\n\n### First entry\n"})
    baseline(root, ONE_LONG)
    report = run_check(root, project_files(root))
    assert report.passed
    assert "registerEntries: 1, below the baseline of 2; --update-baseline lowers it" in render(report)
    run_check(root, project_files(root), update_baseline=True)
    counts = json.loads((root / BASELINE_FILE).read_text(encoding="utf-8"))["counts"]
    assert counts == {**ONE_LONG, "registerEntries": 1}


def test_update_refuses_to_raise_the_register_count(make_repo: RepoBuilder) -> None:
    root = make_repo(CLEAN_TREE)
    baseline(root, {**ONE_LONG, "registerEntries": 1})
    with pytest.raises(BaselineError, match="registerEntries 1 -> 2"):
        run_check(root, project_files(root), update_baseline=True)


def test_a_tree_without_the_register_fails_loudly(make_repo: RepoBuilder) -> None:
    root = make_repo({path: content for path, content in CLEAN_TREE.items() if path != "docs/TECH_DEBT.md"})
    baseline(root, ONE_LONG)
    missing = run_script(root)
    assert missing.returncode == 1
    assert "no debt register at docs/TECH_DEBT.md" in missing.stderr
