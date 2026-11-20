import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest

from app.api import mcp_picture_tools
from app.api.mcp_tools import ToolContext, answer
from app.core.errors import InvalidInput
from app.core.mcp_scopes import CONTRIBUTE_SCOPE, READ_SCOPE
from app.models import User
from app.research.upload_links import SlotCraft, SlotDeclaration, SlotFact, SlotStage, UploadSlot
from app.services import upload_links
from app.services.craft_resolver import CraftIndexStore

SITE = "https://kalavigyan.example"
API = "https://api.kalavigyan.example"
EXPIRES = datetime(2026, 11, 19, 12, 30, tzinfo=UTC)
FACT = uuid.UUID(int=21)
STAGE = uuid.UUID(int=5)
LINK = "kvup_pg_link-token"
SLOT = "kvup_sl_slot-token"
DECLARATION = {"origin": "DRAWING", "rights_confirmed": True, "terms_version": "2026-11-19"}
WORDS = {
    "caption": "The resist paste on the block",
    "alt_text": "A drawing of a carved block coated in grey paste",
}
UPLOAD_TYPES = [
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/avif",
    "image/gif",
    "image/heic",
    "image/heif",
    "image/tiff",
    "image/bmp",
    "image/svg+xml",
]
OWNER = User(id=uuid.UUID(int=41), name="Meera Rao", email="meera@example.org", role="RESEARCHER")


class FakeSession:
    def __init__(self) -> None:
        self.ended: list[str] = []

    async def commit(self) -> None:
        self.ended.append("commit")

    async def rollback(self) -> None:
        self.ended.append("rollback")


def context(
    user: User | None = OWNER, scopes: frozenset[str] = frozenset({READ_SCOPE, CONTRIBUTE_SCOPE})
) -> ToolContext:
    return ToolContext(session=FakeSession(), index=CraftIndexStore(), site=SITE, user=user, scopes=scopes)  # type: ignore[arg-type]


def issuing(
    monkeypatch: pytest.MonkeyPatch, api: str | None = API
) -> list[tuple[UploadSlot, SlotDeclaration | None]]:
    seen: list[tuple[UploadSlot, SlotDeclaration | None]] = []

    async def start(
        session: Any, user: User, slot: UploadSlot, declaration: SlotDeclaration | None, *, now: datetime
    ) -> upload_links.IssuedLink:
        seen.append((slot, declaration))
        return upload_links.IssuedLink(
            link_token=LINK,
            slot_token=None if declaration is None else SLOT,
            expires_at=EXPIRES,
            craft=SlotCraft(slug="Kutch-Ajrakh", name="Kutch Ajrakh"),
            stage=SlotStage(id=STAGE, name="Printing the resist"),
            facts=[SlotFact(id=FACT, text="The resist paste holds lime and gum.")],
        )

    monkeypatch.setattr(upload_links, "start_upload", start)
    monkeypatch.setattr(
        mcp_picture_tools, "endpoints_or_none", lambda: None if api is None else SimpleNamespace(issuer=api)
    )
    return seen


def upload(**changes: Any) -> dict[str, Any]:
    return {"upload": True, "claim_ids": [str(FACT)]} | changes


async def call(arguments: dict[str, Any], tool_context: ToolContext) -> dict[str, Any]:
    message = {
        "jsonrpc": "2.0",
        "id": 5,
        "method": "tools/call",
        "params": {"name": "give_pictures", "arguments": {"craft_slug": "Kutch-Ajrakh"} | arguments},
    }
    reply = await answer(message, tool_context)
    assert reply is not None and "result" in reply, reply
    return reply["result"]


async def test_without_a_declaration_an_upload_returns_only_the_link_for_the_person(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = issuing(monkeypatch)
    tool_context = context()
    result = await call({"pictures": [upload(stage_id=str(STAGE))]}, tool_context)
    reply = result["structuredContent"]
    (place,) = reply["uploads"]
    shown = place["upload"]
    assert (place["position"], place["refused"], reply["given"], reply["refused"]) == (1, None, 0, 0)
    assert shown["link"] == f"{SITE}/contributions/pictures/upload?link={LINK}"
    assert (shown["uploadUrl"], shown["declared"], shown["expiresAt"]) == (
        None,
        False,
        "2026-11-19T12:30:00Z",
    )
    assert shown["nextStep"].startswith("Send the person the link") and reply["nextStep"] == shown["nextStep"]
    assert (shown["craft"]["slug"], shown["stage"]["name"], shown["facts"][0]["id"]) == (
        "Kutch-Ajrakh",
        "Printing the resist",
        str(FACT),
    )
    assert (shown["uploadMethod"], shown["uploadTypes"], shown["uploadMaxBytes"]) == (
        "PUT",
        UPLOAD_TYPES,
        10 * 1024 * 1024,
    )
    ((slot, declaration),) = seen
    assert (slot.craft_slug, slot.stage_id, slot.claim_ids, declaration) == (
        "Kutch-Ajrakh",
        STAGE,
        [FACT],
        None,
    )
    assert tool_context.session.ended == ["commit"]  # type: ignore[attr-defined]


async def test_a_confirmed_declaration_also_returns_a_presigned_slot_on_the_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = issuing(monkeypatch)
    result = await call({"declaration": DECLARATION, "pictures": [upload(**WORDS)]}, context())
    shown = result["structuredContent"]["uploads"][0]["upload"]
    assert shown["uploadUrl"] == f"{API}/api/upload-links/slots/{SLOT}"
    assert shown["declared"] is True and "PUT the picture's bytes to upload_url" in shown["nextStep"]
    ((_, declaration),) = seen
    assert declaration is not None and (declaration.origin, declaration.alt_text, declaration.caption) == (
        "DRAWING",
        WORDS["alt_text"],
        WORDS["caption"],
    )


async def test_without_a_configured_api_origin_the_link_is_the_only_way(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    issuing(monkeypatch, api=None)
    result = await call({"declaration": DECLARATION, "pictures": [upload(**WORDS)]}, context())
    assert result["structuredContent"]["uploads"][0]["upload"]["uploadUrl"] is None


@pytest.mark.parametrize(
    ("tool_context", "arguments", "says"),
    [
        (context(None), {}, "needs a signed-in connection"),
        (context(scopes=frozenset({READ_SCOPE})), {}, "needs the contribute scope"),
        (context(), {"pictures": [upload(claim_ids=[])]}, "names the facts it shows"),
        (
            context(),
            {"pictures": [upload(image_url="https://files.example.org/a.png")]},
            "exactly one of them",
        ),
        (context(), {"declaration": DECLARATION | {"rights_confirmed": False}}, "declaration"),
        (context(), {"pictures": []}, "pictures"),
    ],
)
async def test_it_needs_sign_in_the_contribute_scope_and_a_well_formed_slot(
    monkeypatch: pytest.MonkeyPatch, tool_context: ToolContext, arguments: dict[str, Any], says: str
) -> None:
    seen = issuing(monkeypatch)
    result = await call({"pictures": [upload()]} | arguments, tool_context)
    assert result["isError"] is True and says in result["content"][0]["text"]
    assert seen == []


async def test_a_slot_that_cannot_be_opened_refuses_that_picture_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def refused(*args: Any, **kwargs: Any) -> None:
        raise InvalidInput("This account holds 10 open upload links. Use one, or wait for them to expire.")

    monkeypatch.setattr(upload_links, "start_upload", refused)
    tool_context = context()
    result = await call({"pictures": [upload(), upload(slot="MASTHEAD")]}, tool_context)
    reply = result["structuredContent"]
    assert result["isError"] is False and (reply["given"], reply["refused"]) == (0, 2)
    assert [place["refused"] for place in reply["uploads"]] == [
        "This account holds 10 open upload links. Use one, or wait for them to expire."
    ] * 2
    assert reply["nextStep"].startswith("No picture was given and no upload was started")


async def test_it_is_listed_as_one_open_world_write_in_the_pictures_group() -> None:
    reply = await answer({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, context(None))
    assert reply is not None
    tools = {tool["name"]: tool for tool in reply["result"]["tools"]}
    for name in ("start_image_upload", "give_image", "give_images"):
        assert name not in tools
    listed = tools["give_pictures"]
    assert (listed["annotations"]["readOnlyHint"], listed["annotations"]["openWorldHint"]) == (False, True)
    assert listed["_meta"]["kalavigyan/group"] == "pictures"
    assert "single-use link" in listed["description"] and "30 minutes" in listed["description"]
    assert mcp_picture_tools.GIVE_PICTURES.scope == CONTRIBUTE_SCOPE
