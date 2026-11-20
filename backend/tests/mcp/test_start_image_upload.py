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
DECLARATION = {
    "origin": "DRAWING",
    "caption": "The resist paste on the block",
    "altText": "A drawing of a carved block coated in grey paste",
    "rightsConfirmed": True,
    "termsVersion": "2026-11-19",
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


async def call(arguments: dict[str, Any], tool_context: ToolContext) -> dict[str, Any]:
    message = {
        "jsonrpc": "2.0",
        "id": 5,
        "method": "tools/call",
        "params": {"name": "start_image_upload", "arguments": arguments},
    }
    reply = await answer(message, tool_context)
    assert reply is not None and "result" in reply, reply
    return reply["result"]


async def test_without_a_declaration_it_returns_only_the_link_for_the_person(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = issuing(monkeypatch)
    tool_context = context()
    result = await call(
        {"craft_slug": "Kutch-Ajrakh", "stage_id": str(STAGE), "claim_ids": [str(FACT)]}, tool_context
    )
    shown = result["structuredContent"]
    assert shown["link"] == f"{SITE}/contributions/pictures/upload?link={LINK}"
    assert (shown["uploadUrl"], shown["declared"], shown["expiresAt"]) == (
        None,
        False,
        "2026-11-19T12:30:00Z",
    )
    assert shown["nextStep"].startswith("Send the person the link")
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
    result = await call(
        {"craft_slug": "Kutch-Ajrakh", "claim_ids": [str(FACT)], "declaration": DECLARATION}, context()
    )
    shown = result["structuredContent"]
    assert shown["uploadUrl"] == f"{API}/api/upload-links/slots/{SLOT}"
    assert shown["declared"] is True and "PUT the picture's bytes to upload_url" in shown["nextStep"]
    ((_, declaration),) = seen
    assert declaration is not None and (declaration.origin, declaration.alt_text) == (
        "DRAWING",
        DECLARATION["altText"],
    )


async def test_without_a_configured_api_origin_the_link_is_the_only_way(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    issuing(monkeypatch, api=None)
    result = await call(
        {"craft_slug": "Kutch-Ajrakh", "claim_ids": [str(FACT)], "declaration": DECLARATION}, context()
    )
    assert result["structuredContent"]["uploadUrl"] is None


@pytest.mark.parametrize(
    ("tool_context", "arguments", "says"),
    [
        (context(None), {}, "needs a signed-in connection"),
        (context(scopes=frozenset({READ_SCOPE})), {}, "needs the contribute scope"),
        (context(), {"claim_ids": [str(FACT), str(FACT)]}, "Each fact is named once"),
        (context(), {"claim_ids": []}, "claim_ids"),
        (context(), {"declaration": DECLARATION | {"rightsConfirmed": False}}, "rightsConfirmed"),
    ],
)
async def test_it_needs_sign_in_the_contribute_scope_and_a_well_formed_slot(
    monkeypatch: pytest.MonkeyPatch, tool_context: ToolContext, arguments: dict[str, Any], says: str
) -> None:
    seen = issuing(monkeypatch)
    result = await call({"craft_slug": "Kutch-Ajrakh", "claim_ids": [str(FACT)]} | arguments, tool_context)
    assert result["isError"] is True and says in result["content"][0]["text"]
    assert seen == []


async def test_a_refused_link_rolls_back_and_says_why(monkeypatch: pytest.MonkeyPatch) -> None:
    async def refused(*args: Any, **kwargs: Any) -> None:
        raise InvalidInput("This account holds 10 open upload links. Use one, or wait for them to expire.")

    monkeypatch.setattr(upload_links, "start_upload", refused)
    tool_context = context()
    result = await call({"craft_slug": "Kutch-Ajrakh", "claim_ids": [str(FACT)]}, tool_context)
    assert result["isError"] is True and "10 open upload links" in result["content"][0]["text"]
    assert tool_context.session.ended == ["rollback"]  # type: ignore[attr-defined]


async def test_it_is_listed_as_a_write_that_needs_the_contribute_scope() -> None:
    reply = await answer({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, context(None))
    assert reply is not None
    (listed,) = [tool for tool in reply["result"]["tools"] if tool["name"] == "start_image_upload"]
    assert listed["annotations"]["readOnlyHint"] is False
    assert "single-use link" in listed["description"] and "30 minutes" in listed["description"]
    assert {"link", "uploadUrl", "expiresAt", "facts"} <= set(listed["outputSchema"]["properties"])
    assert mcp_picture_tools.START_IMAGE_UPLOAD.scope == CONTRIBUTE_SCOPE
