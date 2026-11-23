import re

import pytest

from .golden import REPO

WORKFLOW = REPO / ".github" / "workflows" / "backend-checks.yml"
READ_OUTSIDE_THE_BACKEND = (
    "docs/PLAN.md",
    "docs/plans/answer-experience.md",
    "etl/geo/geo_etl/layers/chirps.py",
    "etl/geo/geo_etl/layers/ghcncams.py",
    "etl/geo/geo_etl/river_districts.py",
    "etl/geo/geo_etl/rivers.py",
    "etl/geo/geo_etl/rows.py",
    "etl/geo/geo_etl/topology.py",
    "etl/geo/geo_etl/trend.py",
    "etl/geo/load.py",
    "etl/geo/load_rivers.py",
    "infra/terraform/cloudfront.tf",
    "infra/terraform/user_data.sh",
)


def trigger_paths(event: str) -> list[str]:
    lines = WORKFLOW.read_text(encoding="utf-8").splitlines()
    start = lines.index(f"  {event}:")
    found: list[str] = []
    for line in lines[start + 1 :]:
        if line.startswith("  ") and not line.startswith("    "):
            break
        listed = re.fullmatch(r'\s+- "([^"]+)"', line)
        if listed:
            found.append(listed.group(1))
    return found


def matches(glob: str, path: str) -> bool:
    pattern = "".join(
        ".*" if part == "**" else "[^/]*" if part == "*" else re.escape(part)
        for part in re.split(r"(\*\*|\*)", glob)
    )
    return re.fullmatch(pattern, path) is not None


def test_the_glob_reading_follows_github_path_filters() -> None:
    assert matches("etl/geo/geo_etl/**", "etl/geo/geo_etl/layers/chirps.py")
    assert matches("etl/geo/load*.py", "etl/geo/load_rivers.py")
    assert not matches("etl/geo/load*.py", "etl/geo/tests/load.py")
    assert not matches("docs/PLAN.md", "docs/PLAN.md.bak")


@pytest.mark.parametrize("path", READ_OUTSIDE_THE_BACKEND)
def test_a_pull_request_changing_a_file_the_contract_tests_read_runs_them(path: str) -> None:
    assert (REPO / path).is_file()
    assert any(matches(glob, path) for glob in trigger_paths("pull_request"))


@pytest.mark.parametrize("path", READ_OUTSIDE_THE_BACKEND)
def test_a_push_changing_only_such_a_file_deploys_nothing(path: str) -> None:
    assert not any(matches(glob, path) for glob in trigger_paths("push"))
