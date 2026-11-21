from __future__ import annotations

import ast
import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

__all__ = ["HTTP_METHODS", "OUTPUT", "Facts", "Repo", "gather"]

OUTPUT = PurePosixPath("docs/REPO_FACTS.md")
MODELS = PurePosixPath("backend/app/models")
ROUTES = PurePosixPath("backend/app/api/routes")
MCP_HOME = PurePosixPath("backend/app/api")
APP_MAIN = PurePosixPath("backend/app/main.py")
MIGRATIONS = PurePosixPath("backend/migrations/versions")
CURATION = PurePosixPath("backend/app/data/curation")
CATEGORY_DOSSIERS = CURATION / "categories"
DECISIONS = PurePosixPath("docs/decisions")
CONTRACTS = PurePosixPath("docs/contracts")
WORKFLOWS = PurePosixPath(".github/workflows")
FRONTEND_SPECS = PurePosixPath("frontend/e2e")
HTTP_METHODS = ("get", "post", "put", "patch", "delete")
MIGRATION_FILE = re.compile(r"^\d{4}_\w+\.py$")
DECISION_FILE = re.compile(r"^\d{4}-[\w-]+\.md$")
FRONTEND_TEST = re.compile(r"^\s*test(?:\.(?:only|skip|fixme))?\(", re.MULTILINE)
UNIT_SPEC = "-unit.spec.ts"
PYTHON_SUITES = (
    ("Backend, without a database", PurePosixPath("backend/tests"), PurePosixPath("backend/tests/db")),
    ("Backend, on Postgres", PurePosixPath("backend/tests/db"), None),
    ("Tools", PurePosixPath("tools/tests"), None),
    ("Craft data ETL", PurePosixPath("etl/crafts/tests"), None),
    ("Geo ETL", PurePosixPath("etl/geo/tests"), None),
)
VOLUME_AREAS = (
    PurePosixPath("backend/app"),
    PurePosixPath("backend/tests"),
    PurePosixPath("backend/migrations"),
    PurePosixPath("frontend/app"),
    PurePosixPath("frontend/components"),
    PurePosixPath("frontend/lib"),
    PurePosixPath("frontend/e2e"),
    PurePosixPath("etl"),
    PurePosixPath("tools"),
    PurePosixPath("infra"),
)
CODE_SUFFIXES = frozenset({".py", ".ts", ".tsx", ".mjs", ".css", ".sh", ".tf", ".sql"})


@dataclass(frozen=True)
class Repo:
    root: Path
    files: tuple[PurePosixPath, ...]

    def under(self, folder: PurePosixPath, suffix: str = "") -> list[PurePosixPath]:
        return [path for path in self.files if path.is_relative_to(folder) and path.name.endswith(suffix)]

    def text(self, path: PurePosixPath) -> str:
        return (self.root / path).read_text(encoding="utf-8")

    def tree(self, path: PurePosixPath) -> ast.Module:
        return ast.parse(self.text(path), filename=str(path))


@dataclass(frozen=True)
class Facts:
    tables: tuple[str, ...]
    migrations: tuple[str, ...]
    operations: dict[str, Counter[str]]
    mcp_tools: Counter[str]
    python_tests: tuple[tuple[str, int, int], ...]
    frontend_tests: tuple[tuple[str, int, int], ...]
    records: tuple[tuple[str, int], ...]
    volume: tuple[tuple[str, int, int], ...]


def table_names(repo: Repo) -> tuple[str, ...]:
    names = []
    for path in repo.under(MODELS, ".py"):
        for node in ast.walk(repo.tree(path)):
            if _assigns_tablename(node):
                names.append(str(node.value.value))
    return tuple(sorted(names))


def _assigns_tablename(node: ast.AST) -> bool:
    if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Constant):
        return False
    return any(isinstance(target, ast.Name) and target.id == "__tablename__" for target in node.targets)


def migration_names(repo: Repo) -> tuple[str, ...]:
    found = [path.stem for path in repo.under(MIGRATIONS, ".py") if MIGRATION_FILE.match(path.name)]
    return tuple(sorted(found))


def route_method(decorator: ast.expr, owner: str) -> str | None:
    if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
        return None
    target = decorator.func
    if not isinstance(target.value, ast.Name) or target.value.id != owner:
        return None
    return target.attr.upper() if target.attr in HTTP_METHODS else None


def operations_in(repo: Repo, path: PurePosixPath, owner: str) -> Counter[str]:
    methods: Counter[str] = Counter()
    for node in ast.walk(repo.tree(path)):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            methods.update(m for m in (route_method(d, owner) for d in node.decorator_list) if m)
    return methods


def http_operations(repo: Repo) -> dict[str, Counter[str]]:
    found = {path.name: operations_in(repo, path, "router") for path in repo.under(ROUTES, ".py")}
    if APP_MAIN in repo.files:
        found[APP_MAIN.name] = operations_in(repo, APP_MAIN, "app")
    return {name: methods for name, methods in found.items() if methods}


def mcp_tool_count(repo: Repo) -> Counter[str]:
    tools: Counter[str] = Counter()
    for path in repo.under(MCP_HOME, ".py"):
        if path.parent != MCP_HOME:
            continue
        for node in ast.walk(repo.tree(path)):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "Tool":
                tools[path.name] += 1
    return tools


def python_test_count(repo: Repo, path: PurePosixPath) -> int:
    nodes = ast.walk(repo.tree(path))
    return sum(
        1
        for node in nodes
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.startswith("test_")
    )


def python_suites(repo: Repo) -> tuple[tuple[str, int, int], ...]:
    rows = []
    for label, folder, excluded in PYTHON_SUITES:
        files = [
            path
            for path in repo.under(folder, ".py")
            if path.name.startswith("test_") and not (excluded and path.is_relative_to(excluded))
        ]
        rows.append((label, len(files), sum(python_test_count(repo, path) for path in files)))
    return tuple(rows)


def frontend_suites(repo: Repo) -> tuple[tuple[str, int, int], ...]:
    specs = repo.under(FRONTEND_SPECS, ".spec.ts")
    unit = [path for path in specs if path.name.endswith(UNIT_SPEC)]
    other = [path for path in specs if not path.name.endswith(UNIT_SPEC)]
    return (
        ("Unit specs (`*-unit.spec.ts`)", len(unit), _frontend_tests(repo, unit)),
        ("Browser and release specs", len(other), _frontend_tests(repo, other)),
    )


def _frontend_tests(repo: Repo, specs: Iterable[PurePosixPath]) -> int:
    return sum(len(FRONTEND_TEST.findall(repo.text(path))) for path in specs)


def record_counts(repo: Repo) -> tuple[tuple[str, int], ...]:
    dossiers = [path for path in repo.under(CURATION, ".json") if _is_dossier(path, CURATION)]
    categories = [
        path for path in repo.under(CATEGORY_DOSSIERS, ".json") if _is_dossier(path, CATEGORY_DOSSIERS)
    ]
    return (
        ("Decision records (`docs/decisions/`)", _count(repo.under(DECISIONS, ".md"), DECISION_FILE)),
        (
            "Contracts (`docs/contracts/`)",
            len([p for p in repo.under(CONTRACTS, ".md") if p.name != "README.md"]),
        ),
        ("Workflows (`.github/workflows/`)", len(repo.under(WORKFLOWS, ".yml"))),
        ("Curated craft dossiers", len(dossiers)),
        ("Curated category dossiers", len(categories)),
    )


def _is_dossier(path: PurePosixPath, folder: PurePosixPath) -> bool:
    return path.parent == folder and not path.name.endswith(".check.json") and path.name != "index.json"


def _count(paths: Iterable[PurePosixPath], pattern: re.Pattern[str]) -> int:
    return sum(1 for path in paths if pattern.match(path.name))


def code_volume(repo: Repo) -> tuple[tuple[str, int, int], ...]:
    rows = []
    for area in VOLUME_AREAS:
        files = [path for path in repo.under(area) if path.suffix in CODE_SUFFIXES]
        lines = sum(repo.text(path).count("\n") for path in files)
        rows.append((str(area), len(files), lines))
    return tuple(rows)


def gather(repo: Repo) -> Facts:
    return Facts(
        tables=table_names(repo),
        migrations=migration_names(repo),
        operations=http_operations(repo),
        mcp_tools=mcp_tool_count(repo),
        python_tests=python_suites(repo),
        frontend_tests=frontend_suites(repo),
        records=record_counts(repo),
        volume=code_volume(repo),
    )
