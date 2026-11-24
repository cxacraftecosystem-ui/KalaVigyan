import asyncio
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

import pytest

from app.providers import media_router, router as provider_router
from app.providers.base import Adapter, BilledFailure, MediaPoll, MediaRequest, MediaResult, ProviderError
from app.providers.budget import BudgetDecision
from app.providers.catalogue import AiTask
from app.providers.media_router import MediaAsk, MediaRouter
from app.providers.router import Principal, RouteChoice, RouterError

from .fakes import media_result, png_bytes
from .mp4_builder import movie

ASK = MediaAsk(
    task=AiTask.IMAGE,
    prompt="Draw one stage.",
    output={"aspect_ratio": "1:1", "image_size": "1K"},
    units=1.0,
    principal=Principal(user_id=uuid.uuid4(), role="STUDENT"),
)


def route(ordinal: int, model: str) -> RouteChoice:
    return RouteChoice(
        ordinal=ordinal,
        provider="GEMINI",
        provider_id=None,
        preset="gemini",
        kind="gemini",
        base_url=None,
        key_name="GEMINI_API_KEY",
        model=model,
    )


@dataclass
class Ledger:
    routes: list[RouteChoice]
    allowed: bool = True
    reserved: list[tuple[str, Decimal]] = field(default_factory=list)
    settled: list[dict[str, Any]] = field(default_factory=list)


@pytest.fixture
def ledger(monkeypatch: pytest.MonkeyPatch) -> Ledger:
    found = Ledger(routes=[route(1, "gemini-3.1-flash-image"), route(2, "gemini-nano-banana-2.1")])

    async def load_routes(session: Any, task: AiTask) -> list[RouteChoice]:
        return [r for r in found.routes if task == AiTask.IMAGE or r.model == "gemini-omni-1.2-flash"]

    async def reserve(session: Any, **kw: Any) -> tuple[uuid.UUID, BudgetDecision]:
        found.reserved.append((kw["choice"].model, kw["estimate_usd"]))
        reason = None if found.allowed else "MEDIA_CAP"
        return uuid.uuid4(), BudgetDecision(found.allowed, reason, False, Decimal(0))

    async def settle(session: Any, event_id: uuid.UUID, **kw: Any) -> None:
        found.settled.append(kw)

    async def nothing(*_: Any, **__: Any) -> Any:
        return {}

    monkeypatch.setattr(media_router, "load_routes", load_routes)
    monkeypatch.setattr(media_router, "reserve", reserve)
    monkeypatch.setattr(media_router, "settle", settle)
    monkeypatch.setattr(provider_router, "settle", settle)
    monkeypatch.setattr(media_router.spend_settings, "load_spend_settings", nothing)
    monkeypatch.setattr(media_router.managed_keys, "refresh_if_stale", nothing)
    monkeypatch.setattr(media_router.managed_keys, "peek_secret", lambda name: "test-only-key")
    return found


@asynccontextmanager
async def no_session() -> Any:
    yield None


class Scripted(Adapter):
    def __init__(self, outcomes: dict[str, list[Any]], calls: list[str]) -> None:
        super().__init__(api_key="k", base_url=None, preset="gemini", extra={}, learned={})
        self.outcomes = outcomes
        self.calls = calls

    async def chat(self, req: Any) -> Any:
        raise AssertionError("media never chats")

    async def list_models(self) -> list[dict]:
        return []

    async def generate_image(self, req: MediaRequest) -> MediaResult:
        return self._next(req.model)

    async def start_video(self, req: MediaRequest) -> str:
        self.calls.append("start")
        return "v1_video"

    async def poll_video(self, ref: str) -> MediaPoll:
        return self._next("poll")

    async def forget_media(self, ref: str) -> None:
        self.calls.append(f"forget:{ref}")

    def _next(self, name: str) -> Any:
        self.calls.append(name)
        outcome = self.outcomes[name].pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def router(outcomes: dict[str, list[Any]], calls: list[str], **kw: Any) -> MediaRouter:
    return MediaRouter(
        session_factory=no_session,
        adapter_factory=lambda choice, key: Scripted(outcomes, calls),
        **kw,
    )


async def test_an_unavailable_route_falls_through_and_each_call_is_reserved_and_settled(
    ledger: Ledger,
) -> None:
    calls: list[str] = []
    outcomes = {
        "gemini-3.1-flash-image": [ProviderError("down", kind="unavailable")],
        "gemini-nano-banana-2.1": [media_result(png_bytes())],
    }
    made = await router(outcomes, calls).generate(ASK)
    assert calls == ["gemini-3.1-flash-image", "gemini-nano-banana-2.1"]
    assert made.model == "gemini-nano-banana-2.1"
    assert ledger.reserved == [
        ("gemini-3.1-flash-image", Decimal("0.067000")),
        ("gemini-nano-banana-2.1", Decimal("0.033600")),
    ]
    assert [s["outcome"] for s in ledger.settled] == ["ERROR", "OK"]
    assert made.cost_usd == Decimal("0.034050") == ledger.settled[1]["cost_usd"]


async def test_a_refusal_stops_the_walk_and_is_settled_as_refused(ledger: Ledger) -> None:
    calls: list[str] = []
    outcomes = {"gemini-3.1-flash-image": [ProviderError("blocked", kind="refusal")]}
    with pytest.raises(RouterError) as refused:
        await router(outcomes, calls).generate(ASK)
    assert refused.value.kind == "refusal" and calls == ["gemini-3.1-flash-image"]
    assert ledger.settled[0]["outcome"] == "REFUSED_PROVIDER"


async def test_the_media_cap_refuses_before_any_provider_call(ledger: Ledger) -> None:
    ledger.allowed = False
    calls: list[str] = []
    with pytest.raises(RouterError) as refused:
        await router({}, calls).generate(ASK)
    assert (refused.value.kind, refused.value.reason, calls) == ("ceiling", "MEDIA_CAP", [])
    assert "images and video" in refused.value.message


async def test_a_video_is_polled_until_done_then_forgotten(ledger: Ledger) -> None:
    ledger.routes = [route(1, "gemini-omni-1.2-flash")]
    clip = MediaResult(movie().data, "video/mp4", 410, 46336, 46336, "v1_video", None)
    calls: list[str] = []
    slept: list[float] = []

    async def sleep(seconds: float) -> None:
        slept.append(seconds)

    outcomes = {"poll": [MediaPoll(done=False), MediaPoll(done=True, result=clip)]}
    video = MediaAsk(AiTask.VIDEO, "Show one stage.", {"duration": "8s"}, 8.0, ASK.principal)
    made = await router(outcomes, calls, sleep=sleep).generate(video)
    assert calls == ["start", "poll", "poll", "forget:v1_video"]
    assert slept == [5.0]
    assert ledger.reserved == [("gemini-omni-1.2-flash", Decimal("0.560000"))]
    assert made.cost_usd == Decimal("0.556647")


async def test_a_call_cut_off_by_the_timeout_is_settled_at_its_estimate(ledger: Ledger) -> None:
    ledger.routes = [route(1, "gemini-omni-1.2-flash")]
    calls: list[str] = []

    async def forever(seconds: float) -> None:
        await asyncio.sleep(3600)

    video = MediaAsk(AiTask.VIDEO, "Show one stage.", {"duration": "8s"}, 8.0, ASK.principal)
    outcomes = {"poll": [MediaPoll(done=False)]}
    with pytest.raises(TimeoutError):
        async with asyncio.timeout(0.05):
            await router(outcomes, calls, sleep=forever).generate(video)
    assert ledger.settled == [
        {"outcome": "CANCELLED", "cost_usd": Decimal("0.560000"), "error_kind": "abandoned"}
    ]
    assert calls[-1] == "forget:v1_video"


async def test_a_clip_lost_after_the_provider_took_it_is_settled_at_its_estimate(ledger: Ledger) -> None:
    ledger.routes = [route(1, "gemini-omni-1.2-flash")]
    calls: list[str] = []
    lost = BilledFailure("Cannot reach Gemini (ReadTimeout)", kind="unavailable", retryable=True)
    video = MediaAsk(AiTask.VIDEO, "Show one stage.", {"duration": "8s"}, 8.0, ASK.principal)
    with pytest.raises(RouterError) as exhausted:
        await router({"poll": [lost]}, calls).generate(video)
    assert exhausted.value.kind == "exhausted"
    assert calls == ["start", "poll", "forget:v1_video"]
    [settled] = ledger.settled
    assert (settled["outcome"], settled["error_kind"], settled["cost_usd"]) == (
        "ERROR",
        "unavailable",
        Decimal("0.560000"),
    )


async def test_an_image_lost_after_it_was_made_counts_its_estimate_and_the_next_route_answers(
    ledger: Ledger,
) -> None:
    calls: list[str] = []
    outcomes = {
        "gemini-3.1-flash-image": [BilledFailure("Gemini answered 503", kind="unavailable")],
        "gemini-nano-banana-2.1": [media_result(png_bytes())],
    }
    made = await router(outcomes, calls).generate(ASK)
    assert made.model == "gemini-nano-banana-2.1"
    assert [(s["outcome"], s["cost_usd"]) for s in ledger.settled] == [
        ("ERROR", Decimal("0.067000")),
        ("OK", Decimal("0.034050")),
    ]


@pytest.mark.parametrize(
    "failure",
    [
        ProviderError("Gemini answered 503", kind="unavailable", retryable=True),
        ProviderError("Gemini declined the media (failed)", kind="refusal"),
        ProviderError("Gemini stopped the media (failed)", kind="error", retryable=True),
    ],
)
async def test_a_failure_before_the_work_was_taken_or_the_provider_s_own_verdict_costs_nothing(
    ledger: Ledger, failure: ProviderError
) -> None:
    ledger.routes = [route(1, "gemini-3.1-flash-image")]
    with pytest.raises(RouterError):
        await router({"gemini-3.1-flash-image": [failure]}, []).generate(ASK)
    [settled] = ledger.settled
    assert (settled["error_kind"], settled["cost_usd"]) == (failure.kind, Decimal(0))
