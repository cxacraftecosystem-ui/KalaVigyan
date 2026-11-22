from __future__ import annotations

import logging
import uuid
from collections.abc import Callable, Mapping, Sequence
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core import managed_keys
from app.core.errors import SPEND_REFUSAL_KIND, STOP_KINDS
from app.providers.catalogue import AiTask, model_for
from app.research.reranking import Relevance

from . import budget, spend_settings
from .base import Adapter, ProviderError, RerankRequest, RerankResult
from .registry import build_adapter
from .router import (
    Principal,
    RouteChoice,
    RouterError,
    load_routes,
    mark_key_failed,
    order_routes,
    reserve,
    settle,
    settle_abandoned,
)

__all__ = ["NO_KEY_KIND", "RerankRouter", "rerank_cost", "rerank_tokens", "router_reranker"]

logger = logging.getLogger(__name__)

NO_KEY_KIND = "no_key"

AdapterFactory = Callable[[RouteChoice, str], Adapter]
KeyLookup = Callable[[str], str | None]


def rerank_tokens(query: str, documents: Sequence[str]) -> int:
    query_tokens = budget.estimate_tokens(query)
    return query_tokens * len(documents) + sum(budget.estimate_tokens(document) for document in documents)


def router_reranker(principal: Principal | None = None) -> RerankRouter:
    return RerankRouter(principal=principal or Principal())


class RerankRouter:
    def __init__(
        self,
        *,
        principal: Principal,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
        adapter_factory: AdapterFactory | None = None,
        keys: KeyLookup = managed_keys.peek_secret,
    ) -> None:
        self._principal = principal
        self._session_factory = session_factory
        self._adapter_factory = adapter_factory or _built_adapter
        self._keys = keys

    async def __call__(self, query: str, documents: Sequence[str]) -> list[Relevance]:
        choices, overrides = await self._routes()
        keyed = self._keyed(choices)
        if not keyed:
            raise RouterError(NO_KEY_KIND, "No enabled rerank route has a key")
        attempts: list[dict[str, Any]] = []
        for choice, key in keyed:
            try:
                return await self._call(
                    choice, key, RerankRequest(choice.model, query, tuple(documents)), overrides
                )
            except ProviderError as failure:
                attempts.append({"provider": choice.provider, "model": choice.model, "outcome": failure.kind})
                logger.warning("rerank route failed", extra={"model": choice.model, "kind": failure.kind})
                if failure.kind in STOP_KINDS:
                    raise RouterError(failure.kind, str(failure), attempts=attempts) from failure
        raise RouterError("exhausted", "Every route for RERANK failed", attempts=attempts)

    def _keyed(self, choices: Sequence[RouteChoice]) -> list[tuple[RouteChoice, str]]:
        found: list[tuple[RouteChoice, str]] = []
        for choice in choices:
            key = self._keys(choice.key_name)
            if key:
                found.append((choice, key))
        return found

    def _sessions(self) -> async_sessionmaker[AsyncSession]:
        if self._session_factory is None:
            from app.core.db import sessionmaker

            self._session_factory = sessionmaker()
        return self._session_factory

    async def _routes(self) -> tuple[list[RouteChoice], dict[str, Any]]:
        async with self._sessions()() as session:
            loaded = await load_routes(session, AiTask.RERANK)
            values = await spend_settings.load_spend_settings(session)
            await managed_keys.refresh_if_stale(session)
        ordered = order_routes(AiTask.RERANK, loaded, degrade=False, estimate=lambda _: Decimal(0))
        return ordered, values.get(spend_settings.MODEL_PRICES) or {}

    async def _call(
        self, choice: RouteChoice, key: str, request: RerankRequest, overrides: Mapping[str, Any]
    ) -> list[Relevance]:
        estimate = rerank_cost(choice, rerank_tokens(request.query, request.documents), overrides)
        event_id = await self._reserve(choice, estimate)
        try:
            result = await self._reranked(choice, key, request)
        except ProviderError as failure:
            await self._failed(event_id, choice, key, failure, estimate)
            raise
        except BaseException:
            await settle_abandoned(self._sessions(), event_id, estimate, answer=self._principal.answer)
            raise
        tokens = result.total_tokens
        if tokens is None:
            tokens = rerank_tokens(request.query, request.documents)
        await self._settled(event_id, estimate, rerank_cost(choice, tokens, overrides), tokens, result)
        return [Relevance(index=index, score=score) for index, score in result.scores]

    async def _reserve(self, choice: RouteChoice, estimate: Decimal) -> uuid.UUID:
        async with self._sessions()() as session:
            event_id, decision = await reserve(
                session, task=AiTask.RERANK, choice=choice, principal=self._principal, estimate_usd=estimate
            )
        if not decision.allowed:
            raise RouterError(
                SPEND_REFUSAL_KIND, decision.message or "Budget reached", reason=decision.reason
            )
        return event_id

    async def _reranked(self, choice: RouteChoice, key: str, request: RerankRequest) -> RerankResult:
        adapter = self._adapter_factory(choice, key)
        try:
            return await adapter.rerank(request)
        finally:
            await adapter.aclose()

    async def _settled(
        self, event_id: uuid.UUID, estimate: Decimal, cost: Decimal, tokens: int, result: RerankResult
    ) -> None:
        if self._principal.answer is not None:
            self._principal.answer.settle(estimate, cost)
        async with self._sessions()() as session:
            await settle(
                session,
                event_id,
                outcome="OK",
                cost_usd=cost,
                input_tokens=tokens,
                output_tokens=0,
                latency_ms=result.latency_ms,
                detail={"documents": len(result.scores), "estimatedTokens": result.total_tokens is None},
            )

    async def _failed(
        self, event_id: uuid.UUID, choice: RouteChoice, key: str, failure: ProviderError, estimate: Decimal
    ) -> None:
        if self._principal.answer is not None:
            self._principal.answer.release(estimate)
        async with self._sessions()() as session:
            await settle(
                session,
                event_id,
                outcome="REFUSED_PROVIDER" if failure.kind == "refusal" else "ERROR",
                error_kind=failure.kind,
                detail={"status": failure.status},
            )
            if failure.kind == "auth":
                await mark_key_failed(session, choice.key_name, key, str(failure))


def rerank_cost(choice: RouteChoice, tokens: int, overrides: Mapping[str, Any]) -> Decimal:
    model = model_for(choice.provider, choice.model)
    return budget.token_cost(model, input_tokens=tokens, output_tokens=0, overrides=dict(overrides))


def _built_adapter(choice: RouteChoice, key: str) -> Adapter:
    return build_adapter(
        preset=choice.preset,
        kind=choice.kind,
        api_key=key,
        api_key_name=choice.key_name,
        base_url=choice.base_url,
        extra=choice.extra,
        learned=choice.learned,
    )
