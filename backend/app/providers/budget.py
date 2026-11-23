from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from app.core.clock import INDIA_TZ
from app.core.roles import LOWEST_ROLE, is_uncapped

from . import spend_settings as keys
from .catalogue import UNKNOWN_TOKEN_PRICE, UNKNOWN_UNIT_PRICE, AiModel

CACHED_INPUT_FRACTION = Decimal("0.25")
OPTIONAL_WORK_KEEPS = Decimal("0.5")
RESERVATION_TTL = timedelta(minutes=15)
MICRO = Decimal("0.000001")
MILLION = Decimal(1_000_000)

MONTHLY_CEILING = "MONTHLY_CEILING"
MEDIA_CAP = "MEDIA_CAP"
ROLE_DAILY_CAP = "ROLE_DAILY_CAP"
REQUEST_BUDGET = "REQUEST_BUDGET"
ANSWER_CAP = "ANSWER_CAP"

REFUSAL_MESSAGES = {
    MONTHLY_CEILING: "The monthly AI budget has been reached. Verified answers from stored knowledge still work.",
    MEDIA_CAP: "The monthly budget for images and video has been reached.",
    ROLE_DAILY_CAP: "You have reached today's AI allowance for your role. It resets at midnight IST.",
    REQUEST_BUDGET: "This request would cost more than its budget allows.",
    ANSWER_CAP: "This answer reached the cost limit for its depth.",
}


RequestBudget = Callable[[], Awaitable[Decimal]]


async def request_budget_now(budget: RequestBudget | None) -> Decimal | None:
    return None if budget is None else await budget()


def usd(value: Any) -> Decimal:
    return Decimal(str(value or 0)).quantize(MICRO, rounding=ROUND_HALF_UP)


def cap_usd(value: Any) -> Decimal | None:
    return None if value is None else usd(value)


@dataclass(frozen=True)
class Ceilings:
    monthly_usd: Decimal | None
    media_usd: Decimal | None
    role_daily_usd: dict[str, Decimal | None]
    degrade_at: Decimal | None
    answer_usd: dict[str, Decimal | None]

    @classmethod
    def from_settings(cls, values: dict[str, Any]) -> Ceilings:
        role_caps = keys.stored_spend_value(keys.ROLE_DAILY_USD, values.get(keys.ROLE_DAILY_USD) or {})
        answer_caps = values.get(keys.ANSWER_CAP_USD) or {}
        degrade_at = values.get(keys.DEGRADE_AT_FRACTION)
        return cls(
            monthly_usd=cap_usd(values.get(keys.MONTHLY_CEILING_USD)),
            media_usd=cap_usd(values.get(keys.MEDIA_CAP_USD)),
            role_daily_usd={role: cap_usd(cap) for role, cap in role_caps.items()},
            degrade_at=None if degrade_at is None else Decimal(str(degrade_at)),
            answer_usd={depth: cap_usd(cap) for depth, cap in answer_caps.items()},
        )

    def role_cap(self, role: str | None) -> Decimal | None:
        if not role:
            return None
        return self.role_daily_usd.get(role, self.role_daily_usd.get(LOWEST_ROLE))


@dataclass(frozen=True)
class SpendState:
    month_usd: Decimal = Decimal(0)
    media_month_usd: Decimal = Decimal(0)
    user_day_usd: Decimal = Decimal(0)


@dataclass(eq=False)
class AnswerSpend:
    depth: str
    held_usd: Decimal = Decimal(0)
    spent_usd: Decimal = Decimal(0)

    def left(self, ceilings: Ceilings) -> Decimal | None:
        if self.depth not in ceilings.answer_usd:
            return Decimal(0)
        cap = ceilings.answer_usd[self.depth]
        if cap is None:
            return None
        return cap - self.held_usd - self.spent_usd

    def follow(self, depth: str) -> None:
        self.depth = depth

    def hold(self, amount: Decimal) -> None:
        self.held_usd += amount

    def settle(self, held: Decimal, cost: Decimal) -> None:
        self.held_usd -= held
        self.spent_usd += cost

    def release(self, held: Decimal) -> None:
        self.held_usd -= held

    def headroom(self, keeps: Decimal = OPTIONAL_WORK_KEEPS) -> AnswerHeadroom:
        return AnswerHeadroom(self, keeps)


@dataclass(eq=False)
class AnswerHeadroom:
    answer: AnswerSpend
    keeps: Decimal

    def left(self, ceilings: Ceilings) -> Decimal | None:
        left = self.answer.left(ceilings)
        cap = ceilings.answer_usd.get(self.answer.depth)
        if left is None or cap is None:
            return left
        return left - cap * self.keeps

    def hold(self, amount: Decimal) -> None:
        self.answer.hold(amount)

    def settle(self, held: Decimal, cost: Decimal) -> None:
        self.answer.settle(held, cost)

    def release(self, held: Decimal) -> None:
        self.answer.release(held)


@dataclass(frozen=True)
class BudgetDecision:
    allowed: bool
    reason: str | None
    degrade: bool
    month_fraction: Decimal | None

    @property
    def message(self) -> str | None:
        return REFUSAL_MESSAGES.get(self.reason or "")


def month_fraction(ceilings: Ceilings, spend: SpendState) -> Decimal | None:
    if ceilings.monthly_usd is None:
        return None
    if ceilings.monthly_usd <= 0:
        return Decimal(1)
    return spend.month_usd / ceilings.monthly_usd


def past_degrade_mark(ceilings: Ceilings, spend: SpendState) -> bool:
    fraction = month_fraction(ceilings, spend)
    return ceilings.degrade_at is not None and fraction is not None and fraction >= ceilings.degrade_at


def degrades(ceilings: Ceilings, spend: SpendState, *, role: str | None) -> bool:
    return not is_uncapped(role) and past_degrade_mark(ceilings, spend)


def over(cap: Decimal | None, spent: Decimal, estimate: Decimal) -> bool:
    return cap is not None and spent + estimate > cap


def evaluate(
    ceilings: Ceilings,
    spend: SpendState,
    *,
    estimate_usd: Decimal,
    is_media: bool,
    role: str | None,
    request_budget_usd: Decimal | None = None,
    answer_left_usd: Decimal | None = None,
) -> BudgetDecision:
    fraction = month_fraction(ceilings, spend)
    degrade = degrades(ceilings, spend, role=role)

    def refuse(reason: str) -> BudgetDecision:
        return BudgetDecision(False, reason, degrade, fraction)

    if estimate_usd <= 0 or is_uncapped(role):
        return BudgetDecision(True, None, degrade, fraction)
    if over(request_budget_usd, Decimal(0), estimate_usd):
        return refuse(REQUEST_BUDGET)
    if over(answer_left_usd, Decimal(0), estimate_usd):
        return refuse(ANSWER_CAP)
    if over(ceilings.monthly_usd, spend.month_usd, estimate_usd):
        return refuse(MONTHLY_CEILING)
    if is_media and over(ceilings.media_usd, spend.media_month_usd, estimate_usd):
        return refuse(MEDIA_CAP)
    if over(ceilings.role_cap(role), spend.user_day_usd, estimate_usd):
        return refuse(ROLE_DAILY_CAP)
    return BudgetDecision(True, None, degrade, fraction)


def token_price(
    model: AiModel | None, day: date, overrides: dict[str, Any] | None = None
) -> tuple[Decimal, Decimal]:
    override = (overrides or {}).get(model.id) if model else None
    if isinstance(override, dict) and "in" in override and "out" in override:
        return Decimal(str(override["in"])), Decimal(str(override["out"]))
    price = model.token_price_on(day) if model else None
    chosen = price if price is not None else UNKNOWN_TOKEN_PRICE
    return Decimal(str(chosen[0])), Decimal(str(chosen[1]))


def unit_price(model: AiModel | None, overrides: dict[str, Any] | None = None) -> tuple[Decimal, str]:
    override = (overrides or {}).get(model.id) if model else None
    unit = (model.unit if model else None) or "image"
    if isinstance(override, dict) and "unit" in override:
        return Decimal(str(override["unit"])), unit
    if model is not None and model.price_per_unit is not None:
        return Decimal(str(model.price_per_unit)), unit
    return Decimal(str(UNKNOWN_UNIT_PRICE.get(unit, UNKNOWN_UNIT_PRICE["image"]))), unit


def token_cost(
    model: AiModel | None,
    *,
    input_tokens: int | None,
    output_tokens: int | None,
    cached_tokens: int | None = None,
    media_tokens: int | None = None,
    day: date | None = None,
    overrides: dict[str, Any] | None = None,
) -> Decimal:
    price_in, price_out = token_price(model, day or budget_today(), overrides)
    total_in = Decimal(max(0, input_tokens or 0))
    cached = min(Decimal(max(0, cached_tokens or 0)), total_in)
    billed_in = (total_in - cached) * price_in + cached * price_in * CACHED_INPUT_FRACTION
    total_out = Decimal(max(0, output_tokens or 0))
    price_media = media_token_price(model, overrides)
    if price_media is None:
        return usd((billed_in + total_out * price_out) / MILLION)
    media = total_out if media_tokens is None else min(Decimal(max(0, media_tokens)), total_out)
    billed_out = media * price_media + (total_out - media) * price_out
    return usd((billed_in + billed_out) / MILLION)


def media_token_price(model: AiModel | None, overrides: dict[str, Any] | None = None) -> Decimal | None:
    override = (overrides or {}).get(model.id) if model else None
    if isinstance(override, dict) and "media" in override:
        return Decimal(str(override["media"]))
    if model is None or model.media_price_per_mtok is None:
        return None
    return Decimal(str(model.media_price_per_mtok))


def unit_cost(model: AiModel | None, units: float, overrides: dict[str, Any] | None = None) -> Decimal:
    price, _unit = unit_price(model, overrides)
    return usd(price * Decimal(str(max(0.0, units))))


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 3)


def budget_today(now: datetime | None = None) -> date:
    return (now or datetime.now(UTC)).astimezone(INDIA_TZ).date()


def month_start(now: datetime | None = None) -> datetime:
    local = (now or datetime.now(UTC)).astimezone(INDIA_TZ)
    return datetime.combine(local.date().replace(day=1), time.min, tzinfo=INDIA_TZ).astimezone(UTC)


def day_start(now: datetime | None = None) -> datetime:
    local = (now or datetime.now(UTC)).astimezone(INDIA_TZ)
    return datetime.combine(local.date(), time.min, tzinfo=INDIA_TZ).astimezone(UTC)
