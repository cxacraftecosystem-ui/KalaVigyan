from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .judge_ladder import JudgeLadder
from .reranking import Reranker
from .structured import StructuredModel

__all__ = ["AnswerModels", "DepthFollower"]

DepthFollower = Callable[[str], None]


@dataclass(frozen=True)
class AnswerModels:
    understand: StructuredModel
    plan: StructuredModel
    compose: StructuredModel
    builder_plan: StructuredModel
    builder_compose: StructuredModel
    explainer: StructuredModel
    translate: StructuredModel
    judge: JudgeLadder | None = None
    rerank: Reranker | None = None
    follow_depth: DepthFollower | None = None
