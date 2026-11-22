from __future__ import annotations

from dataclasses import dataclass

from .reranking import Reranker
from .structured import StructuredModel

__all__ = ["AnswerModels"]


@dataclass(frozen=True)
class AnswerModels:
    plan: StructuredModel
    compose: StructuredModel
    builder_plan: StructuredModel
    builder_compose: StructuredModel
    explainer: StructuredModel
    translate: StructuredModel
    judge: StructuredModel | None = None
    rerank: Reranker | None = None
