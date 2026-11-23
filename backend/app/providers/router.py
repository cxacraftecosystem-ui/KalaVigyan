from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core import managed_keys
from app.core.errors import SPEND_REFUSAL_KIND, STOP_KINDS
from app.providers.catalogue import MEDIA_TASKS, AiTask, task_of

from . import budget, spend_settings
from .base import Adapter, ProviderError
from .registry import build_adapter
from .route_call import Ask, Called, CallOutcome, Plan, call_cost, call_route, close_adapter, worth_one_retry
from .route_choice import (
    DEFAULT_MAX_OUTPUT_TOKENS,
    DEGRADABLE_TASKS,
    REASONING_EFFORT_PARAM,
    Principal,
    RouteChoice,
    RouterError,
    RouterResult,
    RouteTuning,
    estimate_for,
    order_routes,
    output_tokens_for,
    reasoning_effort,
    route_allowed,
)
from .route_store import (
    current_spend,
    load_routes,
    mark_key_failed,
    persist_learned,
    reserved_event,
    settle,
    tagged_spend,
)

__all__ = [
    "ABANDONED_KIND",
    "DEFAULT_MAX_OUTPUT_TOKENS",
    "DEGRADABLE_TASKS",
    "REASONING_EFFORT_PARAM",
    "Principal",
    "RouteChoice",
    "RouteTuning",
    "RouterError",
    "RouterResult",
    "current_spend",
    "estimate_for",
    "load_routes",
    "mark_key_failed",
    "order_routes",
    "output_tokens_for",
    "reasoning_effort",
    "reserve",
    "route_allowed",
    "run",
    "settle",
    "settle_abandoned",
    "tagged_spend",
]

logger = logging.getLogger(__name__)

BUDGET_LOCK_KEY = 0x4B565F4255444754
ABANDONED_KIND = "abandoned"

_semaphores: dict[str, asyncio.Semaphore] = {}


async def run(
    task: AiTask | str,
    *,
    system: str = "",
    user: str = "",
    json_schema: dict | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
    texts: list[str] | None = None,
    principal: Principal | None = None,
    request_budget_usd: Decimal | None = None,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    tuning: RouteTuning | None = None,
) -> RouterResult:
    resolved = _runnable(task, texts)
    sessions = session_factory or _default_sessions()
    who = principal or Principal()
    ask = Ask(resolved, system, user, json_schema, max_tokens, temperature, texts, request_budget_usd)
    plan = await _planned(sessions, ask, who, tuning)
    ordered = plan.ordered()
    if not ordered:
        raise RouterError("no_route", f"No enabled route can run {resolved.value}")
    attempts: list[dict[str, Any]] = []
    for choice in ordered:
        result = await _attempt(_Attempt(sessions, plan, choice, who, attempts))
        if result is not None:
            return result
    raise RouterError("exhausted", f"Every route for {resolved.value} failed", attempts=attempts)


async def reserve(
    session: AsyncSession,
    *,
    task: AiTask,
    choice: RouteChoice | None,
    principal: Principal,
    estimate_usd: Decimal,
    request_budget_usd: Decimal | None = None,
    units: float | None = None,
) -> tuple[uuid.UUID, budget.BudgetDecision]:
    await session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": BUDGET_LOCK_KEY})
    ceilings = budget.Ceilings.from_settings(await spend_settings.load_spend_settings(session))
    spend = await current_spend(session, principal)
    answer = principal.answer
    decision = budget.evaluate(
        ceilings,
        spend,
        estimate_usd=estimate_usd,
        is_media=task in MEDIA_TASKS,
        role=principal.role,
        request_budget_usd=request_budget_usd,
        answer_left_usd=answer.left(ceilings) if answer else None,
    )
    if answer is not None and decision.allowed:
        answer.hold(estimate_usd)
    event = reserved_event(task, choice, principal, estimate_usd=estimate_usd, decision=decision, units=units)
    session.add(event)
    await session.flush()
    await session.commit()
    return event.id, decision


async def settle_abandoned(
    sessions: async_sessionmaker[AsyncSession],
    event_id: uuid.UUID,
    estimate_usd: Decimal,
    *,
    answer: budget.AnswerSpend | budget.AnswerHeadroom | None = None,
) -> None:
    if answer is not None:
        answer.settle(estimate_usd, estimate_usd)
    try:
        await asyncio.shield(_settle_at_estimate(sessions, event_id, estimate_usd))
    except Exception:
        logger.exception("an abandoned call was not settled", extra={"usageEventId": str(event_id)})


@dataclass(frozen=True)
class _Attempt:
    sessions: async_sessionmaker[AsyncSession]
    plan: Plan
    choice: RouteChoice
    who: Principal
    attempts: list[dict[str, Any]]

    @property
    def estimate_usd(self) -> Decimal:
        return self.plan.estimate(self.choice)

    def noted(self, outcome: str) -> None:
        self.attempts.append(
            {"provider": self.choice.provider, "model": self.choice.model, "outcome": outcome}
        )


async def _settle_at_estimate(
    sessions: async_sessionmaker[AsyncSession], event_id: uuid.UUID, estimate_usd: Decimal
) -> None:
    async with sessions() as session:
        await settle(session, event_id, outcome="CANCELLED", cost_usd=estimate_usd, error_kind=ABANDONED_KIND)


def _semaphore(choice: RouteChoice) -> asyncio.Semaphore:
    found = _semaphores.get(choice.provider)
    if found is None:
        found = asyncio.Semaphore(max(1, choice.max_concurrency))
        _semaphores[choice.provider] = found
    return found


def _runnable(task: AiTask | str, texts: list[str] | None) -> AiTask:
    resolved = task_of(task)
    if resolved is None:
        raise RouterError("unsupported", f"Unknown task {task!r}")
    if resolved in MEDIA_TASKS:
        raise RouterError("unsupported", "Media tasks reserve and settle through reserve() and settle()")
    if resolved == AiTask.EMBED and not texts:
        raise RouterError("bad_request", "Embedding needs texts")
    return resolved


def _default_sessions() -> async_sessionmaker[AsyncSession]:
    from app.core.db import sessionmaker

    return sessionmaker()


async def _planned(
    sessions: async_sessionmaker[AsyncSession], ask: Ask, who: Principal, tuning: RouteTuning | None
) -> Plan:
    async with sessions() as session:
        loaded = await load_routes(session, ask.task)
        settings_values = await spend_settings.load_spend_settings(session)
        spend = await current_spend(session, who)
        await managed_keys.refresh_if_stale(session)
    ceilings = budget.Ceilings.from_settings(settings_values)
    return Plan(
        ask=ask,
        routes=[tuning.applied(route) if tuning else route for route in loaded],
        overrides=settings_values.get(spend_settings.MODEL_PRICES) or {},
        degrade=budget.degrades(ceilings, spend, role=who.role),
    )


async def _attempt(attempt: _Attempt) -> RouterResult | None:
    event_id = await _reserved(attempt)
    try:
        called = await _called(attempt.plan, attempt.choice)
    except BaseException:
        await settle_abandoned(attempt.sessions, event_id, attempt.estimate_usd, answer=attempt.who.answer)
        raise
    if called.outcome is not None:
        return await _succeeded(attempt, event_id, called, called.outcome)
    assert called.failure is not None
    await _failed(attempt, event_id, called, called.failure)
    return None


async def _reserved(attempt: _Attempt) -> uuid.UUID:
    async with attempt.sessions() as session:
        event_id, decision = await reserve(
            session,
            task=attempt.plan.ask.task,
            choice=attempt.choice,
            principal=attempt.who,
            estimate_usd=attempt.estimate_usd,
            request_budget_usd=attempt.plan.ask.request_budget_usd,
        )
    if not decision.allowed:
        raise RouterError(
            SPEND_REFUSAL_KIND,
            decision.message or "Budget reached",
            reason=decision.reason,
            attempts=attempt.attempts,
        )
    return event_id


async def _called(plan: Plan, choice: RouteChoice) -> Called:
    called = Called()
    for retry in range(2):
        try:
            called.adapter = _adapter(choice)
            async with _semaphore(choice):
                called.outcome = await call_route(called.adapter, plan, choice)
            called.failure = None
            return called
        except ProviderError as exc:
            called.failure = exc
            if retry > 0 or not worth_one_retry(exc):
                return called
            await asyncio.sleep(exc.retry_after or 0)
        finally:
            await close_adapter(called.adapter)
    return called


def _adapter(choice: RouteChoice) -> Adapter:
    return build_adapter(
        preset=choice.preset,
        kind=choice.kind,
        api_key=managed_keys.peek_secret(choice.key_name),
        api_key_name=choice.key_name,
        base_url=choice.base_url,
        extra=choice.extra,
        learned=choice.learned,
    )


async def _succeeded(
    attempt: _Attempt, event_id: uuid.UUID, called: Called, outcome: CallOutcome
) -> RouterResult:
    choice, plan = attempt.choice, attempt.plan
    cost = call_cost(plan, choice, outcome)
    if attempt.who.answer is not None:
        attempt.who.answer.settle(attempt.estimate_usd, cost)
    async with attempt.sessions() as session:
        await settle(
            session,
            event_id,
            outcome="OK",
            cost_usd=cost,
            input_tokens=outcome.input_tokens,
            output_tokens=outcome.output_tokens,
            cached_tokens=outcome.cached_tokens,
            latency_ms=outcome.latency_ms,
            detail={"servedModel": outcome.meta.get("served_model"), "degraded": plan.degrade},
        )
        if called.adapter is not None:
            await persist_learned(session, choice, called.adapter)
    attempt.noted("OK")
    return RouterResult(
        task=plan.ask.task.value,
        provider=choice.provider,
        model=choice.model,
        ordinal=choice.ordinal,
        usage_event_id=event_id,
        cost_usd=cost,
        degraded=plan.degrade,
        attempts=attempt.attempts,
        text=outcome.text,
        embeddings=outcome.embeddings,
        input_tokens=outcome.input_tokens,
        output_tokens=outcome.output_tokens,
        meta=outcome.meta,
    )


async def _failed(attempt: _Attempt, event_id: uuid.UUID, called: Called, failure: ProviderError) -> None:
    choice = attempt.choice
    if attempt.who.answer is not None:
        attempt.who.answer.release(attempt.estimate_usd)
    async with attempt.sessions() as session:
        await settle(
            session,
            event_id,
            outcome="REFUSED_PROVIDER" if failure.kind == "refusal" else "ERROR",
            error_kind=failure.kind,
            detail={"status": failure.status},
        )
        if called.adapter is not None:
            await persist_learned(session, choice, called.adapter)
        if failure.kind == "auth":
            await mark_key_failed(
                session, choice.key_name, managed_keys.peek_secret(choice.key_name), str(failure)
            )
    attempt.noted(failure.kind)
    logger.warning(
        "route failed",
        extra={
            "task": attempt.plan.ask.task.value,
            "provider": choice.provider,
            "model": choice.model,
            "kind": failure.kind,
        },
    )
    if failure.kind in STOP_KINDS:
        raise RouterError(failure.kind, str(failure), attempts=attempt.attempts)
