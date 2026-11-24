from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core import managed_keys
from app.core.errors import SPEND_REFUSAL_KIND, STOP_KINDS
from app.providers.catalogue import AUDIO_TASKS, MEDIA_TASKS, AiTask, model_for

from . import budget, spend_settings
from .base import Adapter, BilledFailure, MediaRequest, MediaResult, ProviderError
from .registry import build_adapter
from .router import (
    Principal,
    RouteChoice,
    RouterError,
    current_spend,
    estimate_for,
    load_routes,
    mark_key_failed,
    order_routes,
    reserve,
    settle,
    settle_abandoned,
)

__all__ = ["PRICE_DRIFT_LIMIT", "VIDEO_POLL_SECONDS", "MediaAsk", "MediaCall", "MediaRouter", "media_cost"]

logger = logging.getLogger(__name__)

VIDEO_POLL_SECONDS = 5.0
PRICE_DRIFT_LIMIT = Decimal("0.20")

AdapterFactory = Callable[[RouteChoice, str | None], Adapter]
Sleep = Callable[[float], Awaitable[None]]


@dataclass(frozen=True)
class MediaAsk:
    task: AiTask
    prompt: str
    output: Mapping[str, str]
    units: float
    principal: Principal


@dataclass(frozen=True)
class MediaCall:
    result: MediaResult
    provider: str
    model: str
    usage_event_id: uuid.UUID
    cost_usd: Decimal


@dataclass(frozen=True)
class _Routes:
    choices: list[RouteChoice]
    overrides: dict[str, Any]


class MediaRouter:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        adapter_factory: AdapterFactory | None = None,
        sleep: Sleep = asyncio.sleep,
        poll_seconds: float = VIDEO_POLL_SECONDS,
    ) -> None:
        self._sessions = session_factory
        self._adapter_factory = adapter_factory or _built_adapter
        self._sleep = sleep
        self._poll_seconds = poll_seconds

    async def first_model(self, task: AiTask) -> str | None:
        routes = await self._routes(task)
        return routes.choices[0].model if routes.choices else None

    async def available(self, ask: MediaAsk) -> bool:
        routes = await self._routes(ask.task)
        keyed = [c for c in routes.choices if managed_keys.peek_secret(c.key_name)]
        if not keyed:
            return False
        async with self._sessions() as session:
            ceilings = budget.Ceilings.from_settings(await spend_settings.load_spend_settings(session))
            spend = await current_spend(session, ask.principal)
        decision = budget.evaluate(
            ceilings,
            spend,
            estimate_usd=_estimate(keyed[0], ask, routes.overrides),
            is_media=True,
            role=ask.principal.role,
        )
        return decision.allowed

    async def hold(self, ask: MediaAsk) -> uuid.UUID:
        routes = await self._routes(ask.task)
        if not routes.choices:
            raise RouterError("no_route", f"No enabled route can run {ask.task.value}")
        return await self._reserve(routes.choices[0], ask, routes.overrides)

    async def release(self, event_id: uuid.UUID) -> None:
        async with self._sessions() as session:
            await settle(session, event_id, outcome="CANCELLED")

    async def generate(self, ask: MediaAsk) -> MediaCall:
        routes = await self._routes(ask.task)
        if not routes.choices:
            raise RouterError("no_route", f"No enabled route can run {ask.task.value}")
        attempts: list[dict[str, Any]] = []
        for choice in routes.choices:
            try:
                return await self._call(choice, ask, routes.overrides)
            except ProviderError as failure:
                attempts.append({"provider": choice.provider, "model": choice.model, "outcome": failure.kind})
                logger.warning(
                    "media route failed",
                    extra={"task": ask.task.value, "model": choice.model, "kind": failure.kind},
                )
                if failure.kind in STOP_KINDS:
                    raise RouterError(failure.kind, str(failure), attempts=attempts) from failure
        raise RouterError("exhausted", f"Every route for {ask.task.value} failed", attempts=attempts)

    async def _routes(self, task: AiTask) -> _Routes:
        if task not in MEDIA_TASKS:
            raise RouterError("unsupported", f"{task.value} is not a media task")
        async with self._sessions() as session:
            loaded = await load_routes(session, task)
            values = await spend_settings.load_spend_settings(session)
            await managed_keys.refresh_if_stale(session)
        ordered = order_routes(task, loaded, degrade=False, estimate=lambda _: Decimal(0))
        return _Routes(choices=ordered, overrides=values.get(spend_settings.MODEL_PRICES) or {})

    async def _reserve(self, choice: RouteChoice, ask: MediaAsk, overrides: dict[str, Any]) -> uuid.UUID:
        async with self._sessions() as session:
            event_id, decision = await reserve(
                session,
                task=ask.task,
                choice=choice,
                principal=ask.principal,
                estimate_usd=_estimate(choice, ask, overrides),
                units=ask.units,
            )
        if not decision.allowed:
            raise RouterError(
                SPEND_REFUSAL_KIND, decision.message or "Budget reached", reason=decision.reason
            )
        return event_id

    async def _call(self, choice: RouteChoice, ask: MediaAsk, overrides: dict[str, Any]) -> MediaCall:
        event_id = await self._reserve(choice, ask, overrides)
        estimate = _estimate(choice, ask, overrides)
        key = managed_keys.peek_secret(choice.key_name)
        adapter: Adapter | None = None
        try:
            adapter = self._adapter_factory(choice, key)
            result = await self._produce(adapter, choice, ask)
        except ProviderError as failure:
            await self._settle_failure(event_id, choice, key, failure, estimate=estimate)
            raise
        except BaseException:
            await settle_abandoned(self._sessions, event_id, estimate, answer=ask.principal.answer)
            raise
        finally:
            if adapter is not None:
                await adapter.aclose()
        cost = media_cost(choice, result, units=ask.units, overrides=overrides)
        async with self._sessions() as session:
            await settle(
                session,
                event_id,
                outcome="OK",
                cost_usd=cost,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                detail={"servedModel": result.served_model, "mediaTokens": result.media_tokens},
                units=ask.units,
            )
        return MediaCall(result, choice.provider, choice.model, event_id, cost)

    async def _produce(self, adapter: Adapter, choice: RouteChoice, ask: MediaAsk) -> MediaResult:
        request = MediaRequest(
            model=choice.model, prompt=ask.prompt, kind=ask.task.value, output=dict(ask.output)
        )
        if ask.task == AiTask.IMAGE:
            return await adapter.generate_image(request)
        if ask.task in AUDIO_TASKS:
            return await adapter.generate_audio(request)
        ref = await adapter.start_video(request)
        try:
            while True:
                poll = await adapter.poll_video(ref)
                if poll.done and poll.result is not None:
                    return poll.result
                await self._sleep(max(self._poll_seconds, adapter.video_poll_seconds))
        finally:
            await _forget(adapter, ref)

    async def _settle_failure(
        self,
        event_id: uuid.UUID,
        choice: RouteChoice,
        key: str | None,
        failure: ProviderError,
        *,
        estimate: Decimal,
    ) -> None:
        async with self._sessions() as session:
            await settle(
                session,
                event_id,
                outcome="REFUSED_PROVIDER" if failure.kind == "refusal" else "ERROR",
                cost_usd=estimate if isinstance(failure, BilledFailure) else Decimal(0),
                error_kind=failure.kind,
                detail={"status": failure.status},
            )
            if failure.kind == "auth":
                await mark_key_failed(session, choice.key_name, key, str(failure))


def media_cost(
    choice: RouteChoice, result: MediaResult, *, units: float, overrides: Mapping[str, Any]
) -> Decimal:
    model = model_for(choice.provider, choice.model)
    configured = budget.unit_cost(model, units, dict(overrides))
    if result.output_tokens is None:
        return configured
    cost = budget.token_cost(
        model,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        media_tokens=result.media_tokens,
        overrides=dict(overrides),
    )
    if configured > 0 and abs(cost - configured) > configured * PRICE_DRIFT_LIMIT:
        logger.warning(
            "media price drift",
            extra={"model": choice.model, "billedUsd": str(cost), "configuredUsd": str(configured)},
        )
    return cost


def _estimate(choice: RouteChoice, ask: MediaAsk, overrides: dict[str, Any]) -> Decimal:
    return estimate_for(choice, ask.task, prompt_tokens=0, max_tokens=0, units=ask.units, overrides=overrides)


def _built_adapter(choice: RouteChoice, key: str | None) -> Adapter:
    return build_adapter(
        preset=choice.preset,
        kind=choice.kind,
        api_key=key,
        api_key_name=choice.key_name,
        base_url=choice.base_url,
        extra=choice.extra,
        learned=choice.learned,
    )


async def _forget(adapter: Adapter, ref: str) -> None:
    try:
        await adapter.forget_media(ref)
    except ProviderError as failure:
        logger.warning("media interaction not deleted", extra={"ref": ref, "kind": failure.kind})
