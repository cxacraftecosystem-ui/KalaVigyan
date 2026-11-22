from __future__ import annotations

from app.research.embedding import TextEmbedder, checked_vectors

from . import router
from .budget import RequestBudget, request_budget_now
from .catalogue import AiTask
from .router import Principal

__all__ = ["router_embedder"]


def router_embedder(
    principal: Principal | None = None, *, request_budget_usd: RequestBudget | None = None
) -> TextEmbedder:
    async def embed(texts: list[str]) -> list[list[float]]:
        result = await router.run(
            AiTask.EMBED,
            texts=texts,
            principal=principal,
            request_budget_usd=await request_budget_now(request_budget_usd),
        )
        return checked_vectors(result.embeddings, expected=len(texts))

    return embed
