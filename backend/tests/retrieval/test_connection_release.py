from __future__ import annotations

import uuid
from typing import Any

import pytest

from app.models import Claim
from app.research.embedding import EMBEDDING_DIMENSIONS
from app.research.retrieval import KnowledgeQuery
from app.retrieval.hybrid import StoredKnowledgeSearch
from app.retrieval.indexing import _fill, _Pending
from app.services.craft_resolver import CraftIndexStore, DatabaseCraftResolver


class Embedded(Exception):
    pass


class RecordingSession:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def execute(self, statement: Any) -> Any:
        self.calls.append("execute")
        return EmptyResult()

    async def commit(self) -> None:
        self.calls.append("commit")


class EmptyResult:
    rowcount = 1

    def first(self) -> None:
        return None

    def all(self) -> list[Any]:
        return []


def embed_after(session: RecordingSession, *, stop: bool):
    async def embed(texts: list[str]) -> list[list[float]]:
        session.calls.append("embed")
        if stop:
            raise Embedded
        return [[0.0] * EMBEDDING_DIMENSIONS for _ in texts]

    return embed


def held_while_embedding(calls: list[str]) -> list[int]:
    held = False
    found: list[int] = []
    for index, call in enumerate(calls):
        if call == "execute":
            held = True
        elif call == "commit":
            held = False
        elif call == "embed" and held:
            found.append(index)
    return found


async def test_stored_search_embeds_the_question_before_it_takes_a_connection() -> None:
    session = RecordingSession()
    search = StoredKnowledgeSearch(session, embed=embed_after(session, stop=True))
    query = KnowledgeQuery(craft_slug="kutch-ajrakh", text="Why does alum fix alizarin?", mode="HYBRID")
    with pytest.raises(Embedded):
        await search.search(query)
    assert session.calls == ["embed"]


async def test_filling_vectors_releases_the_connection_before_every_embedding_call() -> None:
    session = RecordingSession()
    await session.execute("pending rows")
    pending = [_Pending(id=uuid.uuid4(), text=f"claim {n}", read=f"claim {n}") for n in range(5)]
    await _fill(session, embed_after(session, stop=False), Claim, pending, batch_size=2)
    assert session.calls.count("embed") == 3
    assert held_while_embedding(session.calls) == []


async def test_the_craft_resolver_releases_the_connection_before_it_embeds_the_question() -> None:
    session = RecordingSession()
    await session.execute("craft index")
    resolver = DatabaseCraftResolver(session, store=CraftIndexStore(), embed=embed_after(session, stop=True))
    with pytest.raises(Embedded):
        await resolver._semantic("ajrakh block printing")
    assert held_while_embedding(session.calls) == []
