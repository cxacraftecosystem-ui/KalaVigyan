import hashlib
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api import document_reads
from app.api.routes import craft_monograph as route
from app.core.db import get_session
from app.main import create_app
from app.research.document_parts import compact_json, document_parts
from app.research.monograph_document import MonographDocument, served_language
from app.services.answering import NOT_FOUND_DETAIL
from app.services.monograph_document import document_body, document_hash
from app.services.stored_documents import GeneratedRead, StoredCopy

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
    queued: list[tuple[str, str]] = field(default_factory=list)


def stored_copy(document: MonographDocument, *, current: bool = True) -> StoredCopy:
    text = compact_json(document_body(document))
    return StoredCopy(text, document.version, document_hash(document), document.language, current)


async def no_session() -> AsyncIterator[object]:
    yield object()


def watch_rebuilds(monkeypatch: pytest.MonkeyPatch, calls: Calls) -> None:
    async def rebuild_wanted(kind: str, slug: str) -> None:
        calls.queued.append((kind, slug))

    monkeypatch.setattr(document_reads, "rebuild_wanted", rebuild_wanted)


def served(
    monkeypatch: pytest.MonkeyPatch,
    *,
    known: bool = True,
    stored: bool = True,
    generated: bool = False,
    body: dict[str, Any] | None = None,
    ground: Any = None,
    stale: bool = False,
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

    async def generated_fallback(session: Any, craft: Any) -> GeneratedRead:
        calls.made.append(f"generated {craft.slug}")
        copy = stored_copy(GENERATED, current=not stale) if generated else None
        return GeneratedRead(SimpleNamespace(kind="craft", slug=craft.slug), copy, rebuild=stale)  # type: ignore[arg-type]

    async def stored_ground(session: Any, craft: Any) -> Any:
        return ground

    monkeypatch.setattr(route.knowledge_view, "resolve_craft", resolve_craft)
    monkeypatch.setattr(route, "document_row", document_row)
    monkeypatch.setattr(route, "generated_fallback", generated_fallback)
    monkeypatch.setattr(route, "stored_ground", stored_ground)
    watch_rebuilds(monkeypatch, calls)
    app = create_app()
    app.dependency_overrides[get_session] = no_session
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
    assert calls.queued == []


def test_a_stale_generated_document_is_served_as_it_was_and_its_rebuild_queued(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    http, calls = served(monkeypatch, stored=False, generated=True, stale=True)
    answer = http.get(PATH)
    assert answer.status_code == 200
    assert answer.json() == GENERATED.model_dump(mode="json", by_alias=True)
    assert calls.queued == [("craft", "Kutch-Ajrakh")]


def test_a_document_larger_than_a_part_is_read_part_by_part_and_rejoins_whole(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    whole = {
        **STORED,
        "shell": "<section>" + "s" * 120 + "</section>",
        "specs": {"a": {"text": "a" * 120}, "b": {"text": "b" * 120}},
        "fragments": {},
    }
    http, _ = served(monkeypatch, body=whole)
    monkeypatch.setattr(document_reads, "document_parts", lambda body: document_parts(body, most=200))
    first = http.get(PATH, params={"part": 0}).json()
    assert (first["schemaVersion"], first["version"], first["part"], first["parts"]) == (1, 3, 0, 4)
    rejoined = dict(first["body"])
    rejoined.update(shell=None, specs={}, fragments={})
    for part in range(1, first["parts"]):
        answer = http.get(PATH, params={"part": part})
        assert answer.headers["etag"] == f'"v3-{DIGEST}-p{part}"'
        later = answer.json()["body"]
        rejoined["shell"] = later.get("shell", rejoined["shell"])
        rejoined["specs"].update(later["specs"])
        rejoined["fragments"].update(later["fragments"])
    assert rejoined == whole
    assert list(rejoined["specs"]) == ["a", "b"]
    assert http.get(PATH, params={"part": 4}).status_code == 404


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

    async def generated_read(session: Any, subject_kind: str, slug: str) -> GeneratedRead:
        asked.append((subject_kind, slug))
        return GeneratedRead(SimpleNamespace(kind=subject_kind, slug=slug), None)  # type: ignore[arg-type]

    monkeypatch.setattr(route, "generated_read", generated_read)
    craft = SimpleNamespace(slug="Bagh-Print", isCatchAll=False, stateOfPractice=["Madhya Pradesh"])
    catch_all = SimpleNamespace(slug="Applique", isCatchAll=True, stateOfPractice=[])
    all_india = SimpleNamespace(slug="Tie-Dye", isCatchAll=False, stateOfPractice=["All India"])
    for row in (craft, catch_all, all_india):
        assert (await route.generated_fallback(object(), row)).copy is None
    assert asked == [("craft", "Bagh-Print"), ("family", "Applique"), ("family", "Tie-Dye")]
