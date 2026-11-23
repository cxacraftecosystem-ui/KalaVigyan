from __future__ import annotations

from collections.abc import Iterable, Mapping
from types import MappingProxyType

from app.research.judge_ladder import JudgeLadder

from .budget import RequestBudget
from .catalogue import PROVIDERS, AiModel, AiTask, ProviderSpec, supports
from .router import Principal, RouteTuning
from .structured import router_structured_model

__all__ = ["JUDGE_TASK", "cheapest_judge_models", "cheapest_model", "thrifty_judges"]

JUDGE_TASK = AiTask.EVAL_JUDGE


def thrifty_judges(
    principal: Principal | None = None, *, request_budget_usd: RequestBudget | None = None
) -> JudgeLadder:
    cheapest = RouteTuning(models=dict(cheapest_judge_models()))
    return JudgeLadder(
        first=router_structured_model(
            JUDGE_TASK, principal, tuning=cheapest, request_budget_usd=request_budget_usd
        ),
        escalate=(router_structured_model(JUDGE_TASK, principal, request_budget_usd=request_budget_usd),),
    )


def cheapest_model(spec: ProviderSpec, task: AiTask = JUDGE_TASK) -> AiModel | None:
    priced = [
        model
        for model in spec.models
        if model.price_per_mtok is not None
        and model.price_verified
        and supports(spec.provider, model.id, task)
    ]
    return min(priced, key=_price_key, default=None)


def cheapest_judge_models(specs: Iterable[ProviderSpec] | None = None) -> Mapping[str, str]:
    chosen = {}
    for spec in specs if specs is not None else PROVIDERS.values():
        model = cheapest_model(spec)
        if model is not None:
            chosen[spec.provider.value] = model.id
    return MappingProxyType(chosen)


def _price_key(model: AiModel) -> tuple[float, str]:
    price_in, price_out = model.price_per_mtok or (0.0, 0.0)
    return price_in + price_out, model.id
