from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import case, func, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core import managed_keys
from app.core.errors import RETRYABLE_KINDS, SPEND_REFUSAL_KIND, STOP_KINDS, AppError
from app.core.logging import current_request_id
from app.models import ManagedSecret, Provider, RoutePolicy, SecretTestResult, UsageEvent
from app.providers.catalogue import (
    MEDIA_TASKS,
    PUBLIC_TEXT_TASKS,
    AiTask,
    model_for,
    output_limit,
    supports,
    task_of,
)

from . import budget, spend_settings
from .base import Adapter, ChatRequest, ChatResult, ProviderError
from .registry import build_adapter, merge_learned

logger = logging.getLogger(__name__)

BUDGET_LOCK_KEY = 0x4B565F4255444754
RETRY_AFTER_CAP_SECONDS = 2.0
ABANDONED_KIND = "abandoned"
DEFAULT_MAX_OUTPUT_TOKENS = 4096
DEGRADABLE_TASKS = frozenset(
    {AiTask.COMPOSE, AiTask.EXTRACT, AiTask.VOICE_TURN, AiTask.PLAN, AiTask.UNDERSTAND, AiTask.WEB_READ}
)
EMBED_DIMENSIONS = 1536
REASONING_EFFORT_PARAM = "reasoningEffort"
REASONING_EFFORTS = frozenset({"low", "medium", "high", "xhigh", "max"})
TASK_REASONING_EFFORT: dict[AiTask, str] = {AiTask.COMPOSE: "medium"}


@dataclass(frozen=True)
class Principal:
    user_id: uuid.UUID | None = None
    role: str | None = None
    answer: budget.AnswerSpend | budget.AnswerHeadroom | None = None


@dataclass(frozen=True)
class RouteChoice:
    ordinal: int
    provider: str
    provider_id: uuid.UUID | None
    preset: str
    kind: str
    base_url: str | None
    key_name: str
    model: str
    max_output_tokens: int | None = None
    temperature: float | None = None
    max_concurrency: int = 4
    data_class: str = "ANY"
    learned: dict[str, list[str]] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RouteTuning:
    models: Mapping[str, str] = field(default_factory=dict)
    effort: str | None = None
    max_output_tokens: int | None = None

    def __post_init__(self) -> None:
        if self.effort is not None and self.effort not in REASONING_EFFORTS:
            raise ValueError(f"unknown reasoning effort {self.effort!r}")
        if self.max_output_tokens is not None and self.max_output_tokens < 1:
            raise ValueError("a tuned output cap is at least one token")

    def applied(self, choice: RouteChoice) -> RouteChoice:
        params = {**choice.params, REASONING_EFFORT_PARAM: self.effort} if self.effort else choice.params
        cap = max(choice.max_output_tokens or 0, self.max_output_tokens or 0) or None
        model = self.models.get(choice.provider, choice.model)
        return replace(choice, model=model, params=params, max_output_tokens=cap)


def reasoning_effort(task: AiTask, choice: RouteChoice) -> str | None:
    chosen = choice.params.get(REASONING_EFFORT_PARAM)
    if chosen in REASONING_EFFORTS:
        return chosen
    return TASK_REASONING_EFFORT.get(task)


@dataclass
class RouterResult:
    task: str
    provider: str
    model: str
    ordinal: int
    usage_event_id: uuid.UUID
    cost_usd: Decimal
    degraded: bool
    attempts: list[dict[str, Any]]
    text: str = ""
    embeddings: list[list[float]] | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    meta: dict[str, Any] = field(default_factory=dict)


class RouterError(AppError):
    def __init__(
        self,
        kind: str,
        message: str,
        *,
        reason: str | None = None,
        attempts: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.message = message
        self.reason = reason
        self.attempts = attempts or []


def output_tokens_for(choice: RouteChoice, requested: int | None = None) -> int:
    ceiling = output_limit(choice.provider, choice.model)
    wanted = requested or choice.max_output_tokens or ceiling or DEFAULT_MAX_OUTPUT_TOKENS
    return min(wanted, ceiling) if ceiling else wanted


def route_allowed(choice: RouteChoice, task: AiTask) -> bool:
    if choice.data_class == "PUBLIC_TEXT_ONLY" and task not in PUBLIC_TEXT_TASKS:
        return False
    return supports(choice.provider, choice.model, task)


def estimate_for(
    choice: RouteChoice,
    task: AiTask,
    *,
    prompt_tokens: int,
    max_tokens: int,
    units: float | None,
    overrides: dict[str, Any] | None,
) -> Decimal:
    model = model_for(choice.provider, choice.model)
    if task in MEDIA_TASKS:
        return budget.unit_cost(model, units if units is not None else 1.0, overrides)
    output = 0 if task == AiTask.EMBED else max_tokens
    return budget.token_cost(model, input_tokens=prompt_tokens, output_tokens=output, overrides=overrides)


def order_routes(
    task: AiTask,
    routes: Sequence[RouteChoice],
    *,
    degrade: bool,
    estimate: Callable[[RouteChoice], Decimal],
) -> list[RouteChoice]:
    usable = sorted((r for r in routes if route_allowed(r, task)), key=lambda r: r.ordinal)
    if degrade and task in DEGRADABLE_TASKS:
        usable = sorted(usable, key=lambda r: (estimate(r), r.ordinal))
    return usable


_semaphores: dict[str, asyncio.Semaphore] = {}


def _semaphore(choice: RouteChoice) -> asyncio.Semaphore:
    found = _semaphores.get(choice.provider)
    if found is None:
        found = asyncio.Semaphore(max(1, choice.max_concurrency))
        _semaphores[choice.provider] = found
    return found


async def load_routes(session: AsyncSession, task: AiTask) -> list[RouteChoice]:
    rows = (
        await session.execute(
            select(RoutePolicy, Provider)
            .join(Provider, Provider.id == RoutePolicy.providerId)
            .where(RoutePolicy.task == task.value, RoutePolicy.enabled.is_(True), Provider.enabled.is_(True))
            .order_by(RoutePolicy.ordinal)
        )
    ).all()
    return [
        RouteChoice(
            ordinal=route.ordinal,
            provider=provider.name,
            provider_id=provider.id,
            preset=provider.preset,
            kind=provider.kind,
            base_url=provider.baseUrl,
            key_name=provider.apiKeySecretKey,
            model=route.model,
            max_output_tokens=route.maxOutputTokens,
            temperature=route.temperature,
            max_concurrency=provider.maxConcurrency,
            data_class=provider.dataClass,
            learned=dict(provider.learned or {}),
            extra=dict(provider.extra or {}),
            params=dict(route.params or {}),
        )
        for route, provider in rows
    ]


def _spend_sum() -> Any:
    fresh_cutoff = func.now() - text(f"interval '{int(budget.RESERVATION_TTL.total_seconds())} seconds'")
    amount = case(
        (
            UsageEvent.outcome == "RESERVED",
            case((UsageEvent.createdAt > fresh_cutoff, UsageEvent.estimatedCostUsd), else_=Decimal(0)),
        ),
        else_=UsageEvent.costUsd,
    )
    return func.coalesce(func.sum(amount), 0)


async def current_spend(
    session: AsyncSession, principal: Principal, now: datetime | None = None
) -> budget.SpendState:
    month_from = budget.month_start(now)
    month_total = (
        await session.execute(select(_spend_sum()).where(UsageEvent.createdAt >= month_from))
    ).scalar_one()
    media_total = (
        await session.execute(
            select(_spend_sum()).where(UsageEvent.createdAt >= month_from, UsageEvent.isMedia.is_(True))
        )
    ).scalar_one()
    user_day = Decimal(0)
    if principal.user_id is not None:
        user_day = (
            await session.execute(
                select(_spend_sum()).where(
                    UsageEvent.createdAt >= budget.day_start(now), UsageEvent.userId == principal.user_id
                )
            )
        ).scalar_one()
    return budget.SpendState(
        month_usd=budget.usd(month_total),
        media_month_usd=budget.usd(media_total),
        user_day_usd=budget.usd(user_day),
    )


async def tagged_spend(session: AsyncSession, *, request_id_prefix: str, since: datetime) -> Decimal:
    if not request_id_prefix:
        raise ValueError("A tagged spend needs a request id prefix")
    escaped = request_id_prefix.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    total = (
        await session.execute(
            select(_spend_sum()).where(
                UsageEvent.createdAt >= since,
                UsageEvent.requestId.like(f"{escaped}%", escape="\\"),
            )
        )
    ).scalar_one()
    return budget.usd(total)


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
    event = _reserved_event(
        task, choice, principal, estimate_usd=estimate_usd, decision=decision, units=units
    )
    session.add(event)
    await session.flush()
    await session.commit()
    return event.id, decision


def _reserved_event(
    task: AiTask,
    choice: RouteChoice | None,
    principal: Principal,
    *,
    estimate_usd: Decimal,
    decision: budget.BudgetDecision,
    units: float | None,
) -> UsageEvent:
    return UsageEvent(
        userId=principal.user_id,
        role=principal.role,
        task=task.value,
        provider=choice.provider if choice else None,
        model=choice.model if choice else None,
        routeOrdinal=choice.ordinal if choice else None,
        estimatedCostUsd=estimate_usd if decision.allowed else Decimal(0),
        costUsd=Decimal(0),
        isMedia=task in MEDIA_TASKS,
        units=units,
        requestId=current_request_id(),
        outcome="RESERVED" if decision.allowed else "REFUSED_CEILING",
        errorKind=None if decision.allowed else decision.reason,
        settledAt=None if decision.allowed else datetime.now(UTC),
    )


async def settle(
    session: AsyncSession,
    event_id: uuid.UUID,
    *,
    outcome: str,
    cost_usd: Decimal = Decimal(0),
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    cached_tokens: int | None = None,
    latency_ms: int | None = None,
    error_kind: str | None = None,
    detail: dict[str, Any] | None = None,
    units: float | None = None,
    unit: str | None = None,
) -> None:
    values: dict[str, Any] = {
        "outcome": outcome,
        "costUsd": cost_usd,
        "inputTokens": input_tokens,
        "outputTokens": output_tokens,
        "cachedTokens": cached_tokens,
        "latencyMs": latency_ms,
        "errorKind": error_kind,
        "detail": detail,
        "settledAt": datetime.now(UTC),
    }
    if units is not None:
        values["units"] = units
    if unit is not None:
        values["unit"] = unit
    await session.execute(update(UsageEvent).where(UsageEvent.id == event_id).values(**values))
    await session.commit()


async def mark_key_failed(session: AsyncSession, key_name: str, value: str | None, message: str) -> None:
    now = datetime.now(UTC)
    result = await session.execute(
        update(ManagedSecret)
        .where(ManagedSecret.key == key_name)
        .values(lastStatus=managed_keys.STATUS_FAILED, lastCheckedAt=now, lastError=message[:500])
    )
    if not result.rowcount and value:
        payload = {
            "status": managed_keys.STATUS_FAILED,
            "checkedAt": now,
            "error": message[:500],
            "fingerprint": managed_keys.fingerprint(value),
        }
        await session.execute(
            insert(SecretTestResult)
            .values(key=key_name, **payload)
            .on_conflict_do_update(index_elements=[SecretTestResult.key], set_=payload)
        )
    await session.commit()
    managed_keys.invalidate()


async def _persist_learned(session: AsyncSession, choice: RouteChoice, adapter: Adapter) -> None:
    if not adapter.learned_changed or choice.provider_id is None:
        return
    row = await session.get(Provider, choice.provider_id, with_for_update=True)
    if row is not None:
        row.learned = merge_learned(row.learned, adapter.learned)
        await session.commit()


@dataclass
class _CallOutcome:
    text: str = ""
    embeddings: list[list[float]] | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cached_tokens: int | None = None
    latency_ms: int = 0
    meta: dict[str, Any] = field(default_factory=dict)


async def _call(adapter: Adapter, plan: _Plan, choice: RouteChoice) -> _CallOutcome:
    ask = plan.ask
    if ask.task == AiTask.EMBED:
        return await _embedded(adapter, choice, ask.texts or [])
    result: ChatResult = await adapter.chat(
        ChatRequest(
            model=choice.model,
            system=ask.system,
            user=ask.user,
            max_tokens=plan.output_cap(choice),
            temperature=ask.temperature if ask.temperature is not None else choice.temperature,
            reasoning_effort=reasoning_effort(ask.task, choice),
            json_schema=ask.json_schema,
        )
    )
    return _CallOutcome(
        text=result.text,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        cached_tokens=result.cached_input_tokens,
        latency_ms=result.latency_ms,
        meta=result.meta,
    )


async def _embedded(adapter: Adapter, choice: RouteChoice, texts: list[str]) -> _CallOutcome:
    started = time.perf_counter()
    vectors = await adapter.embed(texts, choice.model, dimensions=EMBED_DIMENSIONS)
    latency = int((time.perf_counter() - started) * 1000)
    return _CallOutcome(
        embeddings=vectors,
        input_tokens=sum(budget.estimate_tokens(text) for text in texts),
        output_tokens=0,
        latency_ms=latency,
        meta={"estimatedTokens": True},
    )


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


async def _settle_at_estimate(
    sessions: async_sessionmaker[AsyncSession], event_id: uuid.UUID, estimate_usd: Decimal
) -> None:
    async with sessions() as session:
        await settle(session, event_id, outcome="CANCELLED", cost_usd=estimate_usd, error_kind=ABANDONED_KIND)


@dataclass(frozen=True)
class _Ask:
    task: AiTask
    system: str
    user: str
    json_schema: dict | None
    max_tokens: int | None
    temperature: float | None
    texts: list[str] | None
    request_budget_usd: Decimal | None

    @property
    def prompt_tokens(self) -> int:
        if self.task == AiTask.EMBED and self.texts:
            return budget.estimate_tokens("\n".join(self.texts))
        return budget.estimate_tokens(f"{self.system}\n{self.user}")


@dataclass(frozen=True)
class _Plan:
    ask: _Ask
    routes: list[RouteChoice]
    overrides: dict[str, Any]
    degrade: bool

    def output_cap(self, choice: RouteChoice) -> int:
        return output_tokens_for(choice, self.ask.max_tokens)

    def estimate(self, choice: RouteChoice) -> Decimal:
        return estimate_for(
            choice,
            self.ask.task,
            prompt_tokens=self.ask.prompt_tokens,
            max_tokens=self.output_cap(choice),
            units=None,
            overrides=self.overrides,
        )

    def ordered(self) -> list[RouteChoice]:
        return order_routes(self.ask.task, self.routes, degrade=self.degrade, estimate=self.estimate)


@dataclass
class _Called:
    outcome: _CallOutcome | None = None
    failure: ProviderError | None = None
    adapter: Adapter | None = None


@dataclass(frozen=True)
class _Attempt:
    sessions: async_sessionmaker[AsyncSession]
    plan: _Plan
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
    ask = _Ask(resolved, system, user, json_schema, max_tokens, temperature, texts, request_budget_usd)
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
    sessions: async_sessionmaker[AsyncSession], ask: _Ask, who: Principal, tuning: RouteTuning | None
) -> _Plan:
    async with sessions() as session:
        loaded = await load_routes(session, ask.task)
        settings_values = await spend_settings.load_spend_settings(session)
        spend = await current_spend(session, who)
        await managed_keys.refresh_if_stale(session)
    ceilings = budget.Ceilings.from_settings(settings_values)
    return _Plan(
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


async def _called(plan: _Plan, choice: RouteChoice) -> _Called:
    called = _Called()
    for retry in range(2):
        try:
            called.adapter = _adapter(choice)
            async with _semaphore(choice):
                called.outcome = await _call(called.adapter, plan, choice)
            called.failure = None
            return called
        except ProviderError as exc:
            called.failure = exc
            if retry > 0 or not _worth_one_retry(exc):
                return called
            await asyncio.sleep(exc.retry_after or 0)
        finally:
            await _closed(called.adapter)
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


def _worth_one_retry(failure: ProviderError) -> bool:
    wait = failure.retry_after
    return failure.kind in RETRYABLE_KINDS and wait is not None and wait <= RETRY_AFTER_CAP_SECONDS


async def _closed(adapter: Adapter | None) -> None:
    if adapter is None:
        return
    try:
        await adapter.aclose()
    except Exception:
        logger.debug("adapter close failed", exc_info=True)


async def _succeeded(
    attempt: _Attempt, event_id: uuid.UUID, called: _Called, outcome: _CallOutcome
) -> RouterResult:
    choice, plan = attempt.choice, attempt.plan
    cost = _cost(plan, choice, outcome)
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
            await _persist_learned(session, choice, called.adapter)
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


def _cost(plan: _Plan, choice: RouteChoice, outcome: _CallOutcome) -> Decimal:
    return budget.token_cost(
        model_for(choice.provider, choice.model),
        input_tokens=outcome.input_tokens,
        output_tokens=outcome.output_tokens,
        cached_tokens=outcome.cached_tokens,
        overrides=plan.overrides,
    )


async def _failed(attempt: _Attempt, event_id: uuid.UUID, called: _Called, failure: ProviderError) -> None:
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
            await _persist_learned(session, choice, called.adapter)
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
