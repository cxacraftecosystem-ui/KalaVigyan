import base64
import io
import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from PIL import Image

from app.api import mcp_field_photo_tools
from app.api.mcp_tools import ToolContext, answer
from app.services import field_photo_thumbnails, page_preview_pictures
from app.services.craft_resolver import CraftIndexStore
from app.services.field_photo_scope import ServedPhoto
from app.services.field_photo_thumbnails import field_photo_thumbnails as thumbnails_of
from app.services.page_preview_links import UnknownPreview
from app.services.page_preview_pictures import OwnPicture, pass_field_photo
from tests.pictures import picture

from .test_field_photo_plates import BAGH, IMAGE, OTHER, cleared, offered

NOW = datetime(2026, 11, 28, 9, 0, tzinfo=UTC)
PASS = f"{'a' * 32}.1795000000.{'b' * 64}"
SITE = "https://k.example"
KEYS = {IMAGE: "media/field-voices/a/photo.jpg", OTHER: "media/field-voices/b/photo.jpg"}


class Photos:
    def __init__(self, stored: dict[str, bytes]) -> None:
        self.stored = stored
        self.asked: list[str] = []

    async def get(self, key: str) -> bytes | None:
        self.asked.append(key)
        return self.stored.get(key)


def serving(monkeypatch: pytest.MonkeyPatch, shown: set[uuid.UUID]) -> None:
    async def served(session: Any, image_id: uuid.UUID) -> ServedPhoto | None:
        return ServedPhoto(key=KEYS[image_id], mime="image/jpeg") if image_id in shown else None

    monkeypatch.setattr(field_photo_thumbnails, "served_photo", served)
    monkeypatch.setattr(page_preview_pictures, "served_photo", served)


async def listed(monkeypatch: pytest.MonkeyPatch, objects: Photos | None) -> dict[str, Any]:
    offered(monkeypatch, [cleared(IMAGE), cleared(OTHER)])

    async def subject(session: Any, kind: str, slug: str) -> Any:
        return BAGH

    monkeypatch.setattr(mcp_field_photo_tools, "subject_by_key", subject)
    monkeypatch.setattr(mcp_field_photo_tools, "media_bucket", lambda: objects)
    no_session: Any = None
    context = ToolContext(session=no_session, index=CraftIndexStore(), site=SITE)
    params = {"name": "list_field_photos", "arguments": {"craft_slug": "Bagh-Print"}}
    reply = await answer({"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": params}, context)
    assert reply is not None and reply["result"]["isError"] is False
    return reply["result"]


async def test_the_agent_sees_each_listed_photograph_as_a_thumbnail_captioned_with_its_label(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    serving(monkeypatch, {IMAGE, OTHER})
    objects = Photos({key: picture(1800, 2400, seed=3, kind="JPEG") for key in KEYS.values()})
    result = await listed(monkeypatch, objects)
    images = [item for item in result["content"] if item["type"] == "image"]
    captions = [item["text"] for item in result["content"][1:] if item["type"] == "text"]
    assert len(images) == 2 and all(item["mimeType"] == "image/jpeg" for item in images)
    assert captions == [
        f"{cleared(IMAGE).label}: Printing the first colour",
        f"{cleared(OTHER).label}: Printing the first colour",
    ]
    small = Image.open(io.BytesIO(base64.b64decode(images[0]["data"])))
    assert max(small.size) <= 320 and small.size[1] > small.size[0]
    photos = result["structuredContent"]["photos"]
    assert [photo["pictureUrl"] for photo in photos] == [
        f"{SITE}/api/field-voices/images/{IMAGE}",
        f"{SITE}/api/field-voices/images/{OTHER}",
    ]
    assert "2 of them are shown below as thumbnails" in result["structuredContent"]["message"]


async def test_a_photograph_whose_copy_cannot_be_read_is_listed_without_a_thumbnail_and_said_so(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    serving(monkeypatch, {IMAGE, OTHER})
    objects = Photos({KEYS[IMAGE]: picture(1800, 2400, seed=3, kind="JPEG")})
    result = await listed(monkeypatch, objects)
    assert [item["type"] for item in result["content"]] == ["text", "text", "image"]
    message = result["structuredContent"]["message"]
    assert "1 of them are shown below" in message and "1 could not be shown as thumbnails" in message
    assert len(result["structuredContent"]["photos"]) == 2


async def test_without_the_media_bucket_no_photograph_is_read_and_each_opens_at_its_address(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    serving(monkeypatch, {IMAGE, OTHER})
    result = await listed(monkeypatch, None)
    assert [item["type"] for item in result["content"]] == ["text"]
    assert "2 could not be shown as thumbnails just now" in result["structuredContent"]["message"]


async def test_a_photograph_no_longer_shown_gets_no_thumbnail_and_its_copy_is_never_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    serving(monkeypatch, {IMAGE})
    objects = Photos({key: picture(600, 800, seed=5, kind="JPEG") for key in KEYS.values()})
    no_session: Any = None
    made = await thumbnails_of(no_session, [cleared(IMAGE), cleared(OTHER)], objects)
    assert [shown.label for shown in made] == [cleared(IMAGE).label]
    assert objects.asked == [KEYS[IMAGE]]


def previewing(monkeypatch: pytest.MonkeyPatch, document: dict[str, Any] | None) -> None:
    class Row:
        def __init__(self, held: dict[str, Any]) -> None:
            self.document = held

    async def passed(session: Any, render_pass: str, *, now: Any) -> Row:
        if document is None or render_pass != PASS:
            raise UnknownPreview("unknown")
        return Row(document)

    monkeypatch.setattr(page_preview_pictures, "passed_preview", passed)


def named(*images: uuid.UUID) -> dict[str, Any]:
    specs = {
        f"bagh-print/pictures/field-{image.hex[:12]}": {
            "picture": {"src": f"/api/field-voices/images/{image}"}
        }
        for image in images
    }
    return {"specs": specs}


async def test_the_renderer_s_pass_reads_a_shown_photograph_its_preview_places(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    serving(monkeypatch, {IMAGE, OTHER})
    previewing(monkeypatch, named(IMAGE))
    no_session: Any = None
    found = await pass_field_photo(no_session, PASS, IMAGE, now=NOW)
    assert found == OwnPicture(key=KEYS[IMAGE], mime="image/jpeg")


async def test_the_pass_reads_no_photograph_its_preview_leaves_out_one_hidden_since_or_another_s_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    serving(monkeypatch, {IMAGE})
    previewing(monkeypatch, named(IMAGE, OTHER))
    no_session: Any = None
    assert await pass_field_photo(no_session, PASS, OTHER, now=NOW) is None
    assert await pass_field_photo(no_session, PASS, uuid.uuid4(), now=NOW) is None
    assert await pass_field_photo(no_session, f"{'c' * 32}.1795000000.{'d' * 64}", IMAGE, now=NOW) is None
    previewing(monkeypatch, named(OTHER))
    assert await pass_field_photo(no_session, PASS, IMAGE, now=NOW) is None
