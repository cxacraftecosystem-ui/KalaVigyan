import hashlib
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.routes import contributed_pictures as route
from app.core.db import get_session
from app.core.errors import ExternalFailure
from app.data.design_palette import THEMES
from app.main import create_app
from app.services import drawing_themes
from app.services.contributed_pictures import ShownPicture

PICTURE = uuid.UUID("5c0e0000-0000-4000-8000-000000000001")
PATH = f"/api/crafts/contributed/{PICTURE}"
BYTES = b"RIFF\x24\x00\x00\x00WEBPVP8 a contributed picture"
DIGEST = hashlib.sha256(BYTES).hexdigest()
KEY = "media/contributor/token/KalaVigyan_Contribution_2026-11-19_Picture.webp"


@dataclass
class Calls:
    made: list[str] = field(default_factory=list)


@dataclass
class Session:
    calls: Calls

    async def commit(self) -> None:
        self.calls.made.append("commit")


@dataclass
class Bucket:
    calls: Calls
    kept: dict[str, bytes]
    failure: Exception | None = None

    async def get(self, key: str) -> bytes | None:
        self.calls.made.append(f"bucket get {key}")
        if self.failure is not None:
            raise self.failure
        return self.kept.get(key)


def served(
    monkeypatch: pytest.MonkeyPatch,
    *,
    shown: bool = True,
    bucket: bool = True,
    stored: bool = True,
    failure: Exception | None = None,
    mime: str = "image/webp",
) -> tuple[TestClient, Calls]:
    calls = Calls()
    picture = ShownPicture(key=KEY, mime=mime, sha256=DIGEST)

    async def shown_picture(session: Any, contribution_id: uuid.UUID) -> ShownPicture | None:
        calls.made.append(f"query {contribution_id}")
        return picture if shown else None

    async def session() -> AsyncIterator[Session]:
        yield Session(calls)

    kept = Bucket(calls, {KEY: BYTES} if stored else {}, failure)
    monkeypatch.setattr(route, "shown_picture", shown_picture)
    monkeypatch.setattr(route, "media_bucket", lambda: kept if bucket else None)
    app = create_app()
    app.dependency_overrides[get_session] = session
    return TestClient(app), calls


def test_an_approved_picture_is_served_with_its_stored_type_and_the_field_photo_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    http, calls = served(monkeypatch)
    answer = http.get(PATH)
    assert answer.status_code == 200
    assert answer.content == BYTES
    assert answer.headers["content-type"] == "image/webp"
    assert answer.headers["cache-control"] == "private, max-age=300"
    assert answer.headers["etag"] == f'"{DIGEST}"'
    assert answer.headers["x-content-type-options"] == "nosniff"
    assert calls.made == [f"query {PICTURE}", "commit", f"bucket get {KEY}"]


def test_a_picture_the_reader_holds_is_not_read_again(monkeypatch: pytest.MonkeyPatch) -> None:
    http, calls = served(monkeypatch)
    answer = http.get(PATH, headers={"If-None-Match": f'"{DIGEST}"'})
    assert answer.status_code == 304
    assert answer.headers["cache-control"] == "private, max-age=300"
    assert not any(call.startswith("bucket") for call in calls.made)


@pytest.mark.parametrize(
    ("changes", "status"),
    [
        ({"shown": False}, 404),
        ({"stored": False}, 404),
        ({"bucket": False}, 503),
        ({"failure": ExternalFailure("s3 answered 500", kind="unavailable")}, 503),
    ],
    ids=["not an approved picture", "no stored file", "no media bucket", "the bucket fails"],
)
def test_anything_but_an_approved_stored_picture_is_refused(
    monkeypatch: pytest.MonkeyPatch, changes: dict[str, Any], status: int
) -> None:
    http, calls = served(monkeypatch, **changes)
    answer = http.get(PATH)
    assert answer.status_code == status
    if changes.get("shown") is False:
        assert not any(call.startswith("bucket") for call in calls.made)
    if status == 503:
        assert answer.json()["detail"] == route.NO_PICTURES


def test_a_contribution_is_named_by_its_uuid(monkeypatch: pytest.MonkeyPatch) -> None:
    http, calls = served(monkeypatch)
    assert http.get("/api/crafts/contributed/not-a-picture").status_code == 422
    assert calls.made == []


def themed_tag(theme: str, tokens: str) -> str:
    return hashlib.sha256(f"{DIGEST}:{theme}:{tokens}".encode()).hexdigest()


def test_an_svg_picture_is_tagged_per_theme_and_per_token_set(monkeypatch: pytest.MonkeyPatch) -> None:
    tokens = hashlib.sha256(drawing_themes.design_tokens().encode("utf-8")).hexdigest()
    assert drawing_themes.token_set_hash() == tokens
    assert drawing_themes.picture_version(DIGEST, "image/webp", "dark") == DIGEST
    tags = {theme: drawing_themes.picture_version(DIGEST, "image/svg+xml", theme) for theme in THEMES}
    assert tags == {theme: themed_tag(theme, tokens) for theme in THEMES}
    assert len(set(tags.values())) == len(THEMES)
    assert drawing_themes.picture_version(DIGEST, "image/svg+xml", None) == tags[THEMES[0]]
    http, calls = served(monkeypatch, mime="image/svg+xml")
    held = http.get(
        PATH, params={"theme": "dark"}, headers={"If-None-Match": f'"{themed_tag("dark", tokens)}"'}
    )
    assert held.status_code == 304
    assert not any(call.startswith("bucket") for call in calls.made)
    monkeypatch.setattr(drawing_themes, "token_set_hash", lambda: "a-changed-token-set")
    assert drawing_themes.picture_version(DIGEST, "image/svg+xml", "dark") == themed_tag(
        "dark", "a-changed-token-set"
    )
    assert drawing_themes.picture_version(DIGEST, "image/svg+xml", "dark") != tags["dark"]
