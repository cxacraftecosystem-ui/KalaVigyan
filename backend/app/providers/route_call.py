from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from app.core.errors import RETRYABLE_KINDS
from app.providers.catalogue import AiTask, model_for

from . import budget
from .base import Adapter, ChatRequest, ChatResult, ProviderError
from .route_choice import RouteChoice, estimate_for, order_routes, output_tokens_for, reasoning_effort

__all__ = [
    "EMBED_DIMENSIONS",
    "RETRY_AFTER_CAP_SECONDS",
    "Ask",
    "CallOutcome",
    "Called",
    "Plan",
    "call_cost",
    "call_route",
    "close_adapter",
    "worth_one_retry",
]

logger = logging.getLogger(__name__)

EMBED_DIMENSIONS = 1536
RETRY_AFTER_CAP_SECONDS = 2.0


@dataclass(frozen=True)
class Ask:
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
class Plan:
    ask: Ask
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
class CallOutcome:
    text: str = ""
    embeddings: list[list[float]] | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cached_tokens: int | None = None
    latency_ms: int = 0
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class Called:
    outcome: CallOutcome | None = None
    failure: ProviderError | None = None
    adapter: Adapter | None = None


async def call_route(adapter: Adapter, plan: Plan, choice: RouteChoice) -> CallOutcome:
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
    return CallOutcome(
        text=result.text,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        cached_tokens=result.cached_input_tokens,
        latency_ms=result.latency_ms,
        meta=result.meta,
    )


def call_cost(plan: Plan, choice: RouteChoice, outcome: CallOutcome) -> Decimal:
    return budget.token_cost(
        model_for(choice.provider, choice.model),
        input_tokens=outcome.input_tokens,
        output_tokens=outcome.output_tokens,
        cached_tokens=outcome.cached_tokens,
        overrides=plan.overrides,
    )


def worth_one_retry(failure: ProviderError) -> bool:
    wait = failure.retry_after
    return failure.kind in RETRYABLE_KINDS and wait is not None and wait <= RETRY_AFTER_CAP_SECONDS


async def close_adapter(adapter: Adapter | None) -> None:
    if adapter is None:
        return
    try:
        await adapter.aclose()
    except Exception:
        logger.debug("adapter close failed", exc_info=True)


async def _embedded(adapter: Adapter, choice: RouteChoice, texts: list[str]) -> CallOutcome:
    started = time.perf_counter()
    vectors = await adapter.embed(texts, choice.model, dimensions=EMBED_DIMENSIONS)
    latency = int((time.perf_counter() - started) * 1000)
    return CallOutcome(
        embeddings=vectors,
        input_tokens=sum(budget.estimate_tokens(text) for text in texts),
        output_tokens=0,
        latency_ms=latency,
        meta={"estimatedTokens": True},
    )
