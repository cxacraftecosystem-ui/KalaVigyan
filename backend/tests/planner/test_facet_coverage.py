import asyncio
from dataclasses import dataclass, field

from app.planner.coverage import facet_coverage, stored_knowledge
from app.research.planning import Facet
from app.research.retrieval import KnowledgeHits, KnowledgeQuery

FACETS = (
    Facet(type="MATERIAL", target="alum"),
    Facet(type="MECHANISM", target="mordant bath"),
    Facet(type="PROCESS_STAGE", target="washing"),
)
TOGETHER_SECONDS = 1.0


@dataclass
class TogetherRetriever:
    together: asyncio.Barrier
    queries: list[KnowledgeQuery] = field(default_factory=list)

    async def search(self, query: KnowledgeQuery) -> KnowledgeHits:
        self.queries.append(query)
        await asyncio.wait_for(self.together.wait(), TOGETHER_SECONDS)
        return KnowledgeHits(craft_slug=query.craft_slug)


async def test_the_facets_are_searched_at_once_and_read_no_passages() -> None:
    retriever = TogetherRetriever(asyncio.Barrier(len(FACETS)))
    coverage = await facet_coverage(retriever, craft_slug="Kutch-Ajrakh", mode="HYBRID", facets=FACETS)
    assert [(entry.facet_index, entry.claim_ids) for entry in coverage] == [(0, ()), (1, ()), (2, ())]
    assert [(query.text, query.facets, query.passages) for query in retriever.queries] == [
        ("alum", ("MATERIAL",), False),
        ("mordant bath", ("MECHANISM",), False),
        ("washing", ("PROCESS_STAGE",), False),
    ]


async def test_the_stored_pack_still_reads_passages() -> None:
    retriever = TogetherRetriever(asyncio.Barrier(1))
    await stored_knowledge(retriever, craft_slug="Kutch-Ajrakh", mode="HYBRID", question="Why alum?")
    (query,) = retriever.queries
    assert query.passages is True
