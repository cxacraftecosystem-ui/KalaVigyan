from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from app.providers.catalogue import AiProvider, AiTask
from app.research.answer_models import AnswerModels, DepthFollower

from .budget import AnswerSpend
from .rerank_router import router_reranker
from .router import Principal, RouteTuning
from .structured import router_structured_model

__all__ = [
    "BUILDER_MODEL",
    "BUILDER_TUNING",
    "COMPOSE_TUNINGS",
    "EXPERT_MODEL",
    "EXPLAINER_TUNINGS",
    "answer_models",
    "depth_follower",
]

EXPERT_MODEL = "claude-opus-5-5"
BUILDER_MODEL = "claude-sonnet-5-5"
EXPERT_EFFORT = "high"
_ANTHROPIC = AiProvider.ANTHROPIC.value

BUILDER_TUNING = RouteTuning(models={_ANTHROPIC: BUILDER_MODEL})
COMPOSE_TUNINGS: Mapping[str, RouteTuning] = MappingProxyType(
    {
        "BASIC": RouteTuning(),
        "DETAILED": RouteTuning(),
        "EXPERT": RouteTuning(models={_ANTHROPIC: EXPERT_MODEL}, effort=EXPERT_EFFORT),
    }
)
EXPLAINER_TUNINGS: Mapping[str, RouteTuning] = MappingProxyType(
    {
        "BASIC": RouteTuning(models={_ANTHROPIC: BUILDER_MODEL}),
        "DETAILED": RouteTuning(models={_ANTHROPIC: BUILDER_MODEL}),
        "EXPERT": RouteTuning(models={_ANTHROPIC: EXPERT_MODEL}, effort=EXPERT_EFFORT),
    }
)


def answer_models(depth: str, *, principal: Principal, optional: Principal) -> AnswerModels:
    return AnswerModels(
        understand=router_structured_model(AiTask.UNDERSTAND, principal),
        plan=router_structured_model(AiTask.PLAN, principal),
        compose=router_structured_model(AiTask.COMPOSE, principal, tuning=COMPOSE_TUNINGS[depth]),
        builder_plan=router_structured_model(AiTask.PLAN, optional),
        builder_compose=router_structured_model(AiTask.COMPOSE, optional, tuning=BUILDER_TUNING),
        explainer=router_structured_model(AiTask.COMPOSE, optional, tuning=EXPLAINER_TUNINGS[depth]),
        translate=router_structured_model(AiTask.TRANSLATE, principal),
        judge=router_structured_model(AiTask.EVAL_JUDGE, optional),
        rerank=router_reranker(principal),
        follow_depth=depth_follower(principal),
    )


def depth_follower(principal: Principal) -> DepthFollower | None:
    answer = principal.answer
    return answer.follow if isinstance(answer, AnswerSpend) else None
