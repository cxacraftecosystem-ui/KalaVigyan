import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.db import get_session
from app.data.craft_master_catalogue import build_catalogue
from app.main import create_app
from app.models import User
from app.services import craft_catalogue

from .readers import sign_in_as

PATH = "/api/crafts/catalogue"
PROFESSOR = User(id=uuid.UUID(int=9), name="Meera", email="meera@example.com", role="PROFESSOR")


class Loads:
    def __init__(self) -> None:
        self.calls: list[bool] = []

    async def __call__(self, _session: Any, *, include_inactive: bool = False) -> dict[str, Any]:
        self.calls.append(include_inactive)
        return build_catalogue()


async def no_session() -> AsyncIterator[None]:
    yield None


@pytest.fixture
def loads(monkeypatch: pytest.MonkeyPatch) -> Loads:
    counted = Loads()
    monkeypatch.setattr(craft_catalogue, "load_catalogue", counted)
    return counted


def client(reader: User | None = None) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_session] = no_session
    if reader is not None:
        sign_in_as(app, lambda: reader)
    return TestClient(app)


def test_the_reader_catalogue_is_built_once_and_revalidated_without_a_rebuild(loads: Loads) -> None:
    reader = client()
    first = reader.get(PATH)
    second = reader.get(PATH)
    unchanged = reader.get(PATH, headers={"If-None-Match": first.headers["etag"]})
    assert (first.status_code, second.status_code, unchanged.status_code) == (200, 200, 304)
    assert first.json() == second.json()
    assert loads.calls == [False]


def test_the_full_list_with_retired_crafts_is_always_read_fresh(loads: Loads) -> None:
    professor = client(PROFESSOR)
    assert professor.get(PATH, params={"includeInactive": "true"}).status_code == 200
    assert professor.get(PATH, params={"includeInactive": "true"}).status_code == 200
    assert professor.get(PATH).status_code == 200
    assert loads.calls == [True, True, False]
