import hashlib
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.routes import craft_monograph as route
from app.core.db import get_session
from app.main import create_app
from app.research.monograph_document import MonographDocument, served_language
from app.services.answering import NOT_FOUND_DETAIL

PATH = "/api/crafts/kutch-ajrakh/monograph"
DIGEST = "a" * 64
STORED = {
    "schemaVersion": 1,
    "subjectKind": "craft",
    "subjectSlug": "Kutch-Ajrakh",
    "language": "en",
    "version": 3,
    "title": "Kutch Ajrakh",
}
GENERATED = MonographDocument.model_validate(
    {
        "subjectKind": "craft",
        "subjectSlug": "Kutch-Ajrakh",
        "title": "Kutch Ajrakh",
        "version": 1,
        "content": {
            "craftSlug": "Kutch-Ajrakh",
            "sources": {},
            "citations": {},
            "citationClaims": {},
            "data": {},
            "units": {},
            "components": [],
            "layout": [],
        },
        "pageUrl": "https://kalavigyan.example/crafts/Kutch-Ajrakh",
    }
)


@dataclass
class Calls:
    made: list[str] = field(default_factory=list)


def served(
    monkeypatch: pytest.MonkeyPatch,
    *,
    known: bool = True,
    stored: bool = True,
    generated: bool = False,
    body: dict[str, Any] | None = None,
    ground: Any = None,
) -> tuple[TestClient, Calls]:
    calls = Calls()
    document = STORED if body is None else body

    async def resolve_craft(session: Any, slug: str) -> Any:
        calls.made.append(f"resolve {slug}")
        return SimpleNamespace(slug="Kutch-Ajrakh") if known else None

    async def document_row(session: Any, subject_kind: str, slug: str, *, language: str, version: Any) -> Any:
        calls.made.append(f"stored {subject_kind} {slug} {language} {version}")
        if not stored or version not in (None, 3):
            return None
        return SimpleNamespace(version=3, language="en", contentHash=DIGEST, document=document)

    async def generated_fallback(session: Any, craft: Any) -> MonographDocument | None:
        calls.made.append(f"generated {craft.slug}")
        return GENERATED if generated else None

    async def stored_ground(session: Any, craft: Any) -> Any:
        return ground

    async def session() -> AsyncIterator[object]:
        yield object()

    monkeypatch.setattr(route.knowledge_view, "resolve_craft", resolve_craft)
    monkeypatch.setattr(route, "document_row", document_row)
    monkeypatch.setattr(route, "generated_fallback", generated_fallback)
    monkeypatch.setattr(route, "stored_ground", stored_ground)
    app = create_app()
    app.dependency_overrides[get_session] = session
    return TestClient(app), calls


def test_the_latest_stored_document_is_served_with_its_version_tag_and_the_public_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    http, calls = served(monkeypatch)
    answer = http.get(PATH)
    assert answer.status_code == 200
    assert answer.json() == STORED
    assert answer.headers["etag"] == f'"v3-{DIGEST}"'
    assert answer.headers["cache-control"] == "public, max-age=300"
    assert answer.headers["content-language"] == "en"
    assert "Authorization" in answer.headers["vary"]
    assert calls.made == ["resolve kutch-ajrakh", "stored craft Kutch-Ajrakh en None"]


def test_a_document_stored_without_its_language_is_served_with_its_rows_language(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    older = {key: value for key, value in STORED.items() if key != "language"}
    http, _ = served(monkeypatch, body=older)
    assert http.get(PATH).json() == {**older, "language": "en"}


@pytest.mark.parametrize("asked", ["hi", "ur", "EN", "kn-Knda"])
def test_a_request_for_another_language_gets_the_english_document_said_to_be_english(
    monkeypatch: pytest.MonkeyPatch, asked: str
) -> None:
    http, calls = served(monkeypatch)
    answer = http.get(PATH, params={"lang": asked})
    assert answer.status_code == 200
    assert answer.headers["content-language"] == "en"
    assert answer.json()["language"] == "en"
    assert calls.made[-1] == "stored craft Kutch-Ajrakh en None"
    assert served_language(asked) == "en"


def test_a_versioned_request_reads_that_version_and_an_unknown_one_is_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    http, calls = served(monkeypatch)
    assert http.get(PATH, params={"version": 3}).status_code == 200
    assert calls.made[-1] == "stored craft Kutch-Ajrakh en 3"
    missing = http.get(PATH, params={"version": 9})
    assert missing.status_code == 404
    assert missing.json()["detail"] == route.NO_VERSION_DETAIL
    assert http.get(PATH, params={"version": 0}).status_code == 422


def test_a_reader_holding_the_document_is_told_it_is_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    http, _ = served(monkeypatch)
    answer = http.get(PATH, headers={"If-None-Match": f'"v3-{DIGEST}"'})
    assert answer.status_code == 304
    assert answer.content == b""
    assert answer.headers["content-language"] == "en"


def test_without_a_stored_document_the_generated_one_is_served(monkeypatch: pytest.MonkeyPatch) -> None:
    http, calls = served(monkeypatch, stored=False, generated=True)
    answer = http.get(PATH)
    body = GENERATED.model_dump(mode="json", by_alias=True)
    assert answer.status_code == 200 and answer.json() == body
    assert body["language"] == "en"
    hashed = json.dumps(
        {k: v for k, v in body.items() if k not in {"version", "language"}},
        sort_keys=True,
        separators=(",", ":"),
    )
    assert answer.headers["etag"] == f'"v1-{hashlib.sha256(hashed.encode("utf-8")).hexdigest()}"'
    assert calls.made[-1] == "generated Kutch-Ajrakh"
    assert http.get(PATH, params={"version": 1}).status_code == 200
    assert http.get(PATH, params={"version": 2}).status_code == 404


@pytest.mark.parametrize(
    ("changes", "detail", "asked"),
    [
        ({"known": False}, NOT_FOUND_DETAIL, ["resolve kutch-ajrakh"]),
        (
            {"stored": False},
            route.NO_DOCUMENT_DETAIL,
            ["resolve kutch-ajrakh", "stored craft Kutch-Ajrakh en None", "generated Kutch-Ajrakh"],
        ),
    ],
    ids=["an unknown craft", "a craft with no document stored or generated"],
)
def test_a_craft_without_a_document_is_not_found(
    monkeypatch: pytest.MonkeyPatch, changes: dict[str, bool], detail: str, asked: list[str]
) -> None:
    http, calls = served(monkeypatch, **changes)
    answer = http.get(PATH)
    assert answer.status_code == 404
    assert answer.json()["detail"] == detail
    assert calls.made == asked


async def test_the_fallback_asks_for_a_craft_or_a_family_document_by_the_craft_list_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asked: list[tuple[str, str]] = []

    async def generated_document(session: Any, subject_kind: str, slug: str) -> MonographDocument | None:
        asked.append((subject_kind, slug))
        return None

    monkeypatch.setattr(route, "generated_document", generated_document)
    craft = SimpleNamespace(slug="Bagh-Print", isCatchAll=False, stateOfPractice=["Madhya Pradesh"])
    catch_all = SimpleNamespace(slug="Applique", isCatchAll=True, stateOfPractice=[])
    all_india = SimpleNamespace(slug="Tie-Dye", isCatchAll=False, stateOfPractice=["All India"])
    for row in (craft, catch_all, all_india):
        assert await route.generated_fallback(object(), row) is None
    assert asked == [("craft", "Bagh-Print"), ("family", "Applique"), ("family", "Tie-Dye")]
