import os

os.environ.setdefault("DATABASE_URL", "postgresql://kalavigyan:kalavigyan@localhost:5432/kalavigyan_test")
os.environ.setdefault("JWT_SECRET", "test-only-signing-key-" + "k" * 40)
os.environ.setdefault("MASTER_ADMIN_EMAIL", "owner@example.com")
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SECRETS_ENCRYPTION_KEY", "")
os.environ.setdefault("TWO_FACTOR_ENCRYPTION_KEY", "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=")
os.environ.setdefault("BACKEND_CORS_ORIGINS", "http://localhost:3000")

import pytest

from app.core import allowances, roles

from .ai_caps import ALLOWANCES_AN_OWNER_MIGHT_SET
from .allowance_counter import MemoryCounter


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if os.environ.get("RUN_DB_TESTS") == "1":
        return
    skip = pytest.mark.skip(reason="needs Postgres with pgvector and PostGIS; set RUN_DB_TESTS=1")
    for item in items:
        if "db" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(autouse=True)
def allowance_counter(monkeypatch: pytest.MonkeyPatch) -> MemoryCounter:
    counter = MemoryCounter()
    monkeypatch.setattr(allowances, "counter", counter)
    return counter


@pytest.fixture
def allowances_an_owner_might_set(monkeypatch: pytest.MonkeyPatch) -> dict[str, dict[str, int | None]]:
    monkeypatch.setattr(roles, "DAILY_ALLOWANCES", ALLOWANCES_AN_OWNER_MIGHT_SET)
    return ALLOWANCES_AN_OWNER_MIGHT_SET
