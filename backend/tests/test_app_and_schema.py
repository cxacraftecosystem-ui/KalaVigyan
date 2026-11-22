import ast
import io
import re
import tokenize
from pathlib import Path

import httpx
import pytest
import sqlalchemy as sa

from app.main import app
from app.models import Base

BACKEND = Path(__file__).resolve().parents[1]
MIGRATIONS = BACKEND / "migrations" / "versions"
MIGRATION = MIGRATIONS / "0001_initial_schema.py"
FUNCTIONAL_DIRECTIVE = re.compile(r"^#\s*(noqa|type:|pragma|pyright:|ruff:|fmt:|!)")


@pytest.fixture
async def client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        yield http


async def test_health(client: httpx.AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert len(response.headers["x-request-id"]) >= 8
    assert response.headers["x-content-type-options"] == "nosniff"


async def test_request_id_is_echoed(client: httpx.AsyncClient) -> None:
    response = await client.get("/health", headers={"X-Request-ID": "abcdef123456"})
    assert response.headers["x-request-id"] == "abcdef123456"


async def test_cors_exposes_access_status(client: httpx.AsyncClient) -> None:
    response = await client.options(
        "/api/auth/login",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"},
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    simple = await client.get("/health", headers={"Origin": "http://localhost:3000"})
    exposed = simple.headers["access-control-expose-headers"].lower()
    assert "x-access-status" in exposed
    assert "x-two-factor-setup-required" in exposed
    assert "x-confirm-provider" in exposed


async def test_protected_routes_need_a_token(client: httpx.AsyncClient) -> None:
    for path in (
        "/api/auth/me",
        "/api/users",
        "/api/secrets",
        "/api/access/roster",
        "/api/settings/ai-routing",
    ):
        response = await client.get(path)
        assert response.status_code == 401, path
        assert response.headers["cache-control"] == "no-store"


async def test_no_reveal_route(client: httpx.AsyncClient) -> None:
    paths = {route.path for route in app.routes if hasattr(route, "path")}
    assert not any("reveal" in path for path in paths)
    response = await client.get("/api/secrets/GEMINI_API_KEY/reveal")
    assert response.status_code in {401, 404, 405}


def migration_tree() -> ast.Module:
    return ast.parse(MIGRATION.read_text(encoding="utf-8"))


def module_constant(tree: ast.Module, name: str) -> object | None:
    for node in tree.body:
        target = node.target if isinstance(node, ast.AnnAssign) else None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
        if isinstance(target, ast.Name) and target.id == name and node.value is not None:
            return ast.literal_eval(node.value)
    return None


def enum_additions() -> dict[str, tuple[str, ...]]:
    added: dict[str, tuple[str, ...]] = {}
    for path in sorted(MIGRATIONS.glob("[0-9][0-9][0-9][0-9]_*.py")):
        if path == MIGRATION:
            continue
        for name, values in (
            module_constant(ast.parse(path.read_text(encoding="utf-8")), "ENUM_ADDITIONS") or ()
        ):
            added[name] = added.get(name, ()) + tuple(values)
    return added


def is_call_to(node: ast.AST, attr: str) -> bool:
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == attr


def first_string(call: ast.Call) -> str | None:
    if call.args and isinstance(call.args[0], ast.Constant) and isinstance(call.args[0].value, str):
        return call.args[0].value
    return None


def later_upgrade_steps() -> list[ast.FunctionDef]:
    steps = []
    for path in sorted(MIGRATIONS.glob("[0-9][0-9][0-9][0-9]_*.py")):
        if path == MIGRATION:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        steps.extend(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name != "downgrade")
    return steps


def created_tables() -> list[ast.Call]:
    roots = [migration_tree(), *later_upgrade_steps()]
    return [node for root in roots for node in ast.walk(root) if is_call_to(node, "create_table")]


def migration_tables() -> dict[str, dict[str, ast.Call]]:
    tables: dict[str, dict[str, ast.Call]] = {}
    for node in created_tables():
        if first_string(node) is None:
            continue
        name = first_string(node)
        assert name not in tables, f"{name} is created twice"
        columns: dict[str, ast.Call] = {}
        for arg in node.args[1:]:
            if is_call_to(arg, "Column") and first_string(arg) is not None:
                column = first_string(arg)
                assert column not in columns, f"{name}.{column} is declared twice"
                columns[column] = arg
        tables[name] = columns
    for table, column, call in later_column_changes():
        if call is None:
            tables[table].pop(column, None)
        else:
            assert column not in tables[table], f"{table}.{column} is added twice"
            tables[table][column] = call
    for table in later_dropped_tables():
        assert table in tables, f"{table} is dropped before it is created"
        tables.pop(table)
    return tables


def later_dropped_tables() -> list[str]:
    calls = [
        node for step in later_upgrade_steps() for node in ast.walk(step) if is_call_to(node, "drop_table")
    ]
    names = [first_string(call) for call in calls if isinstance(call, ast.Call)]
    return [name for name in names if name is not None]


def later_column_changes() -> list[tuple[str, str, ast.Call | None]]:
    changes: list[tuple[str, str, ast.Call | None]] = []
    for step in later_upgrade_steps():
        for node in ast.walk(step):
            if is_call_to(node, "add_column") and len(node.args) == 2 and is_call_to(node.args[1], "Column"):
                changes.append((first_string(node), first_string(node.args[1]), node.args[1]))
            elif is_call_to(node, "drop_column") and len(node.args) == 2:
                changes.append((first_string(node), ast.literal_eval(node.args[1]), None))
    return changes


def initial_enum_list() -> dict[str, tuple[str, ...]]:
    pairs = module_constant(migration_tree(), "ENUMS")
    if pairs is None:
        raise AssertionError("ENUMS is missing from the migration")
    names = [name for name, _values in pairs]
    assert len(names) == len(set(names)), "ENUMS lists a type twice"
    return {name: tuple(values) for name, values in pairs}


def migration_enum_list() -> dict[str, tuple[str, ...]]:
    added = enum_additions()
    return {name: values + added.get(name, ()) for name, values in initial_enum_list().items()}


def inline_enum(column: ast.Call) -> tuple[str, tuple[str, ...]] | None:
    for node in ast.walk(column):
        if is_call_to(node, "ENUM"):
            names = [kw.value for kw in node.keywords if kw.arg == "name"]
            assert names and isinstance(names[0], ast.Constant), ast.unparse(column)
            values = tuple(ast.literal_eval(arg) for arg in node.args)
            return names[0].value, values
    return None


def model_enums() -> dict[str, tuple[str, ...]]:
    enums: dict[str, tuple[str, ...]] = {}
    for table in Base.metadata.tables.values():
        for column in table.columns:
            if isinstance(column.type, sa.Enum) and column.type.name:
                values = tuple(column.type.enums)
                previous = enums.setdefault(column.type.name, values)
                assert previous == values, (column.type.name, previous, values)
    return enums


def test_migration_creates_every_model_table() -> None:
    assert set(migration_tables()) == set(Base.metadata.tables)


@pytest.mark.parametrize("table", sorted(Base.metadata.tables))
def test_migration_columns_match_model(table: str) -> None:
    migrated = migration_tables().get(table, {})
    modelled = {column.name for column in Base.metadata.tables[table].columns}
    assert set(migrated) == modelled, {
        "missing_in_migration": sorted(modelled - set(migrated)),
        "missing_in_model": sorted(set(migrated) - modelled),
    }


@pytest.mark.parametrize("table", sorted(Base.metadata.tables))
def test_migration_enum_columns_match_model(table: str) -> None:
    declared = migration_enum_list()
    model_columns = Base.metadata.tables[table].c
    for name, call in migration_tables().get(table, {}).items():
        if name not in model_columns:
            continue
        column_type = model_columns[name].type
        found = inline_enum(call)
        if found is None:
            assert not isinstance(column_type, sa.Enum), f"{table}.{name} is an enum only in the model"
            continue
        enum_name, values = found
        values += enum_additions().get(enum_name, ())
        assert isinstance(column_type, sa.Enum), f"{table}.{name} is an enum only in the migration"
        assert enum_name == column_type.name, (table, name, enum_name, column_type.name)
        assert values == tuple(column_type.enums), (table, name, values, column_type.enums)
        assert declared.get(enum_name) == values, (table, name, enum_name)


def test_migration_enum_types_match_model() -> None:
    declared = migration_enum_list()
    modelled = model_enums()
    assert set(declared) == set(modelled), {
        "missing_in_migration": sorted(set(modelled) - set(declared)),
        "missing_in_model": sorted(set(declared) - set(modelled)),
    }
    for name, values in modelled.items():
        assert declared[name] == values, (name, declared[name], values)


def test_tables_use_pascal_case_and_camel_case_columns() -> None:
    for table in Base.metadata.tables.values():
        assert re.fullmatch(r"[A-Z][A-Za-z0-9]*", table.name), table.name
        for column in table.columns:
            assert re.fullmatch(r"[a-z][A-Za-z0-9]*", column.name), (table.name, column.name)


def test_vector_columns_are_1536() -> None:
    for table, column in (("Chunk", "embedding"), ("Claim", "embedding"), ("Craft", "descriptorEmbedding")):
        assert Base.metadata.tables[table].c[column].type.dim == 1536


def python_sources() -> list[Path]:
    roots = [BACKEND / "app", BACKEND / "tests", BACKEND / "migrations"]
    return [path for root in roots for path in root.rglob("*.py") if ".venv" not in path.parts]


@pytest.mark.parametrize("path", python_sources(), ids=lambda p: str(p.relative_to(BACKEND)))
def test_no_code_comments(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.COMMENT:
            assert FUNCTIONAL_DIRECTIVE.match(token.string), f"{path}:{token.start[0]} {token.string}"


def test_alias_source_downgrade_restores_the_initial_values() -> None:
    later = ast.parse((MIGRATIONS / "0002_portal_alias_source.py").read_text(encoding="utf-8"))
    assert module_constant(later, "ALIAS_SOURCES_BEFORE") == initial_enum_list()["AliasSource"]
    assert enum_additions()["AliasSource"] == ("FR_SYNC",)


def initial_columns_of_enum(enum_name: str) -> set[tuple[str, str]]:
    found: set[tuple[str, str]] = set()
    for node in ast.walk(migration_tree()):
        if not is_call_to(node, "create_table") or first_string(node) is None:
            continue
        for arg in node.args[1:]:
            enum = inline_enum(arg) if is_call_to(arg, "Column") else None
            if enum is not None and enum[0] == enum_name:
                found.add((first_string(node), first_string(arg)))
    return found


def test_user_role_downgrade_restores_the_initial_values() -> None:
    later = ast.parse((MIGRATIONS / "0009_admin_role.py").read_text(encoding="utf-8"))
    assert module_constant(later, "USER_ROLES_BEFORE") == initial_enum_list()["UserRole"]
    assert enum_additions()["UserRole"] == ("ADMIN", "ARTISAN")
    retyped = {(table, column) for table, column, _default in module_constant(later, "ROLE_COLUMNS")}
    assert retyped == initial_columns_of_enum("UserRole")
    assert len(retyped) == 6


def test_claim_status_downgrade_restores_the_initial_values() -> None:
    later = ast.parse((MIGRATIONS / "0017_curated_dossiers.py").read_text(encoding="utf-8"))
    assert module_constant(later, "CLAIM_STATUSES_BEFORE") == initial_enum_list()["ClaimStatus"]
    assert enum_additions()["ClaimStatus"] == ("SUPERSEDED", "WITHDRAWN")
    retyped = {(table, column) for table, column, _default in module_constant(later, "CLAIM_STATUS_COLUMNS")}
    assert retyped == initial_columns_of_enum("ClaimStatus")
