from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput
from app.data.craft_master_loader import ID_NAMESPACE
from app.models import Chunk, Source
from app.research.evidence import EvidenceItem, SourceDocument, canonical_url
from app.research.licences import open_licence
from app.research.retrieval import PUBLIC_CHUNK_ACL, RESEARCHER_CHUNK_ACL
from app.research.storable import storable_text
from app.research.write_back import WRITE_BACK_ORIGIN
from app.retrieval.indexing import replace_source_chunks
from app.retrieval.quote_passages import source_passages

__all__ = [
    "CONTENT_STORAGE",
    "QuoteChunk",
    "chunk_acl",
    "chunk_for_quote",
    "keep_document",
    "live_source_id",
    "source_for",
    "source_values",
]

CONTENT_STORAGE = {"FULL_TEXT": "FULL_TEXT", "ABSTRACT": "EXCERPT", "EXCERPT": "EXCERPT"}
FULL_TEXT = "FULL_TEXT"
LINK_ONLY = "LINK_ONLY"
SELF_DECLARED_LICENCE_TIERS = ("T4",)
EVIDENCE_ID_KEY = "evidenceId"


@dataclass(frozen=True)
class QuoteChunk:
    chunk_id: uuid.UUID
    locator: str | None


def live_source_id(source_key: str) -> uuid.UUID:
    return uuid.uuid5(ID_NAMESPACE, f"live-source:{source_key}")


def chunk_acl(document: SourceDocument) -> str:
    if document.content != "FULL_TEXT":
        return PUBLIC_CHUNK_ACL
    item = document.item
    if item.tier in SELF_DECLARED_LICENCE_TIERS or not open_licence(item.licence):
        return RESEARCHER_CHUNK_ACL
    return PUBLIC_CHUNK_ACL


def source_values(item: EvidenceItem, document: SourceDocument | None = None) -> dict[str, Any]:
    return {
        "id": live_source_id(item.source_key),
        "kind": item.source_type,
        "title": storable_text(item.title),
        "authors": [storable_text(author) for author in item.authors],
        "year": int(item.published[:4]) if item.published else None,
        "doi": item.doi,
        "url": item.url,
        "publisher": _storable_or_none(item.publisher),
        "licence": _storable_or_none(item.licence),
        "reliability": item.trust,
        "storage": CONTENT_STORAGE[document.content] if document else LINK_ONLY,
        "sha256": document.text_sha256 if document else None,
        "retrievedAt": item.retrieved_at,
        "origin": WRITE_BACK_ORIGIN,
        "attribution": _storable_or_none(item.attribution),
        "externalIds": {**item.external_ids, EVIDENCE_ID_KEY: item.id},
    }


async def source_for(
    session: AsyncSession, item: EvidenceItem, document: SourceDocument | None = None
) -> Source:
    existing = await _existing(session, item)
    if existing is not None:
        return existing
    await session.execute(insert(Source).values(source_values(item, document)).on_conflict_do_nothing())
    stored = await _existing(session, item)
    if stored is None:
        raise InvalidInput(f"The source {item.source_key} could not be stored")
    return stored


async def keep_document(session: AsyncSession, document: SourceDocument) -> uuid.UUID:
    source = await source_for(session, document.item, document)
    if await _has_chunks(session, source.id) and not _replaces(source, document):
        return source.id
    await _refresh_live_source(session, source, document)
    await replace_source_chunks(session, source.id, document.text, acl=chunk_acl(document))
    return source.id


async def chunk_for_quote(session: AsyncSession, source_id: uuid.UUID, quote: str) -> QuoteChunk | None:
    found = (await source_passages(session, source_id)).holding(quote)
    return None if found is None else QuoteChunk(chunk_id=found.chunk_id, locator=found.locator)


async def _existing(session: AsyncSession, item: EvidenceItem) -> Source | None:
    same = [Source.id == live_source_id(item.source_key)]
    if item.doi:
        same.append(func.lower(Source.doi) == item.doi.lower())
    else:
        same.append(Source.url.in_(sorted({item.url, canonical_url(item.url)})))
    return await session.scalar(
        select(Source).where(or_(*same)).order_by(Source.createdAt, Source.id).limit(1)
    )


async def _refresh_live_source(session: AsyncSession, source: Source, document: SourceDocument) -> None:
    if source.origin != WRITE_BACK_ORIGIN:
        return
    await session.execute(
        update(Source)
        .where(Source.id == source.id)
        .values(
            storage=CONTENT_STORAGE[document.content],
            sha256=document.text_sha256,
            retrievedAt=document.item.retrieved_at,
        )
    )


def _replaces(source: Source, document: SourceDocument) -> bool:
    full_text = CONTENT_STORAGE[document.content] == FULL_TEXT
    if source.origin != WRITE_BACK_ORIGIN:
        return full_text
    return full_text or source.storage != FULL_TEXT


def _storable_or_none(text: str | None) -> str | None:
    return None if text is None else storable_text(text)


async def _has_chunks(session: AsyncSession, source_id: uuid.UUID) -> bool:
    found = await session.scalar(select(Chunk.id).where(Chunk.sourceId == source_id).limit(1))
    return found is not None
