import uuid
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api import export_deps
from app.api.export_deps import export_tools
from app.api.routes import explainers, lessons, shared
from app.core.db import get_session
from app.core.http_cache import PRIVATE_NO_CACHE, PUBLIC_READ_CACHE
from app.main import create_app
from app.models import User
from app.research.explainer import Explainer, explainer_blocks
from app.research.explainer_versions import ExplainerVersionDocument
from app.research.share_links import ShareLink
from app.services import knowledge_view, share_links
from app.services.apa_references import apa_references
from app.services.explainer_history import UnknownExplainer
from app.services.explainer_payload import stored_payload
from app.services.export_files import ExportTools
from app.services.knowledge_view import ClaimView
from app.services.public_explainer import public_explainer

from ..contracts.learning_golden import CITATIONS, VERSIONS, learning
from ..readers import sign_in_as
from .lesson_fixtures import FakeBucket, first_version, golden_pack, picture_bytes

NOW = datetime(2026, 11, 18, 10, 0, tzinfo=UTC)
TOKEN = "k7Qm2vX9pL4sT8wB1nR6yC3dF5gH0jZa"
ASKER = User(id=uuid.UUID(int=21), name="Meera Iyer", email="meera@example.org", role="RESEARCHER")
PROFESSOR = User(id=uuid.UUID(int=22), name="Asha Mehta", email="asha@example.org", role="PROFESSOR")
STUDENT = User(id=uuid.UUID(int=23), name="Ravi Shah", email="ravi@example.org", role="STUDENT")
LATEST = ExplainerVersionDocument.model_validate(learning(VERSIONS)["latest"])
EXPLAINER_ID = LATEST.mark.explainer_id
SHARED_AT = datetime(2026, 11, 18, 9, 30, tzinfo=UTC)
SHARED = ShareLink(schema_version=1, shared=True, path=f"/shared/answers/{TOKEN}", shared_at=SHARED_AT)
LESSON_SHARED = SHARED.model_copy(update={"path": f"/shared/lessons/{TOKEN}"})
ANONYMOUS_ACLS = ("PUBLIC", "SIGNED_IN")
NEUTRAL_EXPORTS = "exports/00000000-0000-0000-0000-000000000000/"
READER_KEYS = ("email", "userId", "askedBy", "createdById", "ipHash", "passwordHash", "accessToken")


class Pictures:
    async def picture(self, url: str) -> bytes:
        return picture_bytes()


class QuietSession:
    async def commit(self) -> None:
        return None


class OneRow:
    def __init__(self, row: Any) -> None:
        self.row = row

    def first(self) -> Any:
        return self.row


class RowSession:
    def __init__(self, row: Any) -> None:
        self.row = row

    async def execute(self, statement: Any) -> OneRow:
        return OneRow(self.row)


def client(reader: User | None, *, bucket: FakeBucket | None = None) -> TestClient:
    app = create_app()

    async def no_session() -> AsyncIterator[QuietSession]:
        yield QuietSession()

    async def tools() -> AsyncIterator[ExportTools]:
        yield ExportTools(
            objects=bucket or FakeBucket(), pictures=Pictures(), apa=apa_references, clock=lambda: NOW
        )

    app.dependency_overrides[get_session] = no_session
    app.dependency_overrides[export_tools] = tools
    if reader is not None:
        sign_in_as(app, lambda: reader)
    return TestClient(app)


def keys_in(body: Any) -> set[str]:
    if isinstance(body, dict):
        return set(body) | {key for value in body.values() for key in keys_in(value)}
    if isinstance(body, list):
        return {key for value in body for key in keys_in(value)}
    return set()


def cited_pairs(explainer: Explainer) -> set[tuple[str, str]]:
    return {(c.claim_id, c.source_id) for block in explainer_blocks(explainer) for c in block.citations()}


def cited_keys(explainer: Explainer) -> set[tuple[str, str, str | None]]:
    return {
        (c.claim_id, c.source_id, c.quote) for block in explainer_blocks(explainer) for c in block.citations()
    }


def readable_only(keys: set[tuple[str, str, str | None]], asked: list[tuple[str, ...]]) -> Any:
    async def claims_by_id(session: Any, claim_ids: Any, *, acls: Any) -> tuple[dict, dict]:
        asked.append(tuple(acls))
        views: dict[uuid.UUID, ClaimView] = {}
        for claim, source, quote in sorted(keys, key=str):
            view = views.setdefault(
                uuid.UUID(claim), ClaimView(uuid.UUID(claim), "a stored claim", "PROVISIONAL", "", None)
            )
            view.citations.append({"claimId": claim, "sourceId": source, "quote": quote})
        return {key: views[key] for key in claim_ids if key in views}, {}

    return claims_by_id


@pytest.fixture
def shared_latest(monkeypatch: pytest.MonkeyPatch) -> None:
    async def found(session: Any, token: str) -> ExplainerVersionDocument | None:
        return LATEST if token == TOKEN else None

    monkeypatch.setattr(shared, "shared_answer", found)


@pytest.mark.usefixtures("shared_latest")
def test_anyone_reads_a_shared_answer_and_never_its_asker() -> None:
    anonymous = client(None).get(f"/api/shared/answers/{TOKEN}")
    signed_in = client(STUDENT).get(f"/api/shared/answers/{TOKEN}")
    assert anonymous.status_code == signed_in.status_code == 200
    assert anonymous.json() == signed_in.json() == learning(VERSIONS)["latest"]
    assert str(ASKER.id) not in anonymous.text and ASKER.email not in anonymous.text
    assert not set(READER_KEYS) & keys_in(anonymous.json())
    assert anonymous.headers["cache-control"] == PUBLIC_READ_CACHE
    assert signed_in.headers["cache-control"] == PRIVATE_NO_CACHE
    assert "Authorization" in anonymous.headers["vary"]
    again = client(None).get(
        f"/api/shared/answers/{TOKEN}", headers={"If-None-Match": anonymous.headers["etag"]}
    )
    assert (again.status_code, again.content) == (304, b"")


@pytest.mark.usefixtures("shared_latest")
def test_an_unshared_token_is_404_and_a_malformed_one_422() -> None:
    reader = client(None)
    assert reader.get(f"/api/shared/answers/{TOKEN[::-1]}").status_code == 404
    assert reader.get("/api/shared/answers/short").status_code == 422
    assert reader.get(f"/api/shared/answers/{TOKEN[:-1]}!").status_code == 422


@pytest.mark.usefixtures("shared_latest")
def test_a_shared_answer_is_cited_exactly_as_its_asker_exports_it(monkeypatch: pytest.MonkeyPatch) -> None:
    async def seed_dates(session: Any, cited: Any) -> dict[str, date]:
        return {thing.id: date(2026, 10, 14) for thing in cited}

    monkeypatch.setattr(export_deps, "accessed_dates", seed_dates)
    reader = client(None)
    assert reader.get(f"/api/shared/answers/{TOKEN}/citations").json() == learning(CITATIONS)
    bib = reader.get(f"/api/shared/answers/{TOKEN}/citations/bib")
    assert bib.headers["content-disposition"].startswith(
        'attachment; filename="KalaVigyan_Explainer_2026-11-18_Kutch-Ajrakh_Why-Did-Water-Push-Ajrakh-Printers-From_Citations_v2.bib"'
    )
    assert bib.headers["cache-control"] == PUBLIC_READ_CACHE


@pytest.mark.usefixtures("shared_latest")
def test_shared_files_are_filed_under_no_reader_s_id(monkeypatch: pytest.MonkeyPatch) -> None:
    async def no_dates(session: Any, cited: Any) -> dict[str, date]:
        return {}

    async def shared_pack(session: Any, token: str) -> Any:
        return golden_pack() if token == TOKEN else None

    monkeypatch.setattr(export_deps, "accessed_dates", no_dates)
    monkeypatch.setattr(shared, "shared_lesson", shared_pack)
    bucket = FakeBucket()
    reader = client(None, bucket=bucket)
    pdf = reader.get(f"/api/shared/answers/{TOKEN}/pdf")
    slides = reader.get(f"/api/shared/lessons/{TOKEN}/files/pptx")
    assert pdf.status_code == slides.status_code == 200
    assert pdf.json()["fileName"].endswith("_Report_v2.pdf")
    assert pdf.headers["cache-control"] == slides.headers["cache-control"] == PRIVATE_NO_CACHE
    assert len(bucket.stored) == 2 and all(key.startswith(NEUTRAL_EXPORTS) for key in bucket.stored)
    assert reader.get(f"/api/shared/lessons/{TOKEN[::-1]}").status_code == 404


def test_the_asker_shares_only_their_own_version_and_only_what_can_be_public(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    refusals: dict[int, Exception] = {
        1: UnknownExplainer(EXPLAINER_ID),
        3: share_links.NothingPublic(f"explainer {EXPLAINER_ID} version 3"),
    }

    async def share(
        session: Any, user_id: uuid.UUID, explainer_id: uuid.UUID, version: int, *, now: datetime
    ) -> Any:
        assert user_id == ASKER.id
        if version in refusals:
            raise refusals[version]
        return SHARED

    monkeypatch.setattr(explainers, "share_answer", share)
    reader = client(ASKER)
    shared_link = reader.put(f"/api/explainers/{EXPLAINER_ID}/versions/2/share")
    assert shared_link.status_code == 200
    assert shared_link.json() == {
        "schemaVersion": 1,
        "shared": True,
        "path": f"/shared/answers/{TOKEN}",
        "sharedAt": "2026-11-18T09:30:00Z",
    }
    assert shared_link.headers["cache-control"] == PRIVATE_NO_CACHE
    assert reader.put(f"/api/explainers/{EXPLAINER_ID}/versions/1/share").status_code == 404
    nothing = reader.put(f"/api/explainers/{EXPLAINER_ID}/versions/3/share")
    assert (nothing.status_code, nothing.json()) == (422, {"detail": share_links.NOTHING_PUBLIC_DETAIL})


def test_only_a_lesson_builder_shares_a_lesson_and_only_their_own(monkeypatch: pytest.MonkeyPatch) -> None:
    pack_id = golden_pack().id

    async def share(session: Any, user_id: uuid.UUID, lesson_id: uuid.UUID, *, now: datetime) -> Any:
        return LESSON_SHARED if (user_id, lesson_id) == (PROFESSOR.id, pack_id) else None

    async def unshare(session: Any, user_id: uuid.UUID, lesson_id: uuid.UUID) -> bool:
        return (user_id, lesson_id) == (PROFESSOR.id, pack_id)

    monkeypatch.setattr(lessons, "share_lesson", share)
    monkeypatch.setattr(lessons, "unshare_lesson", unshare)
    assert client(PROFESSOR).put(f"/api/lessons/{pack_id}/share").json()["path"] == f"/shared/lessons/{TOKEN}"
    assert client(PROFESSOR).put(f"/api/lessons/{uuid.uuid4()}/share").status_code == 404
    assert client(PROFESSOR).delete(f"/api/lessons/{pack_id}/share").status_code == 204
    assert client(PROFESSOR).delete(f"/api/lessons/{uuid.uuid4()}/share").status_code == 404
    assert client(STUDENT).put(f"/api/lessons/{pack_id}/share").status_code == 403


async def test_a_public_explainer_keeps_what_an_anonymous_reader_may_quote(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    explainer = first_version().explainer
    asked: list[tuple[str, ...]] = []
    monkeypatch.setattr(knowledge_view, "claims_by_id", readable_only(cited_keys(explainer), asked))
    assert await public_explainer(None, explainer) == explainer
    assert asked == [ANONYMOUS_ACLS]


async def test_a_closed_quote_leaves_the_public_explainer_and_nothing_readable_leaves_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    explainer = first_version().explainer
    prose = next(block for section in explainer.sections for block in section.blocks if block.kind == "prose")
    closed = (prose.sentences[0].citations[0].claim_id, prose.sentences[0].citations[0].source_id)
    readable = {key for key in cited_keys(explainer) if key[:2] != closed}
    monkeypatch.setattr(knowledge_view, "claims_by_id", readable_only(readable, []))
    shown = await public_explainer(None, explainer)
    assert shown is not None
    assert closed not in cited_pairs(shown)
    assert prose.sentences[0].text not in shown.model_dump_json()
    monkeypatch.setattr(knowledge_view, "claims_by_id", readable_only(set(), []))
    assert await public_explainer(None, explainer) is None


async def test_a_closed_quote_leaves_even_when_its_fact_and_source_have_a_public_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    explainer = first_version().explainer
    sentence = next(
        sentence
        for section in explainer.sections
        for block in section.blocks
        if block.kind == "prose"
        for sentence in block.sentences
        if any(c.quote for c in sentence.citations)
    )
    quoted = next(c for c in sentence.citations if c.quote)
    public_twin = (quoted.claim_id, quoted.source_id, "A shorter public quote of the same page.")
    readable = (cited_keys(explainer) - {(quoted.claim_id, quoted.source_id, quoted.quote)}) | {public_twin}
    monkeypatch.setattr(knowledge_view, "claims_by_id", readable_only(readable, []))
    shown = await public_explainer(None, explainer)
    assert shown is not None
    assert sentence.text not in shown.model_dump_json()


async def test_a_shared_lesson_is_its_professor_s_pack_when_everything_is_public(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    version = first_version()

    async def as_stored(session: Any, document: ExplainerVersionDocument) -> ExplainerVersionDocument:
        return document

    monkeypatch.setattr(share_links, "shown_version", as_stored)
    monkeypatch.setattr(knowledge_view, "claims_by_id", readable_only(cited_keys(version.explainer), []))
    row = SimpleNamespace(id=version.explainer.answer_id, payload=stored_payload(version.explainer, None))
    assert await share_links.public_lesson(RowSession(row), golden_pack()) == golden_pack()
    monkeypatch.setattr(knowledge_view, "claims_by_id", readable_only(set(), []))
    assert await share_links.public_lesson(RowSession(row), golden_pack()) is None
    assert await share_links.public_lesson(RowSession(None), golden_pack()) is None


def test_a_former_lesson_builder_still_reads_and_stops_their_own_share(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pack_id = golden_pack().id
    owned = (STUDENT.id, pack_id)

    async def share_of(session: Any, user_id: uuid.UUID, lesson_id: uuid.UUID) -> Any:
        return LESSON_SHARED if (user_id, lesson_id) == owned else None

    async def unshare(session: Any, user_id: uuid.UUID, lesson_id: uuid.UUID) -> bool:
        return (user_id, lesson_id) == owned

    monkeypatch.setattr(lessons, "lesson_share", share_of)
    monkeypatch.setattr(lessons, "unshare_lesson", unshare)
    former = client(STUDENT)
    assert former.get(f"/api/lessons/{pack_id}/share").json()["path"] == f"/shared/lessons/{TOKEN}"
    assert former.delete(f"/api/lessons/{pack_id}/share").status_code == 204
    assert former.get(f"/api/lessons/{uuid.uuid4()}/share").status_code == 404
    assert former.delete(f"/api/lessons/{uuid.uuid4()}/share").status_code == 404
    assert former.put(f"/api/lessons/{pack_id}/share").status_code == 403
