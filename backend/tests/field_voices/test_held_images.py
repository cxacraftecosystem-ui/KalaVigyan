import uuid
from collections.abc import Iterator
from datetime import UTC, date, datetime
from typing import Any

import httpx
import pytest
from fastapi import FastAPI, HTTPException, status
from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from app.api.routes import field_voices_held
from app.core.db import get_session
from app.core.deps import get_current_user
from app.core.errors import InvalidInput
from app.models import AppSetting, FieldImage, User
from app.research.field_voices import (
    ARTISAN_IMAGES_HIDDEN,
    ARTISAN_IMAGES_SETTING,
    HeldImage,
    HeldImageList,
)
from app.research.page_revalidation import PageOwners
from app.retrieval.field_scope import held_images, shown_images
from app.services import app_settings, field_voices_held as held

ROW_ID = uuid.UUID("9b3b6f0e-0000-4000-8000-0000000000a1")


def compiled(*where: Any) -> Any:
    return select(FieldImage.id).where(*where).compile(dialect=postgresql.dialect())


def test_a_shown_image_is_never_artisan_linked_unless_the_setting_says_shown() -> None:
    statement = compiled(*shown_images())
    text = str(statement)
    assert '"FieldImage"."artisanLinked" IS false OR (EXISTS' in text
    assert '"AppSetting".key = %(key_1)s::VARCHAR AND "AppSetting".value = %(param_1)s::JSONB' in text
    assert (statement.params["key_1"], statement.params["param_1"]) == (ARTISAN_IMAGES_SETTING, "SHOWN")
    assert str(statement.binds["param_1"].type) == "JSONB"


def test_the_held_list_is_every_artisan_linked_image_still_stored() -> None:
    text = str(compiled(*held_images()))
    assert '"FieldImage"."artisanLinked" IS true' in text and '"FieldImage"."hiddenAt" IS NULL' in text
    assert "AppSetting" not in text


def test_artisan_images_are_hidden_until_a_master_admin_shows_them() -> None:
    assert app_settings.DEFAULTS[ARTISAN_IMAGES_SETTING] == ARTISAN_IMAGES_HIDDEN


def stored_row(**over: Any) -> FieldImage:
    values: dict[str, Any] = {
        "id": ROW_ID,
        "portal": "FIELD_REPOSITORY",
        "portalMediaId": "fr-img-9",
        "caption": "Ismail at home",
        "takenAt": datetime(2026, 3, 14, 20, 0, tzinfo=UTC),
        "artisanLinked": True,
        "context": {
            "crafts": [
                {"id": "fr-craft-1", "slug": "Kutch-Ajrakh", "code": None, "name": "Ajrakh Print of Kutch"}
            ],
            "groups": [{"kind": "PERSON", "key": "person:fr-art-1", "label": "Ismail Khatri"}],
        },
        "people": [{"id": "fr-art-1", "kind": "ARTISAN", "name": "Ismail Khatri"}],
        "credits": [{"personId": "fr-art-1", "as": "ARTISAN"}],
        "width": 1600,
        "height": 1200,
        "objectKey": "media/field-voices/abc/KalaVigyan_Field-Image.jpg",
    }
    values.update(over)
    return FieldImage(**values)


def test_a_held_image_names_what_it_shows_and_never_its_file() -> None:
    shown = held.held_image_of(stored_row())
    assert shown == HeldImage(
        id=ROW_ID,
        item_id="FIELD_REPOSITORY:fr-img-9",
        origin="FIELD_REPOSITORY",
        caption="Ismail at home",
        taken_on=date(2026, 3, 15),
        crafts=["Ajrakh Print of Kutch"],
        placements=["Ismail Khatri"],
        credited=["Ismail Khatri"],
        width=1600,
        height=1200,
    )
    dumped = shown.model_dump(mode="json", by_alias=True)
    assert not {"url", "imageUrl", "objectKey", "key"} & set(dumped)
    assert "media/" not in str(dumped)


class Found:
    def __init__(self, row: AppSetting | None) -> None:
        self.row = row

    def scalar_one_or_none(self) -> AppSetting | None:
        return self.row


class FakeSession:
    def __init__(self, setting: Any = None) -> None:
        self.setting = setting
        self.executed: list[Any] = []
        self.added: list[Any] = []
        self.committed = False

    async def execute(self, statement: Any) -> Found:
        self.executed.append(statement)
        if self.setting is None:
            return Found(None)
        return Found(AppSetting(key=ARTISAN_IMAGES_SETTING, value=self.setting))

    def add(self, row: Any) -> None:
        self.added.append(row)

    async def commit(self) -> None:
        self.committed = True


async def test_the_visibility_reads_hidden_when_unset_or_unknown() -> None:
    assert await held.artisan_image_visibility(FakeSession()) == "HIDDEN"
    assert await held.artisan_image_visibility(FakeSession("SHOWN")) == "SHOWN"
    assert await held.artisan_image_visibility(FakeSession("sometimes")) == "HIDDEN"


async def test_only_hidden_or_shown_can_be_set() -> None:
    with pytest.raises(InvalidInput):
        await held.set_artisan_image_visibility(FakeSession(), "PUBLIC", actor_id=None)


def person(role: str) -> User:
    return User(id=uuid.uuid4(), email=f"{role.lower()}@example.org", name="Asha Demo", role=role)


@pytest.fixture
def state() -> dict[str, Any]:
    return {}


def refreshing(state: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    async def held_crafts(session: Any) -> set[uuid.UUID]:
        return set(state.get("crafts", ()))

    async def owners(session: Any, craft_ids: Any) -> PageOwners:
        return PageOwners(crafts=tuple(sorted(str(each) for each in craft_ids)))

    async def refreshed(owners: PageOwners) -> bool:
        state.setdefault("refreshed", []).append(owners.crafts)
        return True

    monkeypatch.setattr(field_voices_held, "held_photo_crafts", held_crafts)
    monkeypatch.setattr(field_voices_held, "craft_owners", owners)
    monkeypatch.setattr(field_voices_held, "refresh_pages", refreshed)


@pytest.fixture
def app(state: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> Iterator[FastAPI]:
    built = FastAPI()
    built.include_router(field_voices_held.router, prefix="/api")

    async def session() -> Any:
        yield state["session"]

    def current() -> User:
        if state.get("user") is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not signed in")
        return state["user"]

    async def listed(session: Any, *, cursor: str | None) -> HeldImageList:
        if cursor == "bad":
            raise InvalidInput("Unknown cursor.")
        return HeldImageList(
            schema_version=1,
            visibility="HIDDEN",
            total=1,
            cursor=cursor,
            next_cursor=None,
            images=[held.held_image_of(stored_row())],
        )

    monkeypatch.setattr(field_voices_held, "held_image_list", listed)
    refreshing(state, monkeypatch)
    built.dependency_overrides[get_session] = session
    built.dependency_overrides[get_current_user] = current
    yield built


async def call(app: FastAPI, method: str, path: str, **options: Any) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, path, **options)


async def test_the_held_list_is_for_admins_only(app: FastAPI, state: dict[str, Any]) -> None:
    state["session"] = FakeSession()
    assert (await call(app, "GET", "/api/field-voices/held-images")).status_code == 401
    for role in ("STUDENT", "ARTISAN", "RESEARCHER", "PROFESSOR"):
        state["user"] = person(role)
        refused = await call(app, "GET", "/api/field-voices/held-images")
        assert (refused.status_code, refused.json()) == (
            403,
            {"detail": "Held field images are for admins."},
        ), role
    for role in ("ADMIN", "MASTER_ADMIN"):
        state["user"] = person(role)
        shown = await call(app, "GET", "/api/field-voices/held-images")
        assert shown.status_code == 200, role
        assert shown.headers["Cache-Control"] == "private, no-cache"
        body = shown.json()
        assert (body["visibility"], body["total"], body["images"][0]["itemId"]) == (
            "HIDDEN",
            1,
            "FIELD_REPOSITORY:fr-img-9",
        )
    assert (
        await call(app, "GET", "/api/field-voices/held-images", params={"cursor": "bad"})
    ).status_code == 400


async def test_only_a_master_admin_flips_the_setting(app: FastAPI, state: dict[str, Any]) -> None:
    state["session"] = FakeSession()
    for role in ("PROFESSOR", "ADMIN"):
        state["user"] = person(role)
        refused = await call(
            app, "PUT", "/api/field-voices/held-images/visibility", json={"visibility": "SHOWN"}
        )
        assert refused.status_code == 403, role
    assert state["session"].executed == [] and not state["session"].committed
    state["user"] = person("MASTER_ADMIN")
    assert (
        await call(app, "PUT", "/api/field-voices/held-images/visibility", json={"visibility": "PUBLIC"})
    ).status_code == 422
    flipped = await call(app, "PUT", "/api/field-voices/held-images/visibility", json={"visibility": "SHOWN"})
    assert (flipped.status_code, flipped.json()) == (200, {"visibility": "SHOWN"})
    session = state["session"]
    assert session.committed and len(session.executed) == 1
    written = session.executed[0].compile(dialect=postgresql.dialect())
    assert written.params["key"] == ARTISAN_IMAGES_SETTING and written.params["value"] == "SHOWN"
    assert [row.action for row in session.added] == ["field_voices.artisan_images"]


async def test_a_flip_refreshes_the_pages_of_every_craft_with_a_held_photograph(
    app: FastAPI, state: dict[str, Any]
) -> None:
    craft = uuid.UUID("5ca1ab1e-0000-4000-8000-0000000000c1")
    state["session"], state["user"], state["crafts"] = FakeSession(), person("MASTER_ADMIN"), {craft}
    flipped = await call(
        app, "PUT", "/api/field-voices/held-images/visibility", json={"visibility": "HIDDEN"}
    )
    assert flipped.status_code == 200
    assert state["refreshed"] == [(str(craft),)]
