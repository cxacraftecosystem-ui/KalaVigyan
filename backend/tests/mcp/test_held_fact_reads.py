from typing import Any

import pytest

from app.api import mcp_read_tools
from app.api.mcp_tools import ToolContext, answer
from app.core.errors import InvalidInput
from app.models import User
from app.retrieval.citation_access import HELD_KEPT, HELD_LEFT_OUT
from app.services.craft_resolver import CraftIndexStore
from app.services.knowledge_api import held_facts_for

SITE = "https://kalavigyan.example"


@pytest.mark.parametrize(
    ("role", "held"),
    [
        (None, HELD_LEFT_OUT),
        ("STUDENT", HELD_LEFT_OUT),
        ("ARTISAN", HELD_LEFT_OUT),
        ("RESEARCHER", HELD_KEPT),
        ("PROFESSOR", HELD_KEPT),
        ("MASTER_ADMIN", HELD_KEPT),
    ],
)
def test_researchers_and_above_read_held_facts_to_re_source_them(role: str | None, held: str) -> None:
    assert held_facts_for(role) == held


async def test_get_facts_keeps_held_facts_for_a_researcher_and_leaves_them_out_for_others(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[str] = []

    async def facts(session: Any, slug: str, **asked: Any) -> Any:
        seen.append(asked["held"])
        raise InvalidInput("No craft has the slug Kutch-Ajrakh; find_crafts gives the slugs.")

    monkeypatch.setattr(mcp_read_tools.knowledge_api, "craft_facts", facts)
    call = {"jsonrpc": "2.0", "id": 1, "method": "tools/call"}
    params = {"name": "get_facts", "arguments": {"craft_slug": "Kutch-Ajrakh"}}
    for user in (None, User(role="STUDENT"), User(role="RESEARCHER")):
        context = ToolContext(session=None, index=CraftIndexStore(), site=SITE, user=user)  # type: ignore[arg-type]
        reply = await answer(call | {"params": params}, context)
        assert reply is not None and reply["result"]["isError"] is True
    assert seen == [HELD_LEFT_OUT, HELD_LEFT_OUT, HELD_KEPT]
