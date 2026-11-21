import uuid
from typing import Any, cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ExternalFailure
from app.research.review_queue import QueueDecision
from app.retrieval.indexing import EmbeddedCounts
from app.services import written_vectors
from app.services.written_vectors import NOTHING_EMBEDDED, embed_decided, embed_now

from ..craft_fixtures import FixedEmbedder

PROPOSAL, CLAIM = uuid.uuid4(), uuid.uuid4()


class Rows:
    def __init__(self, values: list[Any]) -> None:
        self.values = values

    def all(self) -> list[Any]:
        return self.values


class ClaimOfProposal:
    def __init__(self) -> None:
        self.asked: list[str] = []

    async def scalars(self, statement: Any) -> Rows:
        self.asked.append(str(statement))
        return Rows([CLAIM])


def recorded(monkeypatch: pytest.MonkeyPatch) -> list[tuple[list[uuid.UUID], list[uuid.UUID]]]:
    seen: list[tuple[list[uuid.UUID], list[uuid.UUID]]] = []

    async def embedded(session: Any, embed: Any, *, claim_ids: Any, source_ids: Any) -> EmbeddedCounts:
        seen.append((list(claim_ids), list(source_ids)))
        return EmbeddedCounts(claims=len(claim_ids), chunks=0)

    monkeypatch.setattr(written_vectors, "embed_written", embedded)
    return seen


async def test_nothing_written_asks_for_no_vector() -> None:
    session = cast(AsyncSession, object())
    assert await embed_now(session, FixedEmbedder()) == NOTHING_EMBEDDED


async def test_a_failed_embedding_route_never_undoes_the_write(monkeypatch: pytest.MonkeyPatch) -> None:
    async def failing(*args: Any, **kwargs: Any) -> EmbeddedCounts:
        raise ExternalFailure("embedding route timed out", kind="unavailable", service="embeddings")

    monkeypatch.setattr(written_vectors, "embed_written", failing)
    session = cast(AsyncSession, object())
    assert await embed_now(session, FixedEmbedder(), claim_ids=[CLAIM]) == NOTHING_EMBEDDED


async def test_an_approved_structure_embeds_the_fact_it_wrote(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = recorded(monkeypatch)
    session = ClaimOfProposal()
    decision = QueueDecision(kind="STRUCTURE", id=PROPOSAL, status="APPROVED", message="Approved.")
    counts = await embed_decided(cast(AsyncSession, session), FixedEmbedder(), decision)
    assert counts == EmbeddedCounts(claims=1, chunks=0)
    assert seen == [([CLAIM], [])]
    assert '"StructureProposal"."claimId" IS NOT NULL' in session.asked[0]


async def test_other_decisions_write_no_fact_to_embed(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = recorded(monkeypatch)
    decision = QueueDecision(kind="IMAGES", id=PROPOSAL, status="APPROVED", message="Approved.")
    assert await embed_decided(cast(AsyncSession, object()), FixedEmbedder(), decision) == NOTHING_EMBEDDED
    assert seen == []
