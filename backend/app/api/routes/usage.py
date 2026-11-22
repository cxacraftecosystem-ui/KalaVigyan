import re
from datetime import UTC, date, datetime, time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import INDIA_TZ, INDIA_TZ_NAME
from app.core.db import get_session
from app.core.deps import get_current_user, require
from app.core.roles import ALLOWANCE_RESOURCES, Capability, daily_allowance, is_uncapped
from app.models import UsageEvent, User
from app.providers import budget
from app.providers.catalogue import TASK_LABELS, spec_for, task_of
from app.providers.router import Principal, current_spend
from app.services import app_settings

router = APIRouter(prefix="/usage", tags=["usage"])

usage_reader = require(Capability.VIEW_USAGE)

MONTH_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _month_bounds(month: str | None) -> tuple[str, datetime, datetime]:
    if month is None:
        start = budget.month_start()
        local = start.astimezone(INDIA_TZ)
        label = f"{local.year:04d}-{local.month:02d}"
    else:
        if not MONTH_PATTERN.fullmatch(month):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "month must look like 2026-11")
        label = month
        year, number = int(month[:4]), int(month[5:])
        start = datetime.combine(date(year, number, 1), time.min, tzinfo=INDIA_TZ).astimezone(UTC)
    local = start.astimezone(INDIA_TZ)
    next_year, next_month = (local.year + 1, 1) if local.month == 12 else (local.year, local.month + 1)
    end = datetime.combine(date(next_year, next_month, 1), time.min, tzinfo=INDIA_TZ).astimezone(UTC)
    return label, start, end


def _money(value: Any) -> float:
    return float(budget.usd(value))


def _cap(value: Any) -> float | None:
    return None if value is None else _money(value)


@router.get("/summary")
async def usage_summary(
    month: str | None = Query(default=None),
    _: User = Depends(usage_reader),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    label, start, end = _month_bounds(month)
    window = (UsageEvent.createdAt >= start, UsageEvent.createdAt < end)
    settled = UsageEvent.outcome != "RESERVED"
    settings_values = await app_settings.load_all(session)
    ceilings = budget.Ceilings.from_settings(settings_values)

    async def grouped(column: Any) -> list[dict[str, Any]]:
        rows = (
            await session.execute(
                select(
                    column,
                    func.coalesce(func.sum(UsageEvent.costUsd), 0),
                    func.count(),
                    func.coalesce(func.sum(UsageEvent.inputTokens), 0),
                    func.coalesce(func.sum(UsageEvent.outputTokens), 0),
                    func.sum(case((UsageEvent.outcome == "OK", 1), else_=0)),
                )
                .where(*window, settled)
                .group_by(column)
                .order_by(func.sum(UsageEvent.costUsd).desc())
            )
        ).all()
        return [
            {
                "key": key,
                "costUsd": _money(cost),
                "calls": calls,
                "inputTokens": int(tin),
                "outputTokens": int(tout),
                "ok": int(ok or 0),
            }
            for key, cost, calls, tin, tout, ok in rows
        ]

    totals = (
        await session.execute(
            select(
                func.coalesce(func.sum(UsageEvent.costUsd), 0),
                func.coalesce(func.sum(case((UsageEvent.isMedia.is_(True), UsageEvent.costUsd), else_=0)), 0),
                func.sum(case((UsageEvent.outcome == "REFUSED_CEILING", 1), else_=0)),
                func.sum(case((UsageEvent.outcome == "ERROR", 1), else_=0)),
                func.count(),
            ).where(*window, settled)
        )
    ).one()
    reserved = (
        await session.execute(
            select(func.coalesce(func.sum(UsageEvent.estimatedCostUsd), 0)).where(
                *window, UsageEvent.outcome == "RESERVED"
            )
        )
    ).scalar_one()
    day = func.date_trunc("day", func.timezone(INDIA_TZ_NAME, UsageEvent.createdAt))
    by_day = (
        await session.execute(
            select(day, func.coalesce(func.sum(UsageEvent.costUsd), 0), func.count())
            .where(*window, settled)
            .group_by(day)
            .order_by(day)
        )
    ).all()
    spent = budget.usd(totals[0])
    fraction = budget.month_fraction(ceilings, budget.SpendState(month_usd=spent))
    top_users = (
        await session.execute(
            select(User.id, User.name, User.email, User.role, func.sum(UsageEvent.costUsd), func.count())
            .join(User, User.id == UsageEvent.userId)
            .where(*window, settled)
            .group_by(User.id, User.name, User.email, User.role)
            .order_by(func.sum(UsageEvent.costUsd).desc())
            .limit(20)
        )
    ).all()
    return {
        "month": label,
        "monthlyCeilingUsd": _cap(ceilings.monthly_usd),
        "mediaCapUsd": _cap(ceilings.media_usd),
        "spentUsd": float(spent),
        "mediaSpentUsd": _money(totals[1]),
        "reservedUsd": _money(reserved),
        "fraction": None if fraction is None else round(float(fraction), 4),
        "degraded": budget.past_degrade_mark(ceilings, budget.SpendState(month_usd=spent)),
        "calls": int(totals[4] or 0),
        "refusedCalls": int(totals[2] or 0),
        "failedCalls": int(totals[3] or 0),
        "byTask": await grouped(UsageEvent.task),
        "byProvider": await grouped(UsageEvent.provider),
        "byModel": await grouped(UsageEvent.model),
        "byRole": await grouped(UsageEvent.role),
        "byDay": [
            {"day": d.date().isoformat(), "costUsd": _money(cost), "calls": calls}
            for d, cost, calls in by_day
        ],
        "topUsers": [
            {
                "userId": str(uid),
                "name": name,
                "email": email,
                "role": role,
                "costUsd": _money(cost),
                "calls": calls,
            }
            for uid, name, email, role, cost, calls in top_users
        ],
    }


def _instant(value: str | None, *, fallback: datetime) -> datetime:
    if not value:
        return fallback
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "from and to must be ISO dates") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=INDIA_TZ)
    return parsed.astimezone(UTC)


def _task_label(task: str) -> str:
    resolved = task_of(task)
    return TASK_LABELS.get(resolved, task) if resolved is not None else task


@router.get("/report")
async def usage_report(
    date_from: str | None = Query(default=None, alias="from", max_length=40),
    date_to: str | None = Query(default=None, alias="to", max_length=40),
    _: User = Depends(usage_reader),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    _label, month_start, _end = _month_bounds(None)
    now = datetime.now(UTC)
    start = _instant(date_from, fallback=month_start)
    end = _instant(date_to, fallback=now)
    if end < start:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "to must be after from")
    settled = UsageEvent.outcome != "RESERVED"
    window = (UsageEvent.createdAt >= start, UsageEvent.createdAt <= end, settled)
    failed = func.sum(case((UsageEvent.outcome == "ERROR", 1), else_=0))
    cost = func.coalesce(func.sum(UsageEvent.costUsd), 0)
    ceilings = budget.Ceilings.from_settings(await app_settings.load_all(session))
    month_spent = (
        await session.execute(
            select(cost).where(UsageEvent.createdAt >= month_start, UsageEvent.createdAt <= now, settled)
        )
    ).scalar_one()
    totals = (await session.execute(select(cost, func.count(), failed).where(*window))).one()
    by_task = (
        await session.execute(
            select(
                UsageEvent.task,
                func.count(),
                failed,
                func.coalesce(func.sum(UsageEvent.inputTokens), 0),
                func.coalesce(func.sum(UsageEvent.outputTokens), 0),
                cost,
            )
            .where(*window)
            .group_by(UsageEvent.task)
            .order_by(cost.desc())
        )
    ).all()
    p95 = func.percentile_cont(0.95).within_group(UsageEvent.latencyMs)
    by_provider = (
        await session.execute(
            select(UsageEvent.provider, UsageEvent.model, func.count(), failed, cost, p95)
            .where(*window)
            .group_by(UsageEvent.provider, UsageEvent.model)
            .order_by(cost.desc())
        )
    ).all()
    day = func.date_trunc("day", func.timezone(INDIA_TZ_NAME, UsageEvent.createdAt))
    by_day = (
        await session.execute(select(day, func.count(), cost).where(*window).group_by(day).order_by(day))
    ).all()

    def provider_name(provider: str | None) -> str:
        spec = spec_for(provider) if provider else None
        return spec.label if spec else (provider or "Unknown")

    return {
        "from": start.isoformat(),
        "to": end.isoformat(),
        "ceilingUsd": _cap(ceilings.monthly_usd),
        "spentThisMonthUsd": _money(month_spent),
        "spentUsd": _money(totals[0]),
        "calls": int(totals[1] or 0),
        "failures": int(totals[2] or 0),
        "byTask": [
            {
                "task": task,
                "label": _task_label(task),
                "calls": int(calls),
                "failures": int(fails or 0),
                "inputTokens": int(tin),
                "outputTokens": int(tout),
                "costUsd": _money(spent),
            }
            for task, calls, fails, tin, tout, spent in by_task
        ],
        "byProvider": [
            {
                "provider": provider or "UNKNOWN",
                "name": provider_name(provider),
                "model": model or "",
                "calls": int(calls),
                "failures": int(fails or 0),
                "costUsd": _money(spent),
                "p95LatencyMs": round(latency) if latency is not None else None,
            }
            for provider, model, calls, fails, spent, latency in by_provider
        ],
        "byDay": [
            {"day": d.date().isoformat(), "calls": int(calls), "costUsd": _money(spent)}
            for d, calls, spent in by_day
        ],
    }


@router.get("/me")
async def my_usage(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    settings_values = await app_settings.load_all(session)
    ceilings = budget.Ceilings.from_settings(settings_values)
    spend = await current_spend(session, Principal(user_id=user.id, role=user.role))
    return {
        "todayUsd": float(spend.user_day_usd),
        "dailyCapUsd": None if is_uncapped(user) else _cap(ceilings.role_cap(user.role)),
        "allowances": {resource: daily_allowance(user, resource) for resource in ALLOWANCE_RESOURCES},
        "platformDegraded": budget.past_degrade_mark(ceilings, spend),
    }
