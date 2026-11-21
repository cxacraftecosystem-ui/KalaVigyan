import uuid
from typing import Any

import pytest

from app.core.errors import ExternalFailure
from app.models.crafts import EMBEDDING_DIMENSIONS
from app.providers.router import RouterError
from app.research.crafts import CraftQuery, CraftResolver
from app.research.embedding import checked_vectors
from app.services import craft_resolver
from app.services.craft_index import CraftIndex
from app.services.craft_resolver import (
    CraftIndexStore,
    DatabaseCraftResolver,
    descriptor_text,
)

from .craft_fixtures import BARMER, KUTCH, sample_index

VECTOR = [0.0] * EMBEDDING_DIMENSIONS


class StubStore:
    def __init__(self, index: CraftIndex) -> None:
        self.index = index

    async def get(self, session: Any) -> CraftIndex:
        return self.index


class Rows:
    def __init__(self, rows: list[tuple[uuid.UUID, float]]) -> None:
        self.rows = rows

    def all(self) -> list[tuple[uuid.UUID, float]]:
        return self.rows


class NearestSession:
    def __init__(self, rows: list[tuple[uuid.UUID, float]]) -> None:
        self.rows = rows
        self.queries = 0

    async def execute(self, statement: Any) -> Rows:
        self.queries += 1
        return Rows(self.rows)

    async def commit(self) -> None:
        return None


class RecordingEmbedder:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    async def __call__(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return [VECTOR for _ in texts]


def resolver(index: CraftIndex, session: Any, embed: Any) -> DatabaseCraftResolver:
    return DatabaseCraftResolver(session, store=StubStore(index), embed=embed)


async def test_the_database_resolver_meets_the_contract_protocol() -> None:
    assert isinstance(resolver(sample_index(), NearestSession([]), RecordingEmbedder()), CraftResolver)


async def test_a_lexical_winner_never_pays_for_an_embedding() -> None:
    embed, session = RecordingEmbedder(), NearestSession([])
    found = await resolver(sample_index(embedded=455), session, embed).resolve(
        CraftQuery(text="Why is Kutch Ajrakh dyed twice?")
    )
    assert found.status == "RESOLVED"
    assert (embed.calls, session.queries) == ([], 0)


async def test_semantic_search_waits_until_crafts_have_embeddings() -> None:
    embed, session = RecordingEmbedder(), NearestSession([])
    found = await resolver(sample_index(embedded=0), session, embed).resolve(CraftQuery(text="ajrak"))
    assert found.status == "AMBIGUOUS"
    assert (embed.calls, session.queries) == ([], 0)


async def test_semantic_neighbours_join_an_unsettled_ranking() -> None:
    embed, session = RecordingEmbedder(), NearestSession([(KUTCH, 0.1), (BARMER, 0.5)])
    found = await resolver(sample_index(embedded=2), session, embed).resolve(CraftQuery(text="ajrak"))
    assert embed.calls == [["ajrak"]]
    assert session.queries == 1
    assert [(c.craft.slug, c.score) for c in found.candidates] == [
        ("Kutch-Ajrakh", 0.913636),
        ("Barmer-Ajrakh-Print", 0.863636),
    ]


class FailingEmbedder:
    def __init__(self, error: Exception) -> None:
        self.error = error

    async def __call__(self, texts: list[str]) -> list[list[float]]:
        raise self.error


async def test_a_failed_embedding_keeps_the_crafts_the_name_match_found() -> None:
    timed_out = ExternalFailure("embedding route timed out", kind="unavailable", service="embeddings")
    session = NearestSession([])
    found = await resolver(sample_index(embedded=2), session, FailingEmbedder(timed_out)).resolve(
        CraftQuery(text="ajrak")
    )
    assert found.status == "AMBIGUOUS"
    assert [(c.craft.slug, c.score) for c in found.candidates] == [
        ("Barmer-Ajrakh-Print", 0.863636),
        ("Kutch-Ajrakh", 0.863636),
    ]
    assert session.queries == 0


async def test_a_spend_refusal_while_embedding_still_stops_the_question() -> None:
    refusal = RouterError("ceiling", "The monthly AI budget has been reached.", reason="MONTHLY_CEILING")
    with pytest.raises(RouterError):
        await resolver(sample_index(embedded=2), NearestSession([]), FailingEmbedder(refusal)).resolve(
            CraftQuery(text="ajrak")
        )


async def test_a_named_slug_skips_text_matching() -> None:
    embed, session = RecordingEmbedder(), NearestSession([])
    found = await resolver(sample_index(embedded=2), session, embed).resolve(
        CraftQuery(text="ajrak", craftSlug="Kutch-Ajrakh")
    )
    assert found.craft is not None and found.craft.slug == "Kutch-Ajrakh"
    assert embed.calls == []


def test_embedding_vectors_are_checked_for_count_and_size() -> None:
    assert checked_vectors([VECTOR], expected=1) == [VECTOR]
    with pytest.raises(ExternalFailure, match="0 vectors for 1 texts"):
        checked_vectors(None, expected=1)
    with pytest.raises(ExternalFailure, match="3 dimensions"):
        checked_vectors([[0.1, 0.2, 0.3]], expected=1)


def test_the_descriptor_joins_distinct_names_in_order() -> None:
    text = descriptor_text("Kutch Ajrakh", ["Ajrakh", "ajrakh", " ", "Kutch Ajrakh", "अजरख"])
    assert text == "Kutch Ajrakh; Ajrakh; अजरख"


async def test_the_index_store_reloads_only_after_its_lifetime(monkeypatch: pytest.MonkeyPatch) -> None:
    loads: list[CraftIndex] = []

    async def load(session: Any) -> CraftIndex:
        loads.append(sample_index())
        return loads[-1]

    monkeypatch.setattr(craft_resolver, "load_index", load)
    now = [1000.0]
    store = CraftIndexStore(ttl_seconds=300.0, clock=lambda: now[0])
    first = await store.get(None)
    now[0] = 1299.0
    assert await store.get(None) is first
    now[0] = 1300.0
    assert await store.get(None) is loads[1]
    store.invalidate()
    await store.get(None)
    assert len(loads) == 3
