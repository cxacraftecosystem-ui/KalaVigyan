from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ExternalFailure
from app.models import Claim
from app.research.candidate_gates import NEIGHBOURS_MAX, GateOutcome, HeldFact, closed_outcome, held_twin
from app.research.embedding import EMBEDDING_SERVICE, TextEmbedder, checked_vectors
from app.research.gate_thrift import VECTOR_TWIN_SIMILARITY, vector_twin
from app.research.write_back import ClaimWriteBack
from app.retrieval.text import document_text

from .candidate_store import CLOSED_STATUSES, SqlHeldFacts, craft_subject
from .claim_writer import write_back_claim_id

__all__ = [
    "KeptVectors",
    "by_craft",
    "closed_by_id",
    "closed_refusals",
    "kept_vectors",
    "statement_vectors",
    "stored_statuses",
]

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class KeptVectors:
    by_text: Mapping[str, list[float]]

    async def __call__(self, texts: list[str]) -> list[list[float]]:
        missing = [text for text in texts if text not in self.by_text]
        if missing:
            raise ExternalFailure(
                f"{len(missing)} statement(s) were not embedded before the gates", service=EMBEDDING_SERVICE
            )
        return [self.by_text[text] for text in texts]


async def statement_vectors(embed: TextEmbedder, claims: Sequence[ClaimWriteBack]) -> dict[str, list[float]]:
    if not claims:
        return {}
    texts = [document_text(claim.text) for claim in claims]
    found = checked_vectors(await embed(texts), expected=len(texts))
    return {claim.dedupe_key: vector for claim, vector in zip(claims, found, strict=True)}


def kept_vectors(claims: Sequence[ClaimWriteBack], vectors: Mapping[str, list[float]]) -> KeptVectors:
    return KeptVectors(
        {
            document_text(claim.text): vectors[claim.dedupe_key]
            for claim in claims
            if claim.dedupe_key in vectors
        }
    )


async def stored_statuses(session: AsyncSession, claims: Sequence[ClaimWriteBack]) -> dict[str, str]:
    ids = {write_back_claim_id(claim.dedupe_key): claim.dedupe_key for claim in claims}
    if not ids:
        return {}
    rows = await session.execute(select(Claim.id, Claim.status).where(Claim.id.in_(list(ids))))
    return {ids[row.id]: row.status for row in rows}


def closed_by_id(claim: ClaimWriteBack, status: str) -> GateOutcome:
    claim_id = write_back_claim_id(claim.dedupe_key)
    return closed_outcome(HeldFact(id=claim_id, text=claim.text, similarity=1.0, status=status))


async def closed_refusals(
    session: AsyncSession, claims: Sequence[ClaimWriteBack], vectors: Mapping[str, list[float]]
) -> dict[str, GateOutcome]:
    refused: dict[str, GateOutcome] = {}
    for craft_slug, group in by_craft(claims).items():
        store = SqlHeldFacts(session, await craft_subject(session, craft_slug), statuses=CLOSED_STATUSES)
        for claim in group:
            fact = await _closed_twin(store, claim.text, vectors.get(claim.dedupe_key))
            if fact is not None:
                logger.info("research met fact %s again, closed as %s, and refused it", fact.id, fact.status)
                refused[claim.dedupe_key] = closed_outcome(fact)
    return refused


def by_craft(claims: Sequence[ClaimWriteBack]) -> dict[str | None, list[ClaimWriteBack]]:
    grouped: dict[str | None, list[ClaimWriteBack]] = {}
    for claim in claims:
        grouped.setdefault(claim.craft_slug, []).append(claim)
    return grouped


async def _closed_twin(store: SqlHeldFacts, statement: str, vector: list[float] | None) -> HeldFact | None:
    twin = held_twin(statement, await store.twins(None, statement))
    if twin is not None or vector is None:
        return twin
    nearest = await store.nearest(None, vector, NEIGHBOURS_MAX)
    return vector_twin(statement, nearest, at_least=VECTOR_TWIN_SIMILARITY)
