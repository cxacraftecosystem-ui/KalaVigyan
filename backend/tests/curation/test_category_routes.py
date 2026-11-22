from __future__ import annotations

import json
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.routes import categories
from app.core.db import get_session
from app.core.http_cache import PRIVATE_NO_CACHE, PUBLIC_READ_CACHE
from app.main import create_app
from app.models import User
from app.services.category_page import CategoryPageRecords
from app.services.category_register import register_categories

from ..contracts.golden import golden_text
from ..readers import sign_in_as
from .category_support import LEATHER, LIST_GOLDEN, PAGE_GOLDEN, PAPER, UNCURATED_GOLDEN, leather_records

PAGE = f"/api/categories/{LEATHER}"


async def no_session() -> Any:
    yield None


def plain_records(slug: str) -> CategoryPageRecords:
    return CategoryPageRecords(category=next(c for c in register_categories() if c.slug == slug))


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    async def page_records(_session: Any, slug: str) -> Any:
        if slug == LEATHER:
            return leather_records()
        return plain_records(slug) if slug == PAPER else None

    async def list_records(_session: Any) -> Any:
        return [
            leather_records() if c.slug == LEATHER else plain_records(c.slug) for c in register_categories()
        ]

    monkeypatch.setattr(categories, "category_page_records", page_records)
    monkeypatch.setattr(categories, "category_list_records", list_records)
    app = create_app()
    app.dependency_overrides[get_session] = no_session
    return TestClient(app)


def test_a_category_page_is_read_without_signing_in(client: TestClient) -> None:
    response = client.get(PAGE)
    assert response.status_code == 200
    assert response.json() == json.loads(golden_text(PAGE_GOLDEN))
    assert response.headers["cache-control"] == PUBLIC_READ_CACHE
    assert response.headers["etag"].startswith('"')
    assert "Authorization" in response.headers["vary"]
    paper = client.get(f"/api/categories/{PAPER}")
    assert paper.json() == json.loads(golden_text(UNCURATED_GOLDEN))


def test_the_list_is_read_without_signing_in(client: TestClient) -> None:
    response = client.get("/api/categories")
    assert response.status_code == 200
    assert response.json() == json.loads(golden_text(LIST_GOLDEN))
    assert response.headers["cache-control"] == PUBLIC_READ_CACHE


def test_an_unchanged_page_answers_304_and_a_changed_one_a_new_tag(client: TestClient) -> None:
    first = client.get(PAGE)
    tag = first.headers["etag"]
    again = client.get(PAGE, headers={"If-None-Match": tag})
    assert (again.status_code, again.content, again.headers["etag"]) == (304, b"", tag)
    other = client.get(f"/api/categories/{PAPER}")
    assert other.headers["etag"] != tag
    assert client.get("/api/categories").headers["etag"] not in {tag, other.headers["etag"]}


def test_an_unknown_category_is_404(client: TestClient) -> None:
    response = client.get("/api/categories/Glass-Craft-Category")
    assert response.status_code == 404
    assert response.json() == {"detail": categories.CATEGORY_NOT_FOUND_DETAIL}


def test_a_signed_in_reader_gets_the_same_page_kept_private(client: TestClient) -> None:
    reader = User(id=uuid.UUID(int=8), name="Student", email="student@example.com", role="STUDENT")
    sign_in_as(client.app, lambda: reader)
    response = client.get(PAGE)
    assert response.status_code == 200
    assert response.json() == json.loads(golden_text(PAGE_GOLDEN))
    assert response.headers["cache-control"] == PRIVATE_NO_CACHE
