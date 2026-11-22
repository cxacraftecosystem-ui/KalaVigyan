import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime
from io import BytesIO
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pptx import Presentation

from app.api import export_deps
from app.api.export_deps import export_tools
from app.api.routes import explainer_exports, lessons
from app.core.db import get_session
from app.core.deps import get_current_user
from app.main import create_app
from app.models import User
from app.research.explainer_versions import ExplainerVersionDocument
from app.research.lesson_builder import LessonNotBuildable
from app.services import knowledge_view, lesson_packs
from app.services.apa_references import apa_references
from app.services.explainer_history import UnknownExplainer
from app.services.export_files import ExportTools
from app.services.export_store import EXPORT_BUILDS_AT_ONCE

from ..contracts.learning_golden import CITATIONS, LESSON, VERSIONS, learning
from .lesson_fixtures import FakeBucket, first_version, golden_pack, picture_bytes

NOW = datetime(2026, 11, 18, 10, 0, tzinfo=UTC)
PROFESSOR = User(id=uuid.UUID(int=7), name="Asha Mehta", email="asha@example.org", role="PROFESSOR")
STUDENT = User(id=uuid.UUID(int=9), name="Ravi Shah", email="ravi@example.org", role="STUDENT")
PACK_ID = uuid.UUID(learning(LESSON)["pack"]["id"])
EXPLAINER_ID = uuid.UUID(learning(VERSIONS)["latest"]["mark"]["explainerId"])


class QuietSession:
    def __init__(self) -> None:
        self.added: list[Any] = []

    def add(self, row: Any) -> None:
        self.added.append(row)

    async def commit(self) -> None:
        return None


class CountingPictures:
    def __init__(self) -> None:
        self.asked: list[str] = []

    async def picture(self, url: str) -> bytes:
        self.asked.append(url)
        return picture_bytes()


def client(
    user: User, *, bucket: FakeBucket | None = None, pictures: CountingPictures | None = None
) -> TestClient:
    app = create_app()
    session = QuietSession()

    async def quiet() -> AsyncIterator[QuietSession]:
        yield session

    async def tools() -> AsyncIterator[ExportTools]:
        yield ExportTools(
            objects=bucket or FakeBucket(),
            pictures=pictures or CountingPictures(),
            apa=apa_references,
            clock=lambda: NOW,
            builds=asyncio.Semaphore(EXPORT_BUILDS_AT_ONCE),
        )

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_session] = quiet
    app.dependency_overrides[export_tools] = tools
    return TestClient(app)


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "/api/lessons"),
        ("get", "/api/lessons"),
        ("get", f"/api/lessons/{PACK_ID}"),
        ("delete", f"/api/lessons/{PACK_ID}"),
        ("get", f"/api/lessons/{PACK_ID}/files/pptx"),
    ],
)
def test_a_student_cannot_build_list_open_or_download_a_lesson(
    monkeypatch: pytest.MonkeyPatch, method: str, path: str
) -> None:
    async def never(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("a student's request reached the lesson store")

    for name in ("build_lesson", "lesson_list", "lesson_of", "delete_lesson"):
        monkeypatch.setattr(lessons, name, never)
    body = learning(LESSON)["request"] if method == "post" else None
    answered = client(STUDENT).request(method.upper(), path, json=body)
    assert answered.status_code == 403


def test_a_professor_builds_the_pack_the_contract_shows(monkeypatch: pytest.MonkeyPatch) -> None:
    async def version(session: Any, explainer_id: uuid.UUID, user_id: uuid.UUID, number: int) -> Any:
        assert (user_id, number) == (PROFESSOR.id, 1)
        return first_version()

    async def every_claim_visible(session: Any, claim_ids: Any, **_kwargs: Any) -> tuple[dict, dict]:
        return dict.fromkeys(claim_ids), {}

    monkeypatch.setattr(lesson_packs, "explainer_version", version)
    monkeypatch.setattr(knowledge_view, "claims_by_id", every_claim_visible)
    answered = client(PROFESSOR).post("/api/lessons", json=learning(LESSON)["request"])
    assert answered.status_code == 201
    expected = learning(LESSON)["pack"]
    shown = answered.json()
    assert {key: shown[key] for key in expected if key not in ("id", "createdAt")} == {
        key: value for key, value in expected.items() if key not in ("id", "createdAt")
    }


@pytest.mark.parametrize(
    ("refusal", "status"),
    [
        (UnknownExplainer(EXPLAINER_ID), 404),
        (LessonNotBuildable("Choose finished sections of this explainer."), 422),
    ],
)
def test_a_lesson_of_another_s_explainer_or_an_unfinished_section_is_refused(
    monkeypatch: pytest.MonkeyPatch, refusal: Exception, status: int
) -> None:
    async def build(session: Any, user_id: uuid.UUID, request: Any, *, now: datetime) -> Any:
        raise refusal

    monkeypatch.setattr(lessons, "build_lesson", build)
    answered = client(PROFESSOR).post("/api/lessons", json=learning(LESSON)["request"])
    assert answered.status_code == status


def test_a_lesson_file_is_filed_once_and_answered_as_a_short_lived_link(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def own(session: Any, user_id: uuid.UUID, pack_id: uuid.UUID) -> Any:
        return golden_pack() if (user_id, pack_id) == (PROFESSOR.id, PACK_ID) else None

    async def no_dates(session: Any, cited: Any) -> dict[str, date]:
        return {}

    monkeypatch.setattr(lessons, "lesson_of", own)
    monkeypatch.setattr(export_deps, "accessed_dates", no_dates)
    bucket, pictures = FakeBucket(), CountingPictures()
    http = client(PROFESSOR, bucket=bucket, pictures=pictures)
    first = http.get(f"/api/lessons/{PACK_ID}/files/pptx")
    again = http.get(f"/api/lessons/{PACK_ID}/files/pptx")
    assert first.status_code == again.status_code == 200 and first.json() == again.json()
    link = first.json()
    assert link["format"] == "pptx" and link["fileName"].startswith(
        "KalaVigyan_Lesson_2026-11-18_Kutch-Ajrakh_"
    )
    assert link["url"].startswith("https://") and link["expiresAt"] == "2026-11-18T10:05:00Z"
    assert len(bucket.stored) == 1 and len(pictures.asked) == 1
    body, _type = next(iter(bucket.stored.values()))
    assert len(Presentation(BytesIO(body)).slides) == len(golden_pack().slides)
    assert http.get(f"/api/lessons/{PACK_ID}/files/docx").status_code == 422
    assert http.get(f"/api/lessons/{uuid.uuid4()}/files/pdf").status_code == 404


def test_any_reader_exports_their_own_explainer_and_its_citations(monkeypatch: pytest.MonkeyPatch) -> None:
    latest = ExplainerVersionDocument.model_validate(learning(VERSIONS)["latest"])

    async def version(session: Any, explainer_id: uuid.UUID, user_id: uuid.UUID, number: int) -> Any:
        if (explainer_id, user_id, number) != (EXPLAINER_ID, STUDENT.id, 2):
            raise UnknownExplainer(explainer_id)
        return latest

    async def seed_dates(session: Any, cited: Any) -> dict[str, date]:
        return {thing.id: date(2026, 10, 14) for thing in cited}

    monkeypatch.setattr(explainer_exports, "explainer_version", version)
    monkeypatch.setattr(export_deps, "accessed_dates", seed_dates)
    http = client(STUDENT)
    assert http.get(f"/api/explainers/{EXPLAINER_ID}/versions/2/citations").json() == learning(CITATIONS)
    bib = http.get(f"/api/explainers/{EXPLAINER_ID}/versions/2/citations/bib")
    assert bib.headers["content-type"] == "application/x-bibtex; charset=utf-8"
    assert bib.headers["content-disposition"].startswith(
        'attachment; filename="KalaVigyan_Explainer_2026-11-18_Kutch-Ajrakh_Why-Did-Water-Push-Ajrakh-Printers-From_Citations_v2.bib"'
    )
    assert bib.text.count("@") == 6
    pdf = http.get(f"/api/explainers/{EXPLAINER_ID}/versions/2/pdf").json()
    assert pdf["fileName"].endswith("_Report_v2.pdf") and pdf["format"] == "pdf"
    assert http.get(f"/api/explainers/{EXPLAINER_ID}/versions/1/pdf").status_code == 404
    assert http.get(f"/api/explainers/{EXPLAINER_ID}/versions/0/citations").status_code == 422
