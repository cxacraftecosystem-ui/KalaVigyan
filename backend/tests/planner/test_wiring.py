from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from app.models.crafts import EMBEDDING_DIMENSIONS
from app.planner.reading import LiveSources
from app.providers import router
from app.providers.catalogue import AiTask
from app.providers.embedding import router_embedder
from app.providers.structured import router_structured_model
from app.research.structured import StructuredModel
from app.services import live_sources as live_sources_module
from app.sources.scholarly.registry import ScholarlyKeys
from app.sources.web.registry import WebSearchConfig


async def test_the_router_model_runs_the_plan_task_with_the_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    async def run(task: AiTask, **options: Any) -> SimpleNamespace:
        seen.update(options, task=task)
        return SimpleNamespace(text='{"ok": true}', degraded=True, model="gemini-3.8-flash-lite")

    monkeypatch.setattr(router, "run", run)
    principal = router.Principal(role="STUDENT")
    model = router_structured_model(AiTask.PLAN, principal)
    assert isinstance(model, StructuredModel)
    reply = await model(system="sys", user="usr", schema={"type": "object"})
    assert (reply.text, reply.degraded, reply.model) == ('{"ok": true}', True, "gemini-3.8-flash-lite")
    assert seen == {
        "task": AiTask.PLAN,
        "system": "sys",
        "user": "usr",
        "json_schema": {"type": "object"},
        "principal": principal,
        "tuning": None,
        "request_budget_usd": None,
    }


async def test_each_call_is_capped_by_the_request_budget_read_just_before_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    caps: list[Decimal | None] = []
    spent = [Decimal("2.10"), Decimal("2.35")]

    async def run(task: AiTask, **options: Any) -> SimpleNamespace:
        caps.append(options["request_budget_usd"])
        return SimpleNamespace(
            text="{}", degraded=False, model="m", embeddings=[[0.0] * EMBEDDING_DIMENSIONS]
        )

    async def left() -> Decimal:
        return Decimal("2.50") - spent.pop(0)

    monkeypatch.setattr(router, "run", run)
    model = router_structured_model(AiTask.PLAN, request_budget_usd=left)
    await model(system="s", user="u", schema={})
    await router_embedder(request_budget_usd=lambda: _value(Decimal("0.15")))(["text"])
    await model(system="s", user="u", schema={})
    assert caps == [Decimal("0.40"), Decimal("0.15"), Decimal("0.15")]


async def _value(amount: Decimal) -> Decimal:
    return amount


async def test_live_sources_join_every_adapter_with_one_fetcher(monkeypatch: pytest.MonkeyPatch) -> None:
    async def keys(session: object) -> ScholarlyKeys:
        return ScholarlyKeys(contact_email="research@example.org")

    async def web_config(session: object) -> WebSearchConfig:
        return WebSearchConfig(searxng_url="http://127.0.0.1:8888")

    monkeypatch.setattr(live_sources_module, "scholarly_keys", keys)
    monkeypatch.setattr(live_sources_module, "web_search_config", web_config)
    async with httpx.AsyncClient() as client:
        sources = await live_sources_module.live_sources(object(), client)
    assert isinstance(sources, LiveSources)
    names = [searcher.name for searcher in sources.searchers]
    assert names == [
        "openalex",
        "crossref",
        "semantic_scholar",
        "europe_pmc",
        "arxiv",
        "doaj",
        "zenodo",
        "wikipedia",
        "wikidata",
        "pubchem",
        "wikimedia_commons",
        "web",
    ]
    assert {searcher.tier for searcher in sources.searchers[:-1]} == {"T3"}
    assert sources.searchers[-1].tier == "T4"
    assert sources.doi_source is not None and sources.doi_source.name == "crossref"
    assert sources.reference_source is sources.searchers[0]
    assert sources.locator is not None and sources.locator.name == "open_access"
    assert sources.searchers[-1].primary.fetcher is sources.fetcher
