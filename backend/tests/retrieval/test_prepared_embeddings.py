import asyncio
from dataclasses import dataclass, field

from app.planner.coverage import facet_coverage
from app.research.planning import Facet
from app.research.retrieval import KnowledgeHits, KnowledgeQuery
from app.retrieval.answer_embeddings import AnswerEmbeddings
from app.retrieval.hybrid import SessionScopedSearch
from app.retrieval.text import query_text

from .test_first_stage import STAMP, CountingEmbedder, stamps

FACETS = (
    Facet(type="MATERIAL", target="alum"),
    Facet(type="MECHANISM", target="mordant bath"),
    Facet(type="PROCESS_STAGE", target="washing"),
)


async def test_preparing_a_cached_search_embeds_every_text_in_one_call() -> None:
    inner = CountingEmbedder()
    embed = AnswerEmbeddings(inner, stamp=stamps(STAMP))
    search = SessionScopedSearch(lambda: None, embed=embed)
    await search.prepare(["alum", "mordant bath", "washing"])
    await asyncio.gather(*(embed([query_text(text)]) for text in ("washing", "alum", "mordant bath")))
    assert inner.calls == [[query_text("alum"), query_text("mordant bath"), query_text("washing")]]


async def test_preparing_a_search_without_a_cache_embeds_nothing() -> None:
    inner = CountingEmbedder()
    await SessionScopedSearch(lambda: None, embed=inner).prepare(["alum"])
    assert inner.calls == []


@dataclass
class PreparedRetriever:
    steps: list[str] = field(default_factory=list)

    async def prepare(self, texts: list[str]) -> None:
        self.steps.append("prepare " + ", ".join(texts))

    async def search(self, query: KnowledgeQuery) -> KnowledgeHits:
        self.steps.append(f"search {query.text}")
        return KnowledgeHits(craft_slug=query.craft_slug)


async def test_facet_coverage_prepares_every_target_before_searching_any() -> None:
    retriever = PreparedRetriever()
    await facet_coverage(retriever, craft_slug="Kutch-Ajrakh", mode="HYBRID", facets=FACETS)
    assert retriever.steps == [
        "prepare alum, mordant bath, washing",
        "search alum",
        "search mordant bath",
        "search washing",
    ]
