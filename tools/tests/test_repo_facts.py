from __future__ import annotations

from collections import Counter
from pathlib import Path

from conftest import RepoBuilder

from hygiene.check import project_files
from repo_facts.counts import Facts, Repo, gather
from repo_facts_build import facts_text, main

MODELS = """
class Craft(Base):
    __tablename__ = "Craft"


class Claim(Base):
    __tablename__ = "Claim"
    name = "not a table"
"""
ROUTES = """
@router.get("/crafts")
async def crafts():
    return []


@router.post("/crafts")
@limited
async def add_craft():
    return None


@router.get("/crafts/{slug}")
def craft(slug):
    return slug


@other.get("/elsewhere")
def elsewhere():
    return None
"""
MAIN = """
@app.get("/health")
def health():
    return {}
"""
MCP_TOOLS = """
READ = (Tool("find_crafts", "Find"), Tool(name="get_facts"))
"""
UNIT_TESTS = """
def test_one():
    assert True


async def test_two():
    assert True


def helper():
    return None
"""
DB_TESTS = """
async def test_on_postgres():
    assert True
"""
UNIT_SPEC = """test.describe("group", () => {
  test("first", () => {});
  test.skip("second", () => {});
});
test("third", () => {});
"""
SMOKE_SPEC = 'test("smoke", async () => {});\n'

TREE = {
    "backend/app/models/craft.py": MODELS,
    "backend/app/models/__init__.py": "",
    "backend/migrations/versions/0002_more.py": "revision = '0002'\n",
    "backend/migrations/versions/0001_initial.py": "revision = '0001'\n",
    "backend/migrations/versions/README": "not a migration\n",
    "backend/app/api/routes/crafts.py": ROUTES,
    "backend/app/api/routes/empty.py": "VALUE = 1\n",
    "backend/app/main.py": MAIN,
    "backend/app/api/mcp_read_tools.py": MCP_TOOLS,
    "backend/app/api/routes/mcp_like.py": 'TOOL = Tool("hidden")\n',
    "backend/tests/test_units.py": UNIT_TESTS,
    "backend/tests/helpers.py": "def test_not_in_a_test_file():\n    return None\n",
    "backend/tests/db/test_db.py": DB_TESTS,
    "tools/tests/test_tools.py": "def test_tool():\n    assert True\n",
    "frontend/e2e/answer-unit.spec.ts": UNIT_SPEC,
    "frontend/e2e/smoke.spec.ts": SMOKE_SPEC,
    "frontend/lib/shape.ts": "export const a = 1;\nexport const b = 2;\n",
    "docs/decisions/0001-first.md": "# 0001\n",
    "docs/decisions/0002-second.md": "# 0002\n",
    "docs/decisions/README.md": "# Decisions\n",
    "docs/contracts/geo.md": "# Geo\n",
    "docs/contracts/README.md": "# Contracts\n",
    ".github/workflows/hygiene.yml": "name: Hygiene\n",
    ".github/workflows/readme-check.yml": "name: README check\n",
    "backend/app/data/curation/Kutch-Ajrakh.json": "{}\n",
    "backend/app/data/curation/Kutch-Ajrakh.check.json": "{}\n",
    "backend/app/data/curation/index.json": "{}\n",
    "backend/app/data/curation/categories/Textiles.json": "{}\n",
    "backend/app/data/curation/categories/Textiles.check.json": "{}\n",
}


def _facts(make_repo: RepoBuilder) -> tuple[Path, Facts]:
    root = make_repo(TREE)
    return root, gather(Repo(root, tuple(project_files(root))))


def test_tables_are_the_models_tablenames_and_migrations_the_numbered_files(make_repo: RepoBuilder) -> None:
    _, facts = _facts(make_repo)
    assert facts.tables == ("Claim", "Craft")
    assert facts.migrations == ("0001_initial", "0002_more")


def test_operations_are_router_and_app_decorators_by_method(make_repo: RepoBuilder) -> None:
    _, facts = _facts(make_repo)
    assert facts.operations == {
        "crafts.py": Counter({"GET": 2, "POST": 1}),
        "main.py": Counter({"GET": 1}),
    }


def test_mcp_tools_are_tool_calls_beside_the_mcp_modules_only(make_repo: RepoBuilder) -> None:
    _, facts = _facts(make_repo)
    assert facts.mcp_tools == Counter({"mcp_read_tools.py": 2})


def test_tests_are_counted_per_suite(make_repo: RepoBuilder) -> None:
    _, facts = _facts(make_repo)
    assert facts.python_tests == (
        ("Backend, without a database", 1, 2),
        ("Backend, on Postgres", 1, 1),
        ("Tools", 1, 1),
        ("Craft data ETL", 0, 0),
        ("Geo ETL", 0, 0),
    )
    assert facts.frontend_tests == (
        ("Unit specs (`*-unit.spec.ts`)", 1, 3),
        ("Browser and release specs", 1, 1),
    )


def test_records_count_decisions_contracts_workflows_and_dossiers(make_repo: RepoBuilder) -> None:
    _, facts = _facts(make_repo)
    assert dict(facts.records) == {
        "Decision records (`docs/decisions/`)": 2,
        "Contracts (`docs/contracts/`)": 1,
        "Workflows (`.github/workflows/`)": 2,
        "Curated craft dossiers": 1,
        "Curated category dossiers": 1,
    }


def test_volume_counts_code_files_and_their_newlines(make_repo: RepoBuilder) -> None:
    _, facts = _facts(make_repo)
    volume = {area: (files, lines) for area, files, lines in facts.volume}
    assert volume["frontend/lib"] == (1, 2)
    assert volume["backend/migrations"] == (2, 2)
    assert volume["infra"] == (0, 0)


def test_the_page_states_each_count_once_in_the_house_form(make_repo: RepoBuilder) -> None:
    root = make_repo(TREE)
    text = facts_text(root)
    assert text.startswith("# Repository facts\n\n")
    assert "| Tables (`__tablename__` in `backend/app/models/`) | 2 |" in text
    assert "Newest migration: `0002_more`." in text
    assert (
        "**4 operations** in `backend/app/api/routes/` and `backend/app/main.py`: 3 GET, 1 POST, 0 PUT"
        in text
    )
    assert "| `crafts.py` | 3 |\n| `main.py` | 1 |" in text
    assert "**2 tools**" in text
    assert text.rstrip().endswith("a count is only as true as the pattern that finds it.")
    assert "## How this document is kept true" in text


def test_check_passes_on_a_fresh_file_and_fails_once_the_code_moves(make_repo: RepoBuilder) -> None:
    root = make_repo(TREE)
    assert main(["--root", str(root)]) == 0
    assert main(["--root", str(root), "--check"]) == 0
    routes = Path(root, "backend/app/api/routes/crafts.py")
    routes.write_text(routes.read_text(encoding="utf-8") + MAIN.replace("@app", "@router"), encoding="utf-8")
    assert main(["--root", str(root), "--check"]) == 1
