from app.planner.coverage import stored_knowledge
from app.research.retrieval import KnowledgeHits, KnowledgeQuery


class Asked:
    def __init__(self) -> None:
        self.queries: list[KnowledgeQuery] = []

    async def search(self, query: KnowledgeQuery) -> KnowledgeHits:
        self.queries.append(query)
        return KnowledgeHits(craft_slug=query.craft_slug)


async def test_an_answer_reads_open_passages_and_no_transcript_window_whoever_asks_it() -> None:
    asked = Asked()
    await stored_knowledge(asked, craft_slug="Kutch-Ajrakh", mode="HYBRID", question="Why alum?")
    (query,) = asked.queries
    assert query.chunk_acls == ("PUBLIC", "SIGNED_IN") and "RESEARCHER" not in query.chunk_acls
    assert query.chunk_kinds == ("PASSAGE",)
