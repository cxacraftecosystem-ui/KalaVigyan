from __future__ import annotations

import uuid
from collections.abc import Collection, Sequence
from dataclasses import dataclass, replace
from itertools import batched
from typing import Any

from pydantic import TypeAdapter
from sqlalchemy import ColumnElement, Select, delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import release_connection
from app.core.errors import InvalidInput
from app.models import Chunk, Claim, KnowledgePiece, Source
from app.research.embedding import TextEmbedder, checked_vectors
from app.research.explainer import Block
from app.research.knowledge_pieces import piece_text
from app.research.retrieval import (
    HIDDEN_CLAIM_STATUSES,
    PUBLIC_CHUNK_ACL,
    RESTRICTED_SENSITIVITY,
    VISIBLE_SENSITIVITY,
)
from app.research.storable import storable_text

from .chunking import TextChunk, chunk_text
from .citation_links import cited_quotes, relink_quotes
from .claim_titles import claim_document, titled_claims
from .deadline import Deadline
from .stamps import current_embedding_model, needs_model_vector, needs_vector, renewal_order
from .text import document_text

__all__ = [
    "EMBED_BATCH",
    "EMBED_RUN_ROWS",
    "EmbeddedCounts",
    "SourceChunk",
    "embed_pending",
    "embed_pieces",
    "embed_written",
    "replace_planned_chunks",
    "replace_source_chunks",
]

EMBED_BATCH = 50
EMBED_RUN_ROWS = 20000
BLOCKS = TypeAdapter(Block)


@dataclass(frozen=True)
class EmbeddedCounts:
    claims: int
    chunks: int
    pieces: int = 0
    complete: bool = True


@dataclass(frozen=True)
class SourceChunk:
    text: str
    locator: str
    lang: str
    acl: str


@dataclass(frozen=True)
class _Pending:
    id: uuid.UUID
    text: str
    read: Any


@dataclass(frozen=True)
class _Wanted:
    claims: ColumnElement[bool] | None
    chunks: ColumnElement[bool] | None
    renew: bool

    def lacking(self, embedding: Any, stamp: Any) -> ColumnElement[bool]:
        return needs_vector(embedding, stamp) if self.renew else needs_model_vector(embedding, stamp)


async def replace_source_chunks(
    session: AsyncSession, source_id: uuid.UUID, text: str, *, lang: str = "en", acl: str = PUBLIC_CHUNK_ACL
) -> int:
    source = await session.get(Source, source_id)
    if source is None:
        raise InvalidInput(f"No source has the id {source_id}")
    pieces = chunk_text(text)
    cited = await cited_quotes(session, source_id)
    stored = {
        chunk.ordinal: chunk
        for chunk in (await session.scalars(select(Chunk).where(Chunk.sourceId == source_id))).all()
    }
    for piece in pieces:
        _apply(session, stored.get(piece.ordinal), piece, source=source, lang=lang, acl=acl)
    await session.execute(delete(Chunk).where(Chunk.sourceId == source_id, Chunk.ordinal >= len(pieces)))
    await session.flush()
    return len(pieces) + await relink_quotes(session, source, cited, lang=lang)


async def replace_planned_chunks(
    session: AsyncSession, source_id: uuid.UUID, chunks: Sequence[SourceChunk]
) -> int:
    source = await session.get(Source, source_id)
    if source is None:
        raise InvalidInput(f"No source has the id {source_id}")
    if not chunks:
        raise InvalidInput(f"Source {source_id} is given no chunks to store")
    stored = {
        chunk.ordinal: chunk
        for chunk in (await session.scalars(select(Chunk).where(Chunk.sourceId == source_id))).all()
    }
    for ordinal, planned in enumerate(chunks):
        piece = TextChunk(ordinal=ordinal, text=planned.text, locator=planned.locator)
        _apply(session, stored.get(ordinal), piece, source=source, lang=planned.lang, acl=planned.acl)
    await session.execute(delete(Chunk).where(Chunk.sourceId == source_id, Chunk.ordinal >= len(chunks)))
    await session.flush()
    return len(chunks)


async def embed_pending(
    session: AsyncSession,
    embed: TextEmbedder,
    *,
    batch_size: int = EMBED_BATCH,
    deadline: Deadline | None = None,
) -> EmbeddedCounts:
    counts = await _embed(
        session,
        embed,
        _Wanted(claims=None, chunks=None, renew=True),
        batch_size=batch_size,
        deadline=deadline,
    )
    pending = await _pending_pieces(session, None)
    pieces = await _fill(session, embed, KnowledgePiece, pending, batch_size=batch_size, deadline=deadline)
    return replace(counts, pieces=pieces, complete=counts.complete and pieces == len(pending))


async def embed_pieces(
    session: AsyncSession,
    embed: TextEmbedder,
    *,
    piece_ids: Collection[uuid.UUID] | None,
    batch_size: int = EMBED_BATCH,
    deadline: Deadline | None = None,
) -> int:
    _check_batch(batch_size)
    scope = None if piece_ids is None else KnowledgePiece.id.in_(list(piece_ids))
    pending = await _pending_pieces(session, scope)
    return await _fill(session, embed, KnowledgePiece, pending, batch_size=batch_size, deadline=deadline)


async def embed_written(
    session: AsyncSession,
    embed: TextEmbedder,
    *,
    claim_ids: Collection[uuid.UUID],
    source_ids: Collection[uuid.UUID],
    batch_size: int = EMBED_BATCH,
) -> EmbeddedCounts:
    scopes = _Wanted(
        claims=Claim.id.in_(list(claim_ids)), chunks=Chunk.sourceId.in_(list(source_ids)), renew=False
    )
    return await _embed(session, embed, scopes, batch_size=batch_size)


async def _embed(
    session: AsyncSession,
    embed: TextEmbedder,
    wanted: _Wanted,
    *,
    batch_size: int,
    deadline: Deadline | None = None,
) -> EmbeddedCounts:
    _check_batch(batch_size)
    claims = await _pending_claims(session, wanted)
    claimed = await _fill(session, embed, Claim, claims, batch_size=batch_size, deadline=deadline)
    chunks = await _pending_chunks(session, wanted)
    chunked = await _fill(session, embed, Chunk, chunks, batch_size=batch_size, deadline=deadline)
    return EmbeddedCounts(
        claims=claimed, chunks=chunked, complete=claimed == len(claims) and chunked == len(chunks)
    )


def _check_batch(batch_size: int) -> None:
    if batch_size < 1:
        raise InvalidInput(f"An embedding batch holds at least one text, not {batch_size}")


def _over(deadline: Deadline | None) -> bool:
    return deadline is not None and deadline.passed()


def _apply(
    session: AsyncSession, chunk: Chunk | None, piece: TextChunk, *, source: Source, lang: str, acl: str
) -> None:
    text = storable_text(piece.text)
    if chunk is None:
        session.add(
            Chunk(
                sourceId=source.id,
                ordinal=piece.ordinal,
                locator=piece.locator,
                text=text,
                lang=lang,
                acl=acl,
                sensitivity=source.sensitivity,
            )
        )
        return
    if chunk.text != text:
        chunk.text = text
        chunk.embedding = None
    chunk.locator = piece.locator
    chunk.lang = lang
    chunk.acl = acl
    chunk.sensitivity = source.sensitivity


async def _pending_claims(session: AsyncSession, wanted: _Wanted) -> list[_Pending]:
    statement = titled_claims().where(
        wanted.lacking(Claim.embedding, Claim.embeddingModel),
        Claim.sensitivity == VISIBLE_SENSITIVITY,
        Claim.status.not_in(HIDDEN_CLAIM_STATUSES),
    )
    order = renewal_order(Claim.embedding, Claim.embeddingModel, Claim.updatedAt)
    ordered = _scoped(statement, wanted.claims).order_by(*order, Claim.id)
    rows = await session.execute(ordered.limit(EMBED_RUN_ROWS))
    return [_Pending(row.id, claim_document(row), row.text) for row in rows]


async def _pending_chunks(session: AsyncSession, wanted: _Wanted) -> list[_Pending]:
    statement = (
        select(Chunk.id, Chunk.text, Source.title)
        .join(Source, Source.id == Chunk.sourceId)
        .where(
            wanted.lacking(Chunk.embedding, Chunk.embeddingModel),
            Chunk.sensitivity != RESTRICTED_SENSITIVITY,
            Source.sensitivity != RESTRICTED_SENSITIVITY,
        )
    )
    order = renewal_order(Chunk.embedding, Chunk.embeddingModel, Chunk.updatedAt)
    ordered = _scoped(statement, wanted.chunks).order_by(*order, Chunk.id)
    rows = await session.execute(ordered.limit(EMBED_RUN_ROWS))
    return [_Pending(row.id, document_text(row.text, title=row.title), row.text) for row in rows]


async def _pending_pieces(session: AsyncSession, scope: ColumnElement[bool] | None) -> list[_Pending]:
    statement = select(KnowledgePiece.id, KnowledgePiece.payload).where(
        KnowledgePiece.embedding.is_(None),
        KnowledgePiece.supersededById.is_(None),
        KnowledgePiece.label.is_(None),
    )
    rows = await session.execute(_scoped(statement, scope).order_by(KnowledgePiece.id).limit(EMBED_RUN_ROWS))
    return [
        _Pending(row.id, document_text(piece_text(BLOCKS.validate_python(row.payload))), row.payload)
        for row in rows
    ]


def _scoped[T: tuple[object, ...]](statement: Select[T], scope: ColumnElement[bool] | None) -> Select[T]:
    return statement if scope is None else statement.where(scope)


async def _fill(
    session: AsyncSession,
    embed: TextEmbedder,
    model: type[Claim] | type[Chunk] | type[KnowledgePiece],
    pending: Sequence[_Pending],
    *,
    batch_size: int,
    deadline: Deadline | None = None,
) -> int:
    done = 0
    for group in batched(pending, batch_size, strict=False):
        if _over(deadline):
            break
        texts = [item.text for item in group]
        await release_connection(session)
        vectors = checked_vectors(await embed(texts), expected=len(texts))
        for item, vector in zip(group, vectors, strict=True):
            written = await session.execute(
                update(model)
                .where(model.id == item.id, _unchanged(model, item.read))
                .values(_vector_values(model, vector))
            )
            done += int(written.rowcount or 0)
        await session.commit()
    return done


def _unchanged(model: type[Claim] | type[Chunk] | type[KnowledgePiece], read: Any) -> ColumnElement[bool]:
    if model is KnowledgePiece:
        return KnowledgePiece.payload == read
    if model is Claim:
        return Claim.text == read
    return Chunk.text == read


def _vector_values(
    model: type[Claim] | type[Chunk] | type[KnowledgePiece], vector: list[float]
) -> dict[str, Any]:
    if model is KnowledgePiece:
        return {"embedding": vector}
    return {"embedding": vector, "embeddingModel": current_embedding_model()}
