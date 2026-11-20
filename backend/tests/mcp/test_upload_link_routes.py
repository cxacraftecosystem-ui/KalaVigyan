import json
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.routes import upload_links as route
from app.core.db import get_session
from app.core.deps import get_current_user
from app.main import create_app
from app.models import ImageContribution, User
from app.research.image_contributions import ImageContributionView
from app.research.upload_links import SlotCraft, SlotFact, UploadLinkView
from app.services import image_contributions as images, upload_links as links

LINK = "kvup_pg_link-token"
SLOT = "kvup_sl_slot-token"
NOW = datetime(2026, 11, 19, 12, tzinfo=UTC)
FACT = uuid.UUID(int=21)
MADE = ImageContribution(id=uuid.UUID(int=77))
DECLARATION = {
    "origin": "PHOTOGRAPH",
    "caption": "A printer lifts the block",
    "altText": "Hands lifting a carved block from red cloth",
    "rightsConfirmed": True,
    "termsVersion": "2026-11-19",
}
VIEW = UploadLinkView(
    state="OPEN",
    craft=SlotCraft(slug="Kutch-Ajrakh", name="Kutch Ajrakh"),
    stage=None,
    material=None,
    slot=None,
    task_key=None,
    facts=[SlotFact(id=FACT, text="Alum binds alizarin to cotton.")],
    expires_at=NOW,
    contribution_id=None,
)


@dataclass
class Session:
    ended: list[str] = field(default_factory=list)

    async def commit(self) -> None:
        self.ended.append("commit")

    async def rollback(self) -> None:
        self.ended.append("rollback")


def client(role: str | None, session: Session) -> TestClient:
    app = create_app()
    if role is not None:
        user = User(id=uuid.UUID(int=41), name="Meera Rao", email="meera@example.org", role=role)
        app.dependency_overrides[get_current_user] = lambda: user

    async def opened() -> AsyncIterator[Any]:
        yield session

    app.dependency_overrides[get_session] = opened
    return TestClient(app)


def shown(monkeypatch: pytest.MonkeyPatch, bucket: Any = "bucket") -> None:
    async def views(session: Any, rows: list[ImageContribution], *, objects: Any, now: datetime) -> list[Any]:
        return [contribution_view(row.id) for row in rows]

    monkeypatch.setattr(route, "media_bucket", lambda: bucket)
    monkeypatch.setattr(images, "views", views)


def contribution_view(key: uuid.UUID) -> ImageContributionView:
    return ImageContributionView.model_validate(
        {
            "id": str(key),
            "craftSlug": "Kutch-Ajrakh",
            "craftName": "Kutch Ajrakh",
            "stageId": None,
            "materialId": None,
            "slot": None,
            "taskKey": None,
            "claimIds": [str(FACT)],
            "label": "Photograph",
            "generator": None,
            "prompt": None,
            "status": "PENDING",
            "aiMarked": False,
            "mime": "image/png",
            "width": 800,
            "height": 600,
            "fileUrl": None,
            "screen": None,
            "createdAt": "2026-11-19T12:00:00Z",
            "reviewedAt": None,
            "reviewNote": None,
        }
        | {key: value for key, value in DECLARATION.items() if key in {"origin", "caption", "altText"}}
    )


def answering(monkeypatch: pytest.MonkeyPatch, name: str, outcome: Any) -> list[tuple[Any, ...]]:
    seen: list[tuple[Any, ...]] = []

    async def step(*args: Any, **kwargs: Any) -> Any:
        seen.append(args)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(links, name, step)
    return seen


def form(declaration: str, picture: bytes = b"png-bytes") -> dict[str, Any]:
    return {
        "declaration": (None, declaration, "application/json"),
        "picture": ("p.png", picture, "image/png"),
    }


def test_the_owner_reads_the_link_privately(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = answering(monkeypatch, "link_view", VIEW)
    response = client("RESEARCHER", Session()).get(f"/api/upload-links/{LINK}")
    assert response.status_code == 200 and response.headers["cache-control"] == "private, no-cache"
    body = response.json()
    assert (body["state"], body["craft"]["name"], body["facts"][0]["id"]) == (
        "OPEN",
        "Kutch Ajrakh",
        str(FACT),
    )
    ((_, _, token),) = seen
    assert token == LINK


@pytest.mark.parametrize(
    ("refusal", "status", "says"),
    [
        (links.UnknownLink(LINK), 404, "No upload link of yours has that address."),
        (links.LinkGone(links.EXPIRED_DETAIL), 410, links.EXPIRED_DETAIL),
        (links.LinkGone(links.USED_DETAIL), 410, links.USED_DETAIL),
    ],
)
def test_an_unknown_used_or_expired_link_says_so(
    monkeypatch: pytest.MonkeyPatch, refusal: Exception, status: int, says: str
) -> None:
    shown(monkeypatch)
    answering(monkeypatch, "fill_by_link", refusal)
    session = Session()
    response = client("RESEARCHER", session).post(
        f"/api/upload-links/{LINK}/picture", files=form(json.dumps(DECLARATION))
    )
    assert (response.status_code, response.json()["detail"], session.ended) == (status, says, ["rollback"])


def test_a_student_cannot_open_an_upload_link() -> None:
    assert client("STUDENT", Session()).get(f"/api/upload-links/{LINK}").status_code == 403


def test_a_picture_through_the_link_is_declared_sent_and_committed(monkeypatch: pytest.MonkeyPatch) -> None:
    shown(monkeypatch)
    seen = answering(monkeypatch, "fill_by_link", MADE)
    session = Session()
    response = client("RESEARCHER", session).post(
        f"/api/upload-links/{LINK}/picture", files=form(json.dumps(DECLARATION))
    )
    assert response.status_code == 201 and response.json()["id"] == str(MADE.id)
    ((_, _, token, picture),) = seen
    assert (token, picture.declaration.caption, picture.data) == (LINK, DECLARATION["caption"], b"png-bytes")
    assert session.ended == ["commit"]


@pytest.mark.parametrize(
    ("declaration", "says"),
    [
        ("{not json", "The declaration is not a valid picture declaration."),
        (
            json.dumps(DECLARATION | {"rightsConfirmed": False}),
            "The declaration is not a valid picture declaration.",
        ),
    ],
)
def test_a_declaration_that_does_not_parse_is_refused_before_the_link_is_read(
    monkeypatch: pytest.MonkeyPatch, declaration: str, says: str
) -> None:
    shown(monkeypatch)
    seen = answering(monkeypatch, "fill_by_link", MADE)
    response = client("RESEARCHER", Session()).post(
        f"/api/upload-links/{LINK}/picture", files=form(declaration)
    )
    assert (response.status_code, response.json()["detail"], seen) == (422, says, [])


def test_without_a_media_bucket_no_picture_is_taken(monkeypatch: pytest.MonkeyPatch) -> None:
    shown(monkeypatch, bucket=None)
    seen = answering(monkeypatch, "fill_by_link", MADE)
    response = client("RESEARCHER", Session()).post(
        f"/api/upload-links/{LINK}/picture", files=form(json.dumps(DECLARATION))
    )
    assert (response.status_code, seen) == (503, [])


def test_a_used_link_is_renewed_as_a_new_link_for_the_same_slot(monkeypatch: pytest.MonkeyPatch) -> None:
    issued = links.IssuedLink("kvup_pg_new", None, NOW, VIEW.craft, None, list(VIEW.facts))
    answering(monkeypatch, "renew_link", issued)
    monkeypatch.setattr(route.get_settings(), "public_web_url", "https://kalavigyan.example")
    session = Session()
    response = client("RESEARCHER", session).post(f"/api/upload-links/{LINK}/renew")
    assert response.status_code == 201 and session.ended == ["commit"]
    assert response.json() == {
        "token": "kvup_pg_new",
        "link": "https://kalavigyan.example/contributions/pictures/upload?link=kvup_pg_new",
        "expiresAt": "2026-11-19T12:00:00Z",
    }


def test_an_open_link_is_not_renewed(monkeypatch: pytest.MonkeyPatch) -> None:
    answering(monkeypatch, "renew_link", links.LinkRefused(links.STILL_OPEN))
    response = client("RESEARCHER", Session()).post(f"/api/upload-links/{LINK}/renew")
    assert (response.status_code, response.json()["detail"]) == (409, links.STILL_OPEN)


def test_the_presigned_slot_takes_the_bytes_without_a_session(monkeypatch: pytest.MonkeyPatch) -> None:
    shown(monkeypatch)
    seen = answering(monkeypatch, "fill_slot", MADE)
    session = Session()
    response = client(None, session).put(f"/api/upload-links/slots/{SLOT}", content=b"\x89PNG-bytes")
    assert response.status_code == 200 and response.json()["id"] == str(MADE.id)
    ((_, token, data),) = seen
    assert (token, data, session.ended) == (SLOT, b"\x89PNG-bytes", ["commit"])


def test_a_used_slot_or_an_oversized_file_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    shown(monkeypatch)
    answering(monkeypatch, "fill_slot", links.LinkGone(links.USED_DETAIL))
    anonymous = client(None, Session())
    assert anonymous.put(f"/api/upload-links/slots/{SLOT}", content=b"png").status_code == 410
    too_large = anonymous.put(
        f"/api/upload-links/slots/{SLOT}",
        content=b"png",
        headers={"content-length": str(10 * 1024 * 1024 + 1)},
    )
    assert too_large.status_code == 413
