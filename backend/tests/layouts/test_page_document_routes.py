import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api import document_reads
from app.api.routes import page_documents
from app.core.db import get_session
from app.core.deps import get_current_user, get_optional_user
from app.core.errors import InvalidInput, Refused
from app.main import create_app
from app.models import User
from app.research.document_parts import compact_json
from app.research.monograph_document import MonographDocument
from app.research.page_layout import LayoutWrite, PageLayout
from app.services.monograph_document import document_body, document_hash
from app.services.monograph_generated_assembly import assembled_document
from app.services.monograph_generated_drawings import Drawings
from app.services.page_translation_serving import ServedPage, ShownPage
from app.services.stored_documents import GeneratedRead, StoredCopy

from .generated_parts import generated, hero_layout

KNOWN = {("category", "Textile-Craft-Category"), ("family", "Other-Textiles"), ("craft", "Bagh-Print")}
HERO = {"ref": "bagh-print/pictures/i02", "chapter": "glance", "order": 1, "role": "HERO"}


class QuietSession:
    def __init__(self) -> None:
        self.ended: list[str] = []

    async def commit(self) -> None:
        self.ended.append("commit")

    async def rollback(self) -> None:
        self.ended.append("rollback")


class AskedLanguages:
    def __init__(self) -> None:
        self.asked: list[tuple[Any, str, str]] = []
        self.translated = False

    async def in_language(
        self, session: Any, page: Any, english: ServedPage, *, tag: str, language: str
    ) -> ShownPage:
        self.asked.append((page, tag, language))
        if not self.translated or language != "hi":
            return ShownPage(english, wrote=False)
        body = {**english.body, "language": "hi", "title": "बाघ छपाई"}
        return ShownPage(ServedPage(f"{english.etag}-hi-{'c' * 16}", "hi", body), wrote=False)


@pytest.fixture
def languages(monkeypatch: pytest.MonkeyPatch) -> AskedLanguages:
    asked = AskedLanguages()
    monkeypatch.setattr(document_reads, "page_in_language", asked.in_language)
    return asked


@pytest.fixture
def held(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, languages: AskedLanguages) -> dict[str, Any]:
    state: dict[str, Any] = {
        "session": QuietSession(),
        "writes": [],
        "document": assembled_document(generated(), Drawings(root=tmp_path)),
        "layout": hero_layout(),
        "rebuild": False,
        "queued": [],
        "languages": languages,
    }

    async def subject(session: Any, kind: str, slug: str) -> object:
        if (kind, slug) not in KNOWN:
            raise InvalidInput(f"No {kind} has the slug {slug}.")
        return object()

    async def read(session: Any, kind: str, slug: str) -> GeneratedRead:
        await subject(session, kind, slug)
        held = stored(state["document"], current=not state["rebuild"])
        return GeneratedRead(SimpleNamespace(kind=kind, slug=slug), held, rebuild=state["rebuild"])  # type: ignore[arg-type]

    async def queued(kind: str, slug: str) -> None:
        state["queued"].append((kind, slug))

    async def layout(session: Any, kind: str, slug: str) -> PageLayout | None:
        await subject(session, kind, slug)
        return state["layout"]

    async def write(session: Any, kind: str, slug: str, written: LayoutWrite, *, actor: Any) -> PageLayout:
        await subject(session, kind, slug)
        if written.base_version != 2:
            raise Refused("stale_layout", "The layout of Bagh-Print is at version 2, not 1.")
        state["writes"].append((kind, slug, actor.role, len(written.entries)))
        return state["layout"].model_copy(update={"version": 3})

    monkeypatch.setattr(page_documents, "generated_read", read)
    monkeypatch.setattr(document_reads, "rebuild_wanted", queued)
    monkeypatch.setattr(page_documents, "page_layout", layout)
    monkeypatch.setattr(page_documents, "write_layout", write)
    return state


def stored(document: MonographDocument | None, *, current: bool) -> StoredCopy | None:
    if document is None:
        return None
    text = compact_json(document_body(document))
    return StoredCopy(text, document.version, document_hash(document), document.language, current)


def client(state: dict[str, Any], role: str | None = None) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_session] = lambda: state["session"]
    if role is not None:
        user = User(id=uuid.UUID(int=8), name="Asha", email="asha@example.org", role=role)
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_optional_user] = lambda: user
    return TestClient(app)


@pytest.mark.parametrize(
    "path", ["/api/categories/Textile-Craft-Category/monograph", "/api/families/Other-Textiles/monograph"]
)
def test_a_category_or_family_monograph_is_a_public_read_with_an_etag(
    path: str, held: dict[str, Any]
) -> None:
    http = client(held)
    answer = http.get(path)
    assert answer.status_code == 200
    assert answer.json()["subjectSlug"] == "Bagh-Print"
    assert answer.json()["content"]["layout"][0]["ref"] == "bagh-print/pictures/i02"
    assert answer.headers["Cache-Control"] == "public, max-age=300"
    document = held["document"]
    assert answer.headers["ETag"] == f'"v{document.version}-{document_hash(document)}"'
    again = http.get(path, headers={"If-None-Match": answer.headers["ETag"]})
    assert again.status_code == 304
    assert held["queued"] == []


def test_a_stale_stored_document_is_served_and_its_rebuild_queued_after_the_answer(
    held: dict[str, Any],
) -> None:
    held["rebuild"] = True
    answer = client(held).get("/api/families/Other-Textiles/monograph")
    assert answer.status_code == 200
    assert answer.json()["subjectSlug"] == "Bagh-Print"
    assert held["queued"] == [("family", "Other-Textiles")]


def test_a_document_read_in_parts_gives_the_whole_document_back_and_no_part_beyond(
    held: dict[str, Any],
) -> None:
    http = client(held)
    read = http.get("/api/categories/Textile-Craft-Category/monograph")
    whole = read.json()
    first = http.get("/api/categories/Textile-Craft-Category/monograph", params={"part": 0})
    assert first.status_code == 200
    assert first.json() == {
        "schemaVersion": 1,
        "version": whole["version"],
        "part": 0,
        "parts": 1,
        "tag": read.headers["ETag"].strip('"'),
        "body": whole,
    }
    assert first.headers["ETag"].endswith('-p0"')
    beyond = http.get("/api/categories/Textile-Craft-Category/monograph", params={"part": 1})
    assert beyond.status_code == 404
    assert beyond.json()["detail"] == "This monograph has no such part."
    assert (
        http.get("/api/categories/Textile-Craft-Category/monograph", params={"part": -1}).status_code == 422
    )


@pytest.mark.parametrize(
    "path", ["/api/categories/Textile-Craft-Category/monograph", "/api/families/Other-Textiles/monograph"]
)
def test_a_category_or_family_monograph_asks_for_the_language_and_is_english_without_a_translation(
    path: str, held: dict[str, Any]
) -> None:
    answer = client(held).get(path, params={"lang": "hi"})
    assert answer.status_code == 200
    assert answer.headers["Content-Language"] == "en"
    assert answer.json()["language"] == "en"
    assert [language for _, _, language in held["languages"].asked] == ["hi"]
    unknown = client(held).get(path, params={"lang": "xx"})
    assert unknown.status_code == 200
    assert held["languages"].asked[-1][2] == "en"


def test_a_translated_category_is_served_from_its_stored_english_copy_under_its_language_tag(
    held: dict[str, Any],
) -> None:
    held["languages"].translated = True
    document = held["document"]
    english_tag = f"v{document.version}-{document_hash(document)}"
    http = client(held)
    answer = http.get("/api/categories/Textile-Craft-Category/monograph", params={"lang": "hi"})
    assert answer.status_code == 200
    assert answer.headers["Content-Language"] == "hi"
    assert answer.headers["ETag"] == f'"{english_tag}-hi-{"c" * 16}"'
    assert (answer.json()["language"], answer.json()["title"]) == ("hi", "बाघ छपाई")
    assert held["languages"].asked == [(("category", "Textile-Craft-Category"), english_tag, "hi")]
    first = http.get("/api/categories/Textile-Craft-Category/monograph", params={"lang": "hi", "part": 0})
    assert first.json()["tag"] == f"{english_tag}-hi-{'c' * 16}"
    assert first.json()["body"]["title"] == "बाघ छपाई"
    english = http.get("/api/categories/Textile-Craft-Category/monograph")
    assert (english.headers["ETag"], english.json()["language"]) == (f'"{english_tag}"', "en")


def test_an_unknown_subject_or_one_with_nothing_published_is_a_404(held: dict[str, Any]) -> None:
    http = client(held)
    assert http.get("/api/families/No-Such-Family/monograph").status_code == 404
    held["document"] = None
    answer = http.get("/api/categories/Textile-Craft-Category/monograph")
    assert answer.status_code == 404
    assert answer.json()["detail"] == "There is no monograph for that category yet."


def test_a_layout_is_read_by_anyone_and_a_missing_one_is_a_404(held: dict[str, Any]) -> None:
    http = client(held)
    answer = http.get("/api/pages/craft/Bagh-Print/layout")
    assert answer.status_code == 200
    assert answer.json()["entries"][0]["crop"] == {"x": 0.2, "y": 0.2, "width": 0.6, "height": 0.6}
    assert http.get("/api/pages/planet/Bagh-Print/layout").status_code == 422
    assert http.get("/api/pages/craft/No-Such-Craft/layout").status_code == 404
    held["layout"] = None
    assert http.get("/api/pages/craft/Bagh-Print/layout").json()["detail"] == "That page has no layout yet."


@pytest.mark.parametrize("role", ["STUDENT", "RESEARCHER", "PROFESSOR"])
def test_below_admin_may_not_write_a_layout(role: str, held: dict[str, Any]) -> None:
    answer = client(held, role).put(
        "/api/pages/craft/Bagh-Print/layout", json={"baseVersion": 2, "entries": [HERO]}
    )
    assert answer.status_code == 403
    assert held["writes"] == []


@pytest.mark.parametrize("role", ["ADMIN", "MASTER_ADMIN"])
def test_an_admin_writes_the_next_version_on_the_one_read(role: str, held: dict[str, Any]) -> None:
    answer = client(held, role).put(
        "/api/pages/craft/Bagh-Print/layout", json={"baseVersion": 2, "entries": [HERO]}
    )
    assert answer.status_code == 200
    assert answer.json()["version"] == 3
    assert held["writes"] == [("craft", "Bagh-Print", role, 1)]
    assert held["session"].ended == ["commit"]


def test_a_write_on_a_stale_version_is_a_409_and_a_broken_rule_a_422(held: dict[str, Any]) -> None:
    http = client(held, "ADMIN")
    stale = http.put("/api/pages/craft/Bagh-Print/layout", json={"baseVersion": 1, "entries": [HERO]})
    assert stale.status_code == 409
    assert "version 2" in stale.json()["detail"]
    assert held["session"].ended == ["rollback"]
    second = {**HERO, "ref": "bagh-print/pictures/i01", "order": 2}
    broken = http.put(
        "/api/pages/craft/Bagh-Print/layout", json={"baseVersion": 2, "entries": [HERO, second]}
    )
    assert broken.status_code == 422
    assert held["writes"] == []
