from __future__ import annotations

import base64
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.core import managed_keys
from app.core.db import sessionmaker
from app.providers import budget, spend_settings
from app.providers.base import ChatRequest, ChatResult, ProviderError
from app.providers.catalogue import AiTask, model_for
from app.providers.registry import build_adapter
from app.providers.router import (
    Principal,
    RouteChoice,
    estimate_for,
    load_routes,
    reserve,
    route_allowed,
    settle,
    settle_abandoned,
)
from app.research.image_screens import (
    NOT_SCREENED,
    VISION_ANSWER_SCHEMA,
    VISION_OUTPUT_TOKENS,
    ScreenTools,
    VisionRequest,
    VisionVerdict,
    unscreened,
    vision_prompt,
    vision_verdict,
)

__all__ = ["IMAGE_TOKENS", "VISION_TASK", "picture_screen_tools", "provider_content", "screen_with_vision"]

VISION_TASK = AiTask.CAPTION
IMAGE_TOKENS = 800
CONTENT_KINDS = frozenset({"anthropic", "gemini", "openai", "openai_compatible"})
NO_ROUTE = "No vision route is set up, so the picture was not looked at automatically."
NO_BUDGET = "The AI budget did not allow the screen."
FAILED = "The vision screen could not run ({kind})."
UNREAD = "The vision screen's answer could not be read."
SCREEN_DETAIL = "picture screen"


@dataclass(frozen=True)
class _Route:
    choice: RouteChoice
    estimate_usd: Decimal
    overrides: dict[str, Any]


def picture_screen_tools() -> ScreenTools:
    return ScreenTools(vision=screen_with_vision)


def provider_content(kind: str, request: VisionRequest, text: str) -> list[dict[str, Any]]:
    if kind == "gemini":
        parts = [{"inline_data": {"mime_type": request.mime, "data": request.preview}}, {"text": text}]
        return [{"role": "user", "parts": parts}]
    encoded = base64.b64encode(request.preview).decode("ascii")
    if kind == "anthropic":
        image = {"type": "base64", "media_type": request.mime, "data": encoded}
        return [{"type": "image", "source": image}, {"type": "text", "text": text}]
    data_url = f"data:{request.mime};base64,{encoded}"
    return [{"type": "image_url", "image_url": {"url": data_url}}, {"type": "text", "text": text}]


async def screen_with_vision(request: VisionRequest) -> VisionVerdict:
    system, text = vision_prompt(ai_made=request.ai_made)
    route = await _cheapest(budget.estimate_tokens(f"{system}\n{text}") + IMAGE_TOKENS)
    if route is None:
        return unscreened(NO_ROUTE)
    principal = Principal(user_id=request.user_id, role=request.role)
    async with sessionmaker()() as session:
        event_id, decision = await reserve(
            session,
            task=VISION_TASK,
            choice=route.choice,
            principal=principal,
            estimate_usd=route.estimate_usd,
        )
    if not decision.allowed:
        return unscreened(NO_BUDGET)
    content: Any = provider_content(route.choice.kind, request, text)
    chat = ChatRequest(
        model=route.choice.model,
        system=system,
        user=content,
        max_tokens=VISION_OUTPUT_TOKENS,
        json_schema=dict(VISION_ANSWER_SCHEMA),
    )
    try:
        result = await _called(route.choice, chat)
    except ProviderError as failure:
        await _settled_failure(event_id, failure)
        return unscreened(FAILED.format(kind=failure.kind or "error"))
    except BaseException:
        await settle_abandoned(sessionmaker(), event_id, route.estimate_usd)
        raise
    return await _settled(route, event_id, result, request)


async def _cheapest(prompt_tokens: int) -> _Route | None:
    async with sessionmaker()() as session:
        routes = [
            route
            for route in await load_routes(session, VISION_TASK)
            if route_allowed(route, VISION_TASK) and route.kind in CONTENT_KINDS
        ]
        overrides = (await spend_settings.load_spend_settings(session)).get(spend_settings.MODEL_PRICES) or {}
        await managed_keys.refresh_if_stale(session)
    if not routes:
        return None

    def estimate(choice: RouteChoice) -> Decimal:
        return estimate_for(
            choice,
            VISION_TASK,
            prompt_tokens=prompt_tokens,
            max_tokens=VISION_OUTPUT_TOKENS,
            units=None,
            overrides=overrides,
        )

    choice = min(routes, key=lambda route: (estimate(route), route.ordinal))
    return _Route(choice=choice, estimate_usd=estimate(choice), overrides=overrides)


async def _called(choice: RouteChoice, chat: ChatRequest) -> ChatResult:
    adapter = build_adapter(
        preset=choice.preset,
        kind=choice.kind,
        api_key=managed_keys.peek_secret(choice.key_name),
        api_key_name=choice.key_name,
        base_url=choice.base_url,
        extra=choice.extra,
        learned=choice.learned,
    )
    try:
        return await adapter.chat(chat)
    finally:
        await adapter.aclose()


async def _settled(route: _Route, event_id: Any, result: ChatResult, request: VisionRequest) -> VisionVerdict:
    choice = route.choice
    cost = budget.token_cost(
        model_for(choice.provider, choice.model),
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        cached_tokens=result.cached_input_tokens,
        overrides=route.overrides,
    )
    async with sessionmaker()() as session:
        await settle(
            session,
            event_id,
            outcome="OK",
            cost_usd=cost,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            cached_tokens=result.cached_input_tokens,
            latency_ms=result.latency_ms,
            detail={"servedModel": result.meta.get("served_model"), "use": SCREEN_DETAIL},
        )
    parsed = vision_verdict(result.text, ai_made=request.ai_made, faces=request.faces)
    flags, note = parsed if parsed is not None else ((NOT_SCREENED,), UNREAD)
    return VisionVerdict(
        ran=parsed is not None,
        flags=flags,
        note=note,
        provider=choice.provider,
        model=choice.model,
        usage_event_id=event_id,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        cost_usd=cost,
    )


async def _settled_failure(event_id: Any, failure: ProviderError) -> None:
    async with sessionmaker()() as session:
        await settle(
            session,
            event_id,
            outcome="REFUSED_PROVIDER" if failure.kind == "refusal" else "ERROR",
            error_kind=failure.kind,
            detail={"status": failure.status, "use": SCREEN_DETAIL},
        )
