from __future__ import annotations

import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from decimal import Decimal
from typing import Any

from app.core.errors import AppError
from app.providers.catalogue import MEDIA_TASKS, PUBLIC_TEXT_TASKS, AiTask, model_for, output_limit, supports

from . import budget

__all__ = [
    "DEFAULT_MAX_OUTPUT_TOKENS",
    "DEGRADABLE_TASKS",
    "REASONING_EFFORTS",
    "REASONING_EFFORT_PARAM",
    "TASK_REASONING_EFFORT",
    "Principal",
    "RouteChoice",
    "RouteTuning",
    "RouterError",
    "RouterResult",
    "estimate_for",
    "order_routes",
    "output_tokens_for",
    "reasoning_effort",
    "route_allowed",
]

DEFAULT_MAX_OUTPUT_TOKENS = 4096
DEGRADABLE_TASKS = frozenset(
    {AiTask.COMPOSE, AiTask.EXTRACT, AiTask.VOICE_TURN, AiTask.PLAN, AiTask.UNDERSTAND, AiTask.WEB_READ}
)
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
