import uuid
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.api.routes import craft_media
from app.core.db import get_session
from app.main import create_app
from app.services.object_store import PresignedGet

ASSET = uuid.UUID("6f1c2a4e-8d3b-4c5a-9e7f-0a1b2c3d4e5f")
PAGE_KEY = f"media/craft/{'c' * 64}/KalaVigyan_Generated-Image_2026-11-16_1430_Media-Test_Image_Step-06.png"


class Bucket:
    def __init__(self) -> None:
        self.asked: list[tuple[str, str, int]] = []

    def presigned_get(self, key: str, *, disposition: str, seconds: int, now: datetime) -> PresignedGet:
        self.asked.append((key, disposition, seconds))
        return PresignedGet(
            url=f"https://bucket.example/{key}?X-Amz-Expires={seconds}",
            expires_at=now + timedelta(seconds=seconds),
        )


def client(monkeypatch: pytest.MonkeyPatch, *, key: str | None, bucket: Bucket | None) -> TestClient:
    async def page_key(session: object, asset_id: uuid.UUID) -> str | None:
        return key if asset_id == ASSET else None

    async def released(session: object) -> None:
        return None

    monkeypatch.setattr(craft_media, "page_media_key_of", page_key)
    monkeypatch.setattr(craft_media, "release_connection", released)
    monkeypatch.setattr(craft_media, "media_bucket", lambda: bucket)
    app = create_app()
    app.dependency_overrides[get_session] = lambda: None
    return TestClient(app, follow_redirects=False)


def test_a_shared_page_copy_answers_a_fifteen_minute_link(monkeypatch: pytest.MonkeyPatch) -> None:
    bucket = Bucket()
    response = client(monkeypatch, key=PAGE_KEY, bucket=bucket).get(f"/api/crafts/media/{ASSET}")
    assert response.status_code == 302
    assert response.headers["location"] == f"https://bucket.example/{PAGE_KEY}?X-Amz-Expires=900"
    assert bucket.asked[0][1].startswith("inline; filename=") and bucket.asked[0][2] == 900


def test_an_unshared_or_unknown_asset_is_404_and_no_bucket_is_503(monkeypatch: pytest.MonkeyPatch) -> None:
    assert client(monkeypatch, key=None, bucket=Bucket()).get(f"/api/crafts/media/{ASSET}").status_code == 404
    unknown = client(monkeypatch, key=PAGE_KEY, bucket=Bucket()).get(f"/api/crafts/media/{uuid.uuid4()}")
    assert unknown.status_code == 404
    assert client(monkeypatch, key=PAGE_KEY, bucket=None).get(f"/api/crafts/media/{ASSET}").status_code == 503
