import json
import uuid
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.routes import crafts
from app.core.db import get_session
from app.core.http_cache import body_version
from app.main import create_app
from app.models import User
from app.services import knowledge_view
from app.services.craft_page_cache import ServedPage, served_content

from ..contracts.golden import golden_text
from ..readers import sign_in_as
from .import_support import AJRAKH, AJRAKH_GOLDEN

PATH = f"/api/crafts/{AJRAKH}/page"
PIECE = uuid.UUID(int=41)
OLDER = 1


async def no_session() -> Any:
    yield None


def golden() -> dict[str, Any]:
    return json.loads(golden_text(AJRAKH_GOLDEN))


def client_for(monkeypatch: pytest.MonkeyPatch, role: str | None, served: list[str]) -> TestClient:
    async def resolve(_session: Any, slug: str) -> Any:
        return SimpleNamespace(slug=slug, id=uuid.UUID(int=1)) if slug == AJRAKH else None

    async def page(_session: Any, _craft: Any, variant: str, **_options: Any) -> ServedPage:
        served.append(variant)
        body = golden()
        return ServedPage(served_content(body), body_version(body), variant)

    async def hidden(
        _session: Any, _craft: Any, piece_id: uuid.UUID, *, hidden: bool, **_kwargs: Any
    ) -> bool | None:
        return hidden if piece_id == PIECE else None

    monkeypatch.setattr(knowledge_view, "resolve_craft", resolve)
    monkeypatch.setattr(crafts, "served_page", page)
    monkeypatch.setattr(crafts, "set_page_piece_hidden", hidden)
    app = create_app()
    if role is not None:
        reader = User(id=uuid.UUID(int=8), name=role.title(), email=f"{role.lower()}@example.com", role=role)
        sign_in_as(app, lambda: reader)
    app.dependency_overrides[get_session] = no_session
    return TestClient(app)


@pytest.mark.parametrize("role", [None, "STUDENT"])
def test_anonymous_and_student_readers_get_the_open_page_with_all_its_evidence(
    monkeypatch: pytest.MonkeyPatch, role: str | None
) -> None:
    served: list[str] = []
    response = client_for(monkeypatch, role, served).get(PATH)
    assert response.status_code == 200
    assert served == ["OPEN"]
    assert response.json() == golden()
    assert response.json()["evidence"] is not None


@pytest.mark.parametrize("role", ["RESEARCHER", "PROFESSOR", "MASTER_ADMIN"])
def test_a_researcher_and_above_get_the_researcher_variant(
    monkeypatch: pytest.MonkeyPatch, role: str
) -> None:
    served: list[str] = []
    response = client_for(monkeypatch, role, served).get(PATH)
    assert response.status_code == 200
    assert served == ["RESEARCHER"]
    assert response.headers["cache-control"] == "private, no-cache"


def test_the_page_keeps_no_archived_versions_since_an_edition_is_a_monograph_document(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    served: list[str] = []
    client = client_for(monkeypatch, None, served)
    assert client.get(PATH, params={"version": OLDER}).json() == golden()
    assert served == ["OPEN"]
    assert not hasattr(crafts, "archived_page")


def test_only_a_professor_hides_a_piece_on_the_page(monkeypatch: pytest.MonkeyPatch) -> None:
    path = f"/api/crafts/{AJRAKH}/pieces/{PIECE}/hidden"
    assert client_for(monkeypatch, None, []).put(path, json={"hidden": True}).status_code == 401
    assert client_for(monkeypatch, "STUDENT", []).put(path, json={"hidden": True}).status_code == 403
    professor = client_for(monkeypatch, "PROFESSOR", [])
    assert professor.put(path, json={"hidden": True}).json() == {"hidden": True}
    unknown = f"/api/crafts/{AJRAKH}/pieces/{uuid.UUID(int=99)}/hidden"
    assert professor.put(unknown, json={"hidden": True}).status_code == 404
