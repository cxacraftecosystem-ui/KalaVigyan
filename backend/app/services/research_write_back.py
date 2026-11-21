from __future__ import annotations

import logging
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, InvalidInput
from app.models import Answer
from app.research.composition import ComposedAnswer
from app.research.crafts import CraftRef
from app.research.embedding import TextEmbedder
from app.research.evidence import SourceDocument
from app.research.evidence_pack import EvidencePack
from app.research.structured import StructuredModel
from app.research.write_back import ClaimWriteBack, FoundBy, WriteBackResult
from app.retrieval.indexing import EmbeddedCounts, embed_written

from .claim_pages import refresh_claim_pages
from .claim_writer import SqlClaimWriter
from .field_voices_citations import field_documents
from .live_source_store import keep_document
from .write_back_gates import gate_write_back, record_write_back_runs, research_placement
from .write_back_plan import SkippedSentence, composed_sentences, write_back_plan

__all__ = [
    "NOTHING_EMBEDDED",
    "GatedWrite",
    "StoredResearch",
    "cited_source_ids",
    "sentence_claim_ids",
    "shown_results",
    "store_live_research",
    "write_through_gates",
]

logger = logging.getLogger(__name__)

NOTHING_EMBEDDED = EmbeddedCounts(claims=0, chunks=0)
COMPARED_KEY = "compared"


@dataclass(frozen=True)
class GatedWrite:
    claims: tuple[ClaimWriteBack, ...]
    results: tuple[WriteBackResult, ...]
    held_instead: tuple[WriteBackResult, ...]
    skipped: tuple[SkippedSentence, ...]
    vectored: int
    live: bool

    def claim_ids(self) -> dict[str, uuid.UUID]:
        return {result.dedupe_key: result.claim_id for result in (*self.held_instead, *self.results)}


@dataclass(frozen=True)
class StoredResearch:
    source_ids: tuple[uuid.UUID, ...]
    results: tuple[WriteBackResult, ...]
    skipped: tuple[SkippedSentence, ...]
    embedded: EmbeddedCounts
    sentence_keys: tuple[str | None, ...] = ()
    embedding_error: str | None = None

    @property
    def created(self) -> int:
        return sum(1 for result in self.results if result.created)


async def store_live_research(
    session: AsyncSession,
    pack: EvidencePack,
    answer: ComposedAnswer,
    *,
    embed: TextEmbedder,
    found_by: FoundBy,
    answer_id: uuid.UUID | None = None,
    judge: StructuredModel | None = None,
) -> StoredResearch:
    kept = {document.item.id: await keep_document(session, document) for document in pack.documents}
    fields = await field_documents(session, pack)
    compared = await compared_crafts(session, answer_id)
    plan = write_back_plan(
        pack, answer, found_by=found_by, answer_id=answer_id, field_documents=fields, compared=compared
    )
    written = await write_through_gates(
        session, plan.claims, _documents(pack, fields), embed=embed, judge=judge
    )
    await session.commit()
    await refresh_claim_pages(session, shown_results(written.results, live=written.live))
    cited = cited_source_ids(written.claims, kept)
    embedded, error = await _embed_written(session, embed, list(written.results), cited)
    return StoredResearch(
        source_ids=tuple(dict.fromkeys(kept.values())),
        results=written.results,
        skipped=(*plan.skipped, *written.skipped),
        embedded=EmbeddedCounts(claims=embedded.claims + written.vectored, chunks=embedded.chunks),
        sentence_keys=plan.sentence_keys,
        embedding_error=error,
    )


async def write_through_gates(
    session: AsyncSession,
    claims: Sequence[ClaimWriteBack],
    documents: Mapping[str, SourceDocument],
    *,
    embed: TextEmbedder | None,
    judge: StructuredModel | None,
) -> GatedWrite:
    gated = await gate_write_back(session, claims, documents, embed=embed, judge=judge)
    placed = await research_placement(session)
    results = await SqlClaimWriter(session, status=placed.status).write(gated.claims)
    vectored = await record_write_back_runs(
        session, results, gated.runs, live=placed.live, checked_at=datetime.now(UTC)
    )
    return GatedWrite(
        claims=gated.claims,
        results=tuple(results),
        held_instead=gated.held_instead,
        skipped=gated.skipped,
        vectored=vectored,
        live=placed.live,
    )


async def compared_crafts(session: AsyncSession, answer_id: uuid.UUID | None) -> tuple[CraftRef, ...]:
    if answer_id is None:
        return ()
    understanding = await session.scalar(select(Answer.understanding).where(Answer.id == answer_id))
    compared = (understanding or {}).get(COMPARED_KEY) or []
    return tuple(CraftRef.model_validate(craft) for craft in compared)


def cited_source_ids(
    claims: Sequence[ClaimWriteBack], kept: Mapping[str, uuid.UUID]
) -> tuple[uuid.UUID, ...]:
    cited = (kept.get(citation.evidence.id) for claim in claims for citation in claim.citations)
    return tuple(dict.fromkeys(source_id for source_id in cited if source_id is not None))


def shown_results(results: Sequence[WriteBackResult], *, live: bool) -> list[uuid.UUID]:
    return [result.claim_id for result in results if live or not result.created]


def _documents(pack: EvidencePack, fields: Mapping[str, SourceDocument]) -> dict[str, SourceDocument]:
    return {document.item.id: document for document in pack.documents} | dict(fields)


async def _embed_written(
    session: AsyncSession,
    embed: TextEmbedder,
    results: list[WriteBackResult],
    source_ids: tuple[uuid.UUID, ...],
) -> tuple[EmbeddedCounts, str | None]:
    claim_ids = [result.claim_id for result in results]
    try:
        return await embed_written(session, embed, claim_ids=claim_ids, source_ids=source_ids), None
    except AppError as error:
        logger.warning("write-back stored without vectors, left for embed_knowledge: %s", error)
        return NOTHING_EMBEDDED, str(error)


def sentence_claim_ids(
    answer: ComposedAnswer, stored: StoredResearch | None
) -> tuple[tuple[uuid.UUID, ...], ...]:
    sentences = [sentence for sentence, _ in composed_sentences(answer)]
    keys = stored.sentence_keys if stored else (None,) * len(sentences)
    if len(keys) != len(sentences):
        raise InvalidInput(f"The write-back has {len(keys)} sentence keys for {len(sentences)} sentences")
    written = {result.dedupe_key: result.claim_id for result in stored.results} if stored else {}
    found: list[tuple[uuid.UUID, ...]] = []
    for sentence, key in zip(sentences, keys, strict=True):
        own = written.get(key) if key else None
        found.append(tuple(dict.fromkeys([*sentence.claim_ids, *([own] if own else [])])))
    return tuple(found)
