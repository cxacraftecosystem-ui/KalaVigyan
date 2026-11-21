import asyncio
from typing import Any, cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.research.retrieval import KnowledgeQuery
from app.retrieval.hybrid import StoredKnowledgeSearch

from ..craft_fixtures import FixedEmbedder


class NoRows:
    def all(self) -> list[Any]:
        return []


class OverlapSession:
    def __init__(self) -> None:
        self.running = 0
        self.most = 0
        self.statements = 0

    async def scalars(self, statement: Any) -> NoRows:
        self.running += 1
        self.statements += 1
        self.most = max(self.most, self.running)
        await asyncio.sleep(0)
        self.running -= 1
        return NoRows()


def query(text: str, *, passages: bool = True) -> KnowledgeQuery:
    return KnowledgeQuery(craft_slug=None, text=text, mode="HYBRID", passages=passages)


async def test_searches_sharing_one_session_take_turns() -> None:
    session = OverlapSession()
    search = StoredKnowledgeSearch(cast(AsyncSession, session), embed=FixedEmbedder())
    await asyncio.gather(search.search(query("alum mordant")), search.search(query("indigo vat")))
    assert session.most == 1
    assert session.statements == 2 * (3 + 4)


async def test_a_search_without_passages_runs_only_the_three_claim_rankings() -> None:
    session = OverlapSession()
    search = StoredKnowledgeSearch(cast(AsyncSession, session), embed=FixedEmbedder())
    found = await search.search(query("alum mordant", passages=False))
    assert (found.claims, found.chunks, session.statements) == ((), (), 3)
