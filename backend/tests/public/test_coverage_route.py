from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.routes import coverage as route
from app.core.db import get_session
from app.core.errors import InvalidInput
from app.main import create_app
from app.research.coverage import CoverageSubject, FieldCoverage, Holdings, field_coverage

COVERAGE = field_coverage(
    CoverageSubject("craft", "Kutch-Ajrakh", "Kutch Ajrakh"),
    Holdings(filed={"c1": frozenset({"HISTORY"})}, sources={"c1": frozenset({"s1"})}),
    claims_min=3,
)


def client(monkeypatch: pytest.MonkeyPatch, *, known: bool = True) -> tuple[TestClient, list[str]]:
    asked: list[str] = []

    async def resolve_craft(session: Any, slug: str) -> Any:
        return SimpleNamespace(slug="Kutch-Ajrakh") if known else None

    async def craft_coverage(session: Any, slug: str) -> FieldCoverage:
        asked.append(f"craft {slug}")
        return COVERAGE

    async def category_coverage(session: Any, slug: str) -> FieldCoverage:
        asked.append(f"category {slug}")
        if slug != "Textiles":
            raise InvalidInput(f"No category has the slug {slug}.")
        return COVERAGE.model_copy(update={"subject_kind": "category", "subject_slug": "Textiles"})

    async def session() -> AsyncIterator[object]:
        yield object()

    monkeypatch.setattr(route.knowledge_view, "resolve_craft", resolve_craft)
    monkeypatch.setattr(route, "craft_coverage", craft_coverage)
    monkeypatch.setattr(route, "category_coverage", category_coverage)
    app = create_app()
    app.dependency_overrides[get_session] = session
    return TestClient(app), asked


def test_a_craft_s_coverage_is_served_as_a_public_cached_read(monkeypatch: pytest.MonkeyPatch) -> None:
    http, asked = client(monkeypatch)
    answer = http.get("/api/crafts/kutch-ajrakh/coverage")
    assert answer.status_code == 200
    body = answer.json()
    assert (body["subjectSlug"], body["thin"], len(body["fields"])) == ("Kutch-Ajrakh", ["HISTORY"], 16)
    assert answer.headers["cache-control"] == "public, max-age=300"
    assert asked == ["craft Kutch-Ajrakh"]
    unchanged = http.get(
        "/api/crafts/kutch-ajrakh/coverage", headers={"If-None-Match": answer.headers["etag"]}
    )
    assert unchanged.status_code == 304


def test_an_unknown_craft_or_category_has_no_coverage(monkeypatch: pytest.MonkeyPatch) -> None:
    http, _ = client(monkeypatch, known=False)
    missing = http.get("/api/crafts/no-such-craft/coverage")
    assert (missing.status_code, missing.json()["detail"]) == (404, route.CRAFT_NOT_FOUND_DETAIL)
    assert http.get("/api/categories/Textiles/coverage").json()["subjectKind"] == "category"
    assert http.get("/api/categories/Nothing-Here/coverage").status_code == 404
