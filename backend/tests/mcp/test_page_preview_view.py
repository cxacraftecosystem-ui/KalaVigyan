import base64
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from app.api.mcp_tools import ToolContext, answer
from app.data.page_preview_view import STATUS_COLOURS, status_css
from app.services.craft_resolver import CraftIndexStore

SITE = "https://kalavigyan.example"
CONTEXT = ToolContext(session=None, index=CraftIndexStore(), site=SITE)  # type: ignore[arg-type]
VIEW_URI = "ui://kalavigyan/page-preview.html"
TOKENS_PATH = Path(__file__).resolve().parents[2] / "app" / "data" / "design" / "tokens.json"
TOKENS = json.loads(TOKENS_PATH.read_text(encoding="utf-8"))
RAW_MARKUP = ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval(", "new Function")


async def result(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    reply = await answer({"jsonrpc": "2.0", "id": 3, "method": method, "params": params or {}}, CONTEXT)
    assert reply is not None and "result" in reply, reply
    return reply["result"]


async def view() -> dict[str, Any]:
    (content,) = (await result("resources/read", {"uri": VIEW_URI}))["contents"]
    return content


async def test_the_page_preview_view_is_listed_as_an_mcp_app_that_loads_nothing() -> None:
    listed = {resource["uri"]: resource for resource in (await result("resources/list"))["resources"]}
    resource = listed[VIEW_URI]
    assert resource["mimeType"] == "text/html;profile=mcp-app"
    assert resource["_meta"] == {
        "ui": {"prefersBorder": True, "csp": {"connectDomains": [], "resourceDomains": []}}
    }
    assert "checklist rule" in resource["description"]


async def test_the_view_is_one_self_contained_page_whose_one_script_its_policy_names() -> None:
    page = (await view())["text"]
    assert "__KV_" not in page
    (script,) = re.findall(r"<script>(.*?)</script>", page, re.DOTALL)
    digest = base64.b64encode(hashlib.sha256(script.encode("utf-8")).digest()).decode("ascii")
    assert f"script-src 'sha256-{digest}'" in page
    assert "default-src 'none'" in page and "<script src" not in page and "<link" not in page
    assert re.findall(r"""(?:src|href)=["']https?:""", page) == []


async def test_the_view_draws_text_as_text_opens_only_https_and_reads_the_tool_result() -> None:
    page = (await view())["text"]
    assert [call for call in RAW_MARKUP if call in page] == []
    assert "textContent" in page and 'url.protocol === "https:"' in page and "ui/open-link" in page
    assert "structuredContent" in page and "ui/notifications/tool-result" in page
    for word in ("Passes", "Fails", "Yours to judge", "Open the private preview"):
        assert word in page


def test_the_status_colours_follow_the_four_themes_of_the_tokens() -> None:
    css = status_css(TOKENS)
    error = TOKENS["color"]["error"]
    assert f"--error:{error['light']['hex']};" in css and f"--error:{error['dark']['hex']};" in css
    assert f"--error:{error['hcLight']['hex']};" in css and f"--error:{error['hcDark']['hex']};" in css
    assert all(f"--{name}:" in css for name in STATUS_COLOURS)


async def test_the_view_carries_the_answer_view_s_theme_and_the_status_colours() -> None:
    page = (await view())["text"]
    assert f"--indigo:{TOKENS['color']['indigo']['light']['hex']};" in page
    assert f"--success-wash:{TOKENS['color']['success-wash']['light']['hex']};" in page
    assert ':root[data-theme="dark"]' in page


async def test_only_the_newest_preview_opens_and_opening_one_folds_the_others() -> None:
    page = (await view())["text"]
    assert "new BroadcastChannel(CHANNEL)" in page and '"kalavigyan-page-preview"' in page
    assert "Show the full report" in page and "Hide the full report" in page
    assert 'setAttribute("aria-expanded"' in page and 'setAttribute("aria-controls", "kv-full")' in page
    assert 'post("opened")' in page and "message.at > shown.at" in page
    assert "setOpen(Boolean(channel))" in page
