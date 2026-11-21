import uuid
from collections.abc import Sequence
from types import SimpleNamespace
from typing import Any, cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.research.reranking import Relevance
from app.research.retrieval import KnowledgeQuery
from app.retrieval.hybrid import StoredKnowledgeSearch

from ..craft_fixtures import FixedEmbedder

ALUM, INDIGO = uuid.uuid5(uuid.NAMESPACE_URL, "test/alum"), uuid.uuid5(uuid.NAMESPACE_URL, "test/indigo")
SUBJECT = uuid.uuid5(uuid.NAMESPACE_URL, "test/subject")


class Rows(list[Any]):
    def all(self) -> list[Any]:
        return list(self)

    def tuples(self) -> Rows:
        return self


def claim_row(claim_id: uuid.UUID, text: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=claim_id, text=text, evidenceLevel="PROVISIONAL", subjectType="CONCEPT", subjectId=SUBJECT
    )


class TurnSession:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.executed = iter(
            [
                Rows(
                    [claim_row(ALUM, "Alum fixes the red."), claim_row(INDIGO, "Indigo is reduced in a vat.")]
                ),
                Rows([SimpleNamespace(id=ALUM, field="CHEMISTRY", concept="Alum", craft="Ajrakh")]),
                Rows(),
            ]
        )

    async def scalars(self, statement: Any) -> Rows:
        self.calls.append("query")
        return Rows([ALUM, INDIGO])

    async def execute(self, statement: Any) -> Rows:
        self.calls.append("query")
        return next(self.executed)

    async def commit(self) -> None:
        self.calls.append("release")


class Recording:
    def __init__(self, session: TurnSession) -> None:
        self.session = session
        self.documents: list[str] = []

    async def __call__(self, query: str, documents: Sequence[str]) -> list[Relevance]:
        self.session.calls.append("rerank")
        self.documents = list(documents)
        return [Relevance(index=1, score=0.9), Relevance(index=0, score=0.2)]


async def test_the_search_releases_its_connection_before_the_one_rerank_call() -> None:
    session = TurnSession()
    reranker = Recording(session)
    search = StoredKnowledgeSearch(cast(AsyncSession, session), embed=FixedEmbedder(), rerank=reranker)
    query = KnowledgeQuery(craft_slug=None, text="alum mordant", mode="HYBRID", passages=False, rerank=True)
    found = await search.search(query)
    assert session.calls == ["query"] * 6 + ["release", "rerank"]
    assert [(hit.claim_id, hit.relevance_score) for hit in found.claims] == [(INDIGO, 0.9), (ALUM, 0.2)]
    assert reranker.documents == [
        "title: Ajrakh, Alum, chemistry | text: Alum fixes the red.",
        "title: none | text: Indigo is reduced in a vat.",
    ]
