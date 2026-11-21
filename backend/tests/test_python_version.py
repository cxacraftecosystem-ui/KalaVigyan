import re
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PIN = REPO / "infra" / "deploy" / "python.pin"
RELEASE = REPO / "infra" / "deploy" / "release.sh"
BOX = REPO / "infra" / "terraform" / "user_data.sh"
WORKFLOWS = REPO / ".github" / "workflows"
DECIDED = "3.15"
PIN_KEYS = ("PY_VERSION", "PY_BUILD", "PY_URL", "PY_SHA256")
PROJECTS = ("backend", "etl/crafts")
CODE_WORKFLOWS = ("backend-checks.yml", "hygiene.yml", "open-data.yml", "web-fonts.yml", "craft-data.yml")
ENV_REFERENCE = "${{ env.PYTHON_VERSION }}"
INSTALL_STEPS = (
    '/opt/cpython/${PY_VERSION}+${PY_BUILD}"',
    "mktemp -d /opt/cpython/.incoming.XXXXXX",
    "--proto '=https' --tlsv1.2",
    "sha256sum -c -",
    "--no-same-owner",
    "-I -m compileall -q",
    "chown -R root:root",
    "chmod -R go-w",
    "mv -T",
    "import sys, platform, ssl, sqlite3, venv; assert platform.python_version() == sys.argv[1]",
)
CHECKED_THEN_MOVED = ("sha256sum -c -", 'tar -xzf "$stage/python.tar.gz"', 'mv -T "$stage/python" "$PY_HOME"')


def pinned() -> dict[str, str]:
    rows = (line.partition("=") for line in PIN.read_text(encoding="utf-8").splitlines())
    return {key: value for key, _, value in rows}


def box_pin() -> dict[str, str]:
    return dict(re.findall(r'^(PY_[A-Z0-9]+)="([^"]*)"$', BOX.read_text(encoding="utf-8"), re.MULTILINE))


def minor_of(version: str) -> str:
    return ".".join(version.split(".")[:2])


def workflow_pythons(name: str) -> set[str]:
    text = (WORKFLOWS / name).read_text(encoding="utf-8")
    named = re.findall(r"^\s*(?:PYTHON_VERSION|python-version):\s*(.+?)\s*$", text, re.MULTILINE)
    return {value.strip('"') for value in named if value != ENV_REFERENCE}


def project(folder: str) -> dict:
    return tomllib.loads((REPO / folder / "pyproject.toml").read_text(encoding="utf-8"))


def test_the_release_pins_one_standalone_cpython_of_the_decided_minor_over_https() -> None:
    pin = pinned()
    assert tuple(pin) == PIN_KEYS
    version, build = pin["PY_VERSION"], pin["PY_BUILD"]
    assert minor_of(version) == DECIDED
    assert pin["PY_URL"] == (
        f"https://github.com/astral-sh/python-build-standalone/releases/download/{build}/"
        f"cpython-{version}%2B{build}-x86_64-unknown-linux-gnu-install_only.tar.gz"
    )
    assert re.fullmatch(r"[0-9a-f]{64}", pin["PY_SHA256"])


def test_a_rebuilt_box_installs_the_build_the_release_pins() -> None:
    assert box_pin() == pinned()


def test_ci_runs_the_backend_the_tools_and_the_craft_etl_on_the_decided_minor() -> None:
    for name in CODE_WORKFLOWS:
        assert workflow_pythons(name) == {DECIDED}, name


def test_the_projects_and_the_lock_require_the_decided_minor() -> None:
    for folder in PROJECTS:
        settings = project(folder)
        assert settings["project"]["requires-python"] == f">={DECIDED}", folder
        assert settings["tool"]["ruff"]["target-version"] == "py" + DECIDED.replace(".", ""), folder
    tools = project("tools")
    assert "project" not in tools
    assert tools["tool"]["ruff"]["extend"] == "../backend/pyproject.toml"
    lock = tomllib.loads((REPO / "backend" / "uv.lock").read_text(encoding="utf-8"))
    assert lock["requires-python"] == f">={DECIDED}"


def test_the_geo_etl_runs_on_the_python_its_own_project_requires() -> None:
    required = project("etl/geo")["project"]["requires-python"]
    assert {required.removeprefix(">=")} == workflow_pythons("geo-etl.yml")


def test_a_release_installs_its_interpreter_as_the_box_does_and_keeps_every_older_one() -> None:
    release = RELEASE.read_text(encoding="utf-8")
    box = BOX.read_text(encoding="utf-8")
    for step in INSTALL_STEPS:
        assert step in release, step
        assert step in box, step
    order = [release.index(step) for step in CHECKED_THEN_MOVED]
    assert order == sorted(order)
    assert not re.search(r"rm -rf \"?(/opt/cpython|\$PY_HOME)", release)
    assert "KV_PYTHON" not in release


def test_a_release_builds_its_venv_with_the_pinned_interpreter_after_installing_it() -> None:
    release = RELEASE.read_text(encoding="utf-8")
    build = re.search(r"^build_release\(\) \{\n(.*?)^\}$", release, re.MULTILINE | re.DOTALL)
    assert build is not None
    body = build.group(1)
    assert body.index("install_python\n") < body.index('--python "$PYTHON"')
    assert 'PIN="$HERE/python.pin"' in release
    assert 'PYTHON="$PY_HOME/bin/python${PY_MINOR}"' in release
