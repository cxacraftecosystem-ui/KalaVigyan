from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import case, func, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import managed_keys
from app.core.logging import current_request_id
from app.models import ManagedSecret, Provider, RoutePolicy, SecretTestResult, UsageEvent
from app.providers.catalogue import MEDIA_TASKS, AiTask

from . import budget
from .base import Adapter
from .registry import merge_learned
from .route_choice import Principal, RouteChoice

__all__ = [
    "current_spend",
    "load_routes",
    "mark_key_failed",
    "persist_learned",
    "reserved_event",
    "settle",
    "tagged_settled_spend",
    "tagged_spend",
]


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
    total = (
        await session.execute(select(_spend_sum()).where(*_tagged(request_id_prefix, since)))
    ).scalar_one()
    return budget.usd(total)


async def tagged_settled_spend(session: AsyncSession, *, request_id_prefix: str, since: datetime) -> Decimal:
    settled = func.coalesce(func.sum(UsageEvent.costUsd), 0)
    total = (await session.execute(select(settled).where(*_tagged(request_id_prefix, since)))).scalar_one()
    return budget.usd(total)


def _tagged(request_id_prefix: str, since: datetime) -> tuple[Any, ...]:
    if not request_id_prefix:
        raise ValueError("A tagged spend needs a request id prefix")
    escaped = request_id_prefix.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return UsageEvent.createdAt >= since, UsageEvent.requestId.like(f"{escaped}%", escape="\\")


def reserved_event(
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


async def persist_learned(session: AsyncSession, choice: RouteChoice, adapter: Adapter) -> None:
    if not adapter.learned_changed or choice.provider_id is None:
        return
    row = await session.get(Provider, choice.provider_id, with_for_update=True)
    if row is not None:
        row.learned = merge_learned(row.learned, adapter.learned)
        await session.commit()


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
