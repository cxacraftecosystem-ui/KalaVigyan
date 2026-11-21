import json
from collections.abc import Callable
from decimal import Decimal

import httpx
import pytest

from app.providers.base import ChatRequest, ProviderError, RerankRequest
from app.providers.registry import build_adapter
from app.providers.rerank_router import rerank_cost, rerank_tokens
from app.providers.router import RouteChoice
from app.providers.voyage_p import DOCUMENTS_MAX, VoyageAdapter, rerank_body, rerank_result

KEY = "test-only-voyage-key-not-a-secret"
ASKED = RerankRequest(model="rerank-3", query="Why does alum fix red?", documents=("alum bath", "indigo vat"))
ANSWER = {
    "object": "list",
    "data": [{"index": 0, "relevance_score": 0.91015625}, {"index": 1, "relevance_score": 0.1328125}],
    "model": "rerank-3",
    "usage": {"total_tokens": 21},
}

Handler = Callable[[httpx.Request], httpx.Response]


def adapter(handler: Handler, slept: list[float] | None = None) -> tuple[VoyageAdapter, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    async def sleep(seconds: float) -> None:
        if slept is not None:
            slept.append(seconds)

    client = httpx.AsyncClient(transport=httpx.MockTransport(record))
    made = VoyageAdapter(
        api_key=KEY,
        base_url="https://api.voyageai.com/v1",
        preset="voyage",
        extra={},
        learned={},
        client=client,
        sleep=sleep,
    )
    return made, seen


def answered(status: int = 200, body: object = ANSWER, headers: dict[str, str] | None = None) -> Handler:
    return lambda request: httpx.Response(status, json=body, headers=headers or {})


async def test_a_rerank_posts_the_query_documents_and_model_with_the_key_as_a_bearer() -> None:
    made, seen = adapter(answered())
    result = await made.rerank(ASKED)
    (request,) = seen
    assert (request.method, str(request.url)) == ("POST", "https://api.voyageai.com/v1/rerank")
    assert request.headers["authorization"] == f"Bearer {KEY}"
    assert json.loads(request.content) == {
        "query": "Why does alum fix red?",
        "documents": ["alum bath", "indigo vat"],
        "model": "rerank-3",
        "truncation": True,
    }
    assert (result.scores, result.total_tokens) == (((0, 0.91015625), (1, 0.1328125)), 21)


async def test_a_429_with_a_short_retry_after_waits_and_asks_once_more() -> None:
    replies = iter([httpx.Response(429, json={"detail": "slow down"}, headers={"retry-after": "1"})])

    def handler(request: httpx.Request) -> httpx.Response:
        return next(replies, httpx.Response(200, json=ANSWER))

    slept: list[float] = []
    made, seen = adapter(handler, slept)
    result = await made.rerank(ASKED)
    assert (len(seen), slept, result.total_tokens) == (2, [1.0], 21)


async def test_a_429_asking_for_a_long_wait_is_a_rate_limit_carrying_the_wait() -> None:
    slept: list[float] = []
    made, seen = adapter(answered(429, {"detail": "slow down"}, {"retry-after": "30"}), slept)
    with pytest.raises(ProviderError) as refused:
        await made.rerank(ASKED)
    assert (refused.value.kind, refused.value.retry_after, refused.value.status) == ("rate_limit", 30.0, 429)
    assert (len(seen), slept) == (1, [])


@pytest.mark.parametrize(
    ("status", "kind"),
    [(400, "bad_request"), (401, "auth"), (403, "auth"), (500, "unavailable"), (503, "unavailable")],
)
async def test_each_status_is_mapped_to_its_shared_failure_kind_and_never_names_the_key(
    status: int, kind: str
) -> None:
    made, _ = adapter(answered(status, {"detail": "no"}))
    with pytest.raises(ProviderError) as failed:
        await made.rerank(ASKED)
    assert (failed.value.kind, failed.value.status, failed.value.service) == (kind, status, "voyage")
    assert KEY not in str(failed.value)


@pytest.mark.parametrize(
    "body",
    [
        {"object": "list"},
        {"data": [{"index": 2, "relevance_score": 0.5}]},
        {"data": [{"index": 0, "relevance_score": "high"}]},
        {"data": [{"index": True, "relevance_score": 0.5}]},
        {"data": [], "usage": {"total_tokens": -1}},
    ],
)
async def test_an_answer_off_the_contract_is_an_error(body: object) -> None:
    made, _ = adapter(answered(200, body))
    with pytest.raises(ProviderError) as failed:
        await made.rerank(ASKED)
    assert failed.value.kind == "error"


async def test_a_timeout_is_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    made, _ = adapter(handler)
    with pytest.raises(ProviderError) as failed:
        await made.rerank(ASKED)
    assert (failed.value.kind, failed.value.retryable) == ("unavailable", True)


def test_a_rerank_takes_one_to_a_thousand_documents_and_a_query() -> None:
    assert DOCUMENTS_MAX == 1000
    for documents in ((), tuple(f"d{n}" for n in range(1001))):
        with pytest.raises(ProviderError) as refused:
            rerank_body(RerankRequest(model="rerank-3", query="q", documents=documents))
        assert refused.value.kind == "bad_request"
    with pytest.raises(ProviderError):
        rerank_body(RerankRequest(model="rerank-3", query="  ", documents=("d",)))


def test_a_missing_token_count_is_kept_as_unknown() -> None:
    result = rerank_result({"data": [{"index": 0, "relevance_score": 0.5}]}, documents=1)
    assert (result.scores, result.total_tokens) == (((0, 0.5),), None)


async def test_the_registry_builds_the_voyage_adapter_only_with_a_key() -> None:
    built = build_adapter(preset="voyage", kind="voyage", api_key=KEY, api_key_name="VOYAGE_API_KEY")
    assert isinstance(built, VoyageAdapter)
    with pytest.raises(ProviderError) as unchat:
        await built.chat(ChatRequest(model="rerank-3", system="", user=""))
    assert unchat.value.kind == "unavailable"
    await built.aclose()
    with pytest.raises(ProviderError) as keyless:
        build_adapter(preset="voyage", kind="voyage", api_key=None, api_key_name="VOYAGE_API_KEY")
    assert keyless.value.kind == "auth"


def voyage_route() -> RouteChoice:
    return RouteChoice(
        ordinal=1,
        provider="VOYAGE",
        provider_id=None,
        preset="voyage",
        kind="voyage",
        base_url="https://api.voyageai.com/v1",
        key_name="VOYAGE_API_KEY",
        model="rerank-3",
    )


def test_tokens_are_the_query_once_per_document_plus_every_document() -> None:
    assert rerank_tokens("Why alum?", ["a" * 30, "b" * 60]) == 3 * 2 + 10 + 20


def test_rerank_3_is_priced_at_five_cents_a_million_tokens() -> None:
    assert rerank_cost(voyage_route(), 1_000_000, {}) == Decimal("0.050000")
    assert rerank_cost(voyage_route(), 20_000, {}) == Decimal("0.001000")
    assert rerank_cost(voyage_route(), 36, {}) == Decimal("0.000002")
