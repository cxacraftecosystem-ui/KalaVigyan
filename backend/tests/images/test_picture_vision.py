import asyncio
import base64
import uuid
from typing import Any

import pytest

from app.providers import picture_vision
from app.providers.base import Adapter, ChatRequest, ChatResult, ProviderError
from app.providers.catalogue import AiTask
from app.providers.picture_vision import FAILED, provider_content, screen_with_vision
from app.providers.router import ABANDONED_KIND, RouteChoice
from app.providers.spend_settings import MODEL_PRICES
from app.research.image_screens import NOT_SCREENED, VisionRequest

from ..router_fakes import Recorded, anthropic_route, record_router

PREVIEW = b"\xff\xd8preview"
REQUEST = VisionRequest(
    preview=PREVIEW, mime="image/jpeg", ai_made=False, user_id=uuid.UUID(int=1), role="RESEARCHER"
)
ENCODED = base64.b64encode(PREVIEW).decode("ascii")


def test_gemini_gets_the_picture_as_inline_bytes_beside_the_question() -> None:
    assert provider_content("gemini", REQUEST, "Is it an ID?") == [
        {
            "role": "user",
            "parts": [
                {"inline_data": {"mime_type": "image/jpeg", "data": PREVIEW}},
                {"text": "Is it an ID?"},
            ],
        }
    ]


def test_anthropic_gets_a_base64_image_block_before_the_question() -> None:
    assert provider_content("anthropic", REQUEST, "Is it an ID?") == [
        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": ENCODED}},
        {"type": "text", "text": "Is it an ID?"},
    ]


def test_openai_shaped_routes_get_a_data_url() -> None:
    for kind in ("openai", "openai_compatible"):
        assert provider_content(kind, REQUEST, "Is it an ID?") == [
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{ENCODED}"}},
            {"type": "text", "text": "Is it an ID?"},
        ]


class CutAdapter(Adapter):
    def __init__(self, failure: BaseException | None) -> None:
        super().__init__(api_key="k", base_url=None, preset="anthropic", extra={}, learned={})
        self.failure = failure

    async def chat(self, req: ChatRequest) -> ChatResult:
        if self.failure is None:
            await asyncio.Event().wait()
        raise self.failure

    async def list_models(self) -> list[dict]:
        return []


def screening(monkeypatch: pytest.MonkeyPatch, failure: BaseException | None) -> Recorded:
    recorded = record_router(
        monkeypatch, settings={MODEL_PRICES: {"claude-sonnet-5-5": {"in": 2, "out": 10}}}
    )

    async def routes(_session: Any, _task: AiTask) -> list[RouteChoice]:
        return [anthropic_route()]

    async def settle(_session: Any, event_id: Any, **settled: Any) -> None:
        recorded.settled.append(settled)

    monkeypatch.setattr(picture_vision, "load_routes", routes)
    monkeypatch.setattr(picture_vision, "build_adapter", lambda **_: CutAdapter(failure))
    monkeypatch.setattr(picture_vision, "sessionmaker", recorded.sessions)
    monkeypatch.setattr(picture_vision, "settle", settle)
    return recorded


def settled_at_the_estimate(recorded: Recorded) -> list[dict[str, Any]]:
    [reserved] = recorded.reserved
    assert reserved.outcome == "RESERVED" and reserved.estimatedCostUsd > 0
    return [{"outcome": "CANCELLED", "cost_usd": reserved.estimatedCostUsd, "error_kind": ABANDONED_KIND}]


async def test_a_vision_screen_cut_off_by_its_caller_settles_its_reservation_at_the_estimate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded = screening(monkeypatch, None)
    with pytest.raises(TimeoutError):
        async with asyncio.timeout(0.05):
            await screen_with_vision(REQUEST)
    assert recorded.settled == settled_at_the_estimate(recorded)


async def test_a_bug_in_a_vision_call_settles_at_the_estimate_and_still_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded = screening(monkeypatch, RuntimeError("a bug in the adapter"))
    with pytest.raises(RuntimeError, match="a bug in the adapter"):
        await screen_with_vision(REQUEST)
    assert recorded.settled == settled_at_the_estimate(recorded)


async def test_a_refused_vision_call_settles_as_an_error_and_leaves_the_picture_unscreened(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded = screening(monkeypatch, ProviderError("down", kind="unavailable", status=503))
    verdict = await screen_with_vision(REQUEST)
    assert (verdict.ran, verdict.flags, verdict.note) == (
        False,
        (NOT_SCREENED,),
        FAILED.format(kind="unavailable"),
    )
    assert [(entry["outcome"], entry["error_kind"]) for entry in recorded.settled] == [
        ("ERROR", "unavailable")
    ]
