import uuid
from collections.abc import AsyncIterator, Sequence
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.db import get_engine
from app.models import Provider, RoutePolicy, UsageEvent, User
from app.providers.base import Adapter, ProviderError, RerankRequest, RerankResult
from app.providers.budget import AnswerSpend
from app.providers.rerank_router import NO_KEY_KIND, RerankRouter
from app.providers.router import Principal, RouterError
from app.research.reranking import Relevance

pytestmark = pytest.mark.db

DOCUMENTS = ("a" * 300, "b" * 300)
BILLED_TOKENS = 20_000
BILLED_USD = Decimal("0.001000")


@pytest.fixture
async def sessions() -> AsyncIterator[tuple[async_sessionmaker[AsyncSession], AsyncSession]]:
    async with get_engine().connect() as connection:
        transaction = await connection.begin()
        try:
            factory = async_sessionmaker(
                bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
            )
            async with factory() as session:
                yield factory, session
        finally:
            await transaction.rollback()


class Scored(Adapter):
    def __init__(self, *, failure: ProviderError | None = None) -> None:
        super().__init__(api_key="k", base_url=None, preset="voyage", extra={}, learned={})
        self.failure = failure
        self.asked: list[RerankRequest] = []

    async def chat(self, req: Any) -> Any:
        raise AssertionError("a reranker never chats")

    async def list_models(self) -> list[dict]:
        return []

    async def rerank(self, req: RerankRequest) -> RerankResult:
        self.asked.append(req)
        if self.failure is not None:
            raise self.failure
        return RerankResult(scores=((1, 0.875), (0, 0.25)), total_tokens=BILLED_TOKENS)


async def reader(session: AsyncSession, depth: str = "DETAILED") -> Principal:
    user = User(id=uuid.uuid4(), name="Rerank Router", email=f"rerank-{uuid.uuid4().hex[:8]}@example.com")
    session.add(user)
    await session.commit()
    return Principal(user.id, "STUDENT", answer=AnswerSpend(depth=depth))


def router(
    factory: Any, principal: Principal, adapter: Adapter, key: str | None = "test-key"
) -> RerankRouter:
    return RerankRouter(
        principal=principal,
        session_factory=factory,
        adapter_factory=lambda choice, found: adapter,
        keys=lambda name: key if name == "VOYAGE_API_KEY" else None,
    )


async def usage(session: AsyncSession, principal: Principal) -> Sequence[UsageEvent]:
    rows = await session.scalars(
        select(UsageEvent).where(UsageEvent.userId == principal.user_id, UsageEvent.task == "RERANK")
    )
    return rows.all()


async def test_the_migration_adds_voyage_and_routes_rerank_to_rerank_3(sessions: Any) -> None:
    _, session = sessions
    voyage = (await session.execute(select(Provider).where(Provider.name == "VOYAGE"))).scalar_one()
    assert (voyage.preset, voyage.kind, voyage.baseUrl, voyage.apiKeySecretKey, voyage.dataClass) == (
        "voyage",
        "voyage",
        "https://api.voyageai.com/v1",
        "VOYAGE_API_KEY",
        "ANY",
    )
    routes = (
        await session.execute(
            select(RoutePolicy.ordinal, RoutePolicy.model, RoutePolicy.providerId).where(
                RoutePolicy.task == "RERANK"
            )
        )
    ).all()
    assert [(row.ordinal, row.model, row.providerId) for row in routes] == [(1, "rerank-3", voyage.id)]
    tasks = (await session.execute(text('SELECT enum_range(NULL::"AiTask")::text[]'))).scalar_one()
    providers = (await session.execute(text('SELECT enum_range(NULL::"AiProvider")::text[]'))).scalar_one()
    assert "RERANK" in tasks and "VOYAGE" in providers


async def test_a_rerank_is_reserved_then_settled_at_its_billed_tokens(sessions: Any) -> None:
    factory, session = sessions
    principal = await reader(session)
    adapter = Scored()
    found = await router(factory, principal, adapter)("Why does alum fix red?", DOCUMENTS)
    assert found == [Relevance(index=1, score=0.875), Relevance(index=0, score=0.25)]
    assert adapter.asked == [RerankRequest("rerank-3", "Why does alum fix red?", DOCUMENTS)]
    (row,) = await usage(session, principal)
    assert (row.outcome, row.provider, row.model, row.inputTokens, row.outputTokens) == (
        "OK",
        "VOYAGE",
        "rerank-3",
        BILLED_TOKENS,
        0,
    )
    assert row.costUsd == BILLED_USD
    assert row.estimatedCostUsd == Decimal("0.000011")
    assert principal.answer is not None
    assert (principal.answer.held_usd, principal.answer.spent_usd) == (Decimal(0), BILLED_USD)


async def test_without_a_key_nothing_is_reserved_or_called(sessions: Any) -> None:
    factory, session = sessions
    principal = await reader(session)
    adapter = Scored()
    with pytest.raises(RouterError) as refused:
        await router(factory, principal, adapter, key=None)("q", DOCUMENTS)
    assert refused.value.kind == NO_KEY_KIND
    assert (adapter.asked, list(await usage(session, principal))) == ([], [])


async def test_a_refused_spend_raises_the_ceiling_and_calls_nothing(sessions: Any) -> None:
    factory, session = sessions
    principal = await reader(session, depth="NO_SUCH_DEPTH")
    adapter = Scored()
    with pytest.raises(RouterError) as refused:
        await router(factory, principal, adapter)("q", DOCUMENTS)
    assert (refused.value.kind, refused.value.reason) == ("ceiling", "ANSWER_CAP")
    assert adapter.asked == []
    ((row_outcome, row_error),) = [(row.outcome, row.errorKind) for row in await usage(session, principal)]
    assert (row_outcome, row_error) == ("REFUSED_CEILING", "ANSWER_CAP")


async def test_a_refused_key_settles_an_error_and_gives_back_the_answer_s_hold(sessions: Any) -> None:
    factory, session = sessions
    principal = await reader(session)
    adapter = Scored(failure=ProviderError("Voyage answered 401 to rerank", kind="auth", status=401))
    with pytest.raises(RouterError) as failed:
        await router(factory, principal, adapter)("q", DOCUMENTS)
    assert failed.value.kind == "exhausted"
    (row,) = await usage(session, principal)
    assert (row.outcome, row.errorKind, row.costUsd) == ("ERROR", "auth", Decimal(0))
    assert principal.answer is not None
    assert (principal.answer.held_usd, principal.answer.spent_usd) == (Decimal(0), Decimal(0))
