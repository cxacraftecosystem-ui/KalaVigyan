import base64
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import pytest

from app.api import mcp_picture_tools
from app.api.mcp_picture_arguments import GivePictures
from app.api.mcp_tools import ToolContext, answer
from app.research.image_contributions_give import GivenPicture, GivenPictures
from app.research.image_intake_fetch import FetchedPicture
from app.research.image_screens import ScreenSummary, ScreenTools
from app.research.upload_links import SlotCraft
from app.services.upload_links_give import Giving

from .test_picture_uploads import DECLARATION, OWNER, WORDS, context, issuing

STAGE = uuid.UUID(int=5)
MADE = uuid.UUID(int=77)
RECORD = uuid.UUID(int=88)
PICTURE = b"\x89PNG\r\n\x1a\npicture-bytes"
ENCODED = base64.b64encode(PICTURE).decode("ascii")
FETCHED = b"fetched-bytes"
CONFIRMED = "Yes, I drew it myself and the Centre may publish it without my name."
REASON = "It may show an identity document, or a card with a face and a number."


@pytest.fixture
def given(monkeypatch: pytest.MonkeyPatch) -> list[Giving]:
    seen: list[Giving] = []

    async def give(session: Any, user: Any, giving: Giving, *, handing: Any) -> GivenPictures:
        seen.append(giving)
        return GivenPictures(
            craft=SlotCraft(slug="Kutch-Ajrakh", name="Kutch Ajrakh"),
            declaration_id=RECORD,
            given=1,
            refused=0,
            pictures=[
                GivenPicture(
                    position=1,
                    contribution_id=MADE,
                    status="PENDING",
                    label="Drawing",
                    received="image/heic",
                    mime="image/webp",
                    width=900,
                    height=700,
                    screen=ScreenSummary(verdict="FLAGGED", flags=["ID_DOCUMENT"], reasons=[REASON]),
                )
            ],
            next_step="A picture waits for an Admin's review.",
        )

    @asynccontextmanager
    async def fetcher() -> AsyncIterator[Any]:
        yield Fetcher()

    monkeypatch.setattr(mcp_picture_tools, "give_pictures", give)
    monkeypatch.setattr(mcp_picture_tools, "media_bucket", lambda: "bucket")
    monkeypatch.setattr(mcp_picture_tools, "picture_fetcher", fetcher)
    monkeypatch.setattr(mcp_picture_tools, "picture_screen_tools", lambda: ScreenTools(vision=None))
    return seen


class Fetcher:
    urls: list[str] = []

    async def fetch_picture(self, url: str) -> FetchedPicture:
        Fetcher.urls.append(url)
        return FetchedPicture(url=url, final_url=url, content_type="image/png", data=FETCHED)


async def call(arguments: dict[str, Any], tool_context: ToolContext) -> dict[str, Any]:
    message = {
        "jsonrpc": "2.0",
        "id": 9,
        "method": "tools/call",
        "params": {"name": "give_pictures", "arguments": arguments},
    }
    reply = await answer(message, tool_context)
    assert reply is not None and "result" in reply, reply
    return reply["result"]


def one(**changes: Any) -> dict[str, Any]:
    picture = {"stage_id": str(STAGE), "image_base64": ENCODED, **WORDS} | changes
    return {
        "craft_slug": "Kutch-Ajrakh",
        "declaration": DECLARATION,
        "confirmation": CONFIRMED,
        "pictures": [{key: value for key, value in picture.items() if value is not None}],
    }


async def test_a_picture_in_the_call_is_given_under_the_confirmed_declaration(given: list[Giving]) -> None:
    tool_context = context()
    result = await call(one(), tool_context)
    shown = result["structuredContent"]
    assert (shown["declarationId"], shown["given"], shown["pictures"][0]["screen"]["reasons"]) == (
        str(RECORD),
        1,
        [REASON],
    )
    assert shown["uploads"] == [] and shown["nextStep"] == "A picture waits for an Admin's review."
    (giving,) = given
    (file,) = giving.files
    assert (giving.craft_slug, giving.confirmation, giving.shared.origin, giving.shared.generator) == (
        "Kutch-Ajrakh",
        CONFIRMED,
        "DRAWING",
        None,
    )
    assert (file.position, file.data, file.refused) == (1, PICTURE, None)
    assert (file.picture.stage_id, file.picture.caption, file.picture.alt_text) == (
        STAGE,
        WORDS["caption"],
        WORDS["alt_text"],
    )
    assert tool_context.session.ended == ["commit"]  # type: ignore[attr-defined]


async def test_a_picture_link_is_fetched_by_the_server(given: list[Giving]) -> None:
    Fetcher.urls.clear()
    link = "https://files.example.org/made/vat.png"
    await call(one(image_base64=None, image_url=link), context())
    assert Fetcher.urls == [link]
    assert given[0].files[0].data == FETCHED


@pytest.mark.parametrize(
    ("changes", "says"),
    [
        ({"image_url": "https://files.example.org/a.png"}, "exactly one of them"),
        ({"image_base64": None}, "exactly one of them"),
        ({"confirmation": "y"}, "confirmation"),
        ({"declaration": DECLARATION | {"rights_confirmed": False}}, "declaration"),
        ({"stage_id": str(STAGE), "slot": "MASTHEAD"}, "one stage, one material or one picture slot"),
        ({"image_url": "http://files.example.org/a.png", "image_base64": None}, "image_url"),
        ({"caption": None}, "caption and alt_text"),
        ({"declaration": None}, "need the declaration the person confirmed"),
    ],
)
async def test_a_picture_needs_one_source_its_words_the_person_s_words_and_a_whole_declaration(
    given: list[Giving], changes: dict[str, Any], says: str
) -> None:
    shared = ("confirmation", "declaration")
    top = {key: value for key, value in changes.items() if key in shared}
    arguments = one(**{key: value for key, value in changes.items() if key not in shared}) | top
    arguments = {key: value for key, value in arguments.items() if value is not None}
    result = await call(arguments, context())
    assert result["isError"] is True and says in result["content"][0]["text"], result
    assert given == []


async def test_a_spent_upload_limit_refuses_the_picture_without_reading_it(
    given: list[Giving], monkeypatch: pytest.MonkeyPatch
) -> None:
    async def spent(kind: str, user: Any) -> Any:
        return type("Spent", (), {"message": "spent"})()

    monkeypatch.setattr(mcp_picture_tools, "spent_limit", spent)
    await call(one(), context())
    (file,) = given[0].files
    assert (file.data, file.refused) == (None, "spent")


async def test_given_and_uploaded_pictures_share_one_declaration_and_keep_their_positions(
    given: list[Giving], monkeypatch: pytest.MonkeyPatch
) -> None:
    seen = issuing(monkeypatch)
    pictures = [
        {"caption": "The vat", "alt_text": "A clay vat", "image_base64": ENCODED, "stage_id": str(STAGE)},
        {"upload": True, "claim_ids": [str(uuid.UUID(int=21))], **WORDS},
        {
            "caption": "The block",
            "alt_text": "A carved block",
            "image_url": "https://files.example.org/b.png",
        },
    ]
    arguments = {
        "craft_slug": "Kutch-Ajrakh",
        "declaration": {"origin": "PHOTOGRAPH", "rights_confirmed": True, "terms_version": "2026-11-19"},
        "confirmation": CONFIRMED,
        "pictures": pictures,
    }
    shown = (await call(arguments, context()))["structuredContent"]
    first, third = given[0].files
    assert (first.position, first.data, first.picture.caption) == (1, PICTURE, "The vat")
    assert (third.position, third.data, third.picture.caption) == (3, FETCHED, "The block")
    ((_, declaration),) = seen
    assert declaration is not None and (declaration.origin, declaration.caption) == (
        "PHOTOGRAPH",
        WORDS["caption"],
    )
    assert [place["position"] for place in shown["uploads"]] == [2]
    assert shown["nextStep"].startswith("A picture waits") and "upload_url" in shown["nextStep"]


def test_the_pictures_sent_in_one_call_are_capped_together() -> None:
    big = "A" * 6_000_000
    pictures = [{"caption": "The vat", "alt_text": "A clay vat", "image_base64": big} for _ in range(3)]
    with pytest.raises(ValueError, match="12 MB together"):
        GivePictures.model_validate(
            {
                "craft_slug": "Kutch-Ajrakh",
                "declaration": {
                    "origin": "PHOTOGRAPH",
                    "rights_confirmed": True,
                    "terms_version": "2026-11-19",
                },
                "confirmation": CONFIRMED,
                "pictures": pictures,
            }
        )


async def test_the_description_asks_for_the_person_s_own_words_and_names_the_screens() -> None:
    reply = await answer({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, context(None))
    assert reply is not None
    (listed,) = [tool for tool in reply["result"]["tools"] if tool["name"] == "give_pictures"]
    assert "Aadhaar" in listed["description"] and "never fill the declaration in" in listed["description"]
    picture = listed["inputSchema"]["$defs"]["GivenOrUploaded"]["properties"]
    assert {"image_url", "image_base64", "upload", "task_key", "alt_text"} <= set(picture)
    assert {"confirmation", "declaration", "pictures", "craft_slug"} <= set(
        listed["inputSchema"]["properties"]
    )


async def test_giving_a_picture_needs_a_signed_in_connection(given: list[Giving]) -> None:
    result = await call(one(), context(None))
    assert result["isError"] is True and "signed-in connection" in result["content"][0]["text"]
    assert OWNER.role == "RESEARCHER"
