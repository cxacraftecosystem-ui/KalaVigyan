from __future__ import annotations

import hashlib
import logging
from collections.abc import Mapping

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.composer.candidates import STORED_PASSAGES_ADAPTER, offered_passages, stored_passage_id
from app.models import Source
from app.research.evidence import EvidenceItem, SourceDocument
from app.research.evidence_pack import EvidencePack
from app.research.field_voices import FIELD_SOURCE_KIND
from app.research.retrieval import ChunkHit

from .knowledge_view import source_ref

__all__ = [
    "PASSAGE_CONTENT",
    "PASSAGE_TIER",
    "passage_document",
    "stored_document",
    "stored_documents",
    "stored_hits",
]

logger = logging.getLogger(__name__)

PASSAGE_TIER = "T3"
PASSAGE_CONTENT = "EXCERPT"


def stored_hits(pack: EvidencePack) -> list[ChunkHit]:
    return [hit for hit in offered_passages(pack.stored.chunks) if hit.source_kind != FIELD_SOURCE_KIND]


async def stored_documents(session: AsyncSession, pack: EvidencePack) -> Mapping[str, SourceDocument]:
    hits = stored_hits(pack)
    if not hits:
        return {}
    wanted = {hit.source_id for hit in hits}
    sources = {row.id: row for row in await session.scalars(select(Source).where(Source.id.in_(wanted)))}
    documents: dict[str, SourceDocument] = {}
    for hit in hits:
        source = sources.get(hit.source_id)
        document = stored_document(hit, source) if source is not None else None
        if document is not None:
            documents[document.item.id] = document
    return documents


def stored_document(hit: ChunkHit, source: Source) -> SourceDocument | None:
    ref = source_ref(source)
    if ref["url"] is None or source.retrievedAt is None:
        logger.info(
            "stored passage %s cannot be cited: its source has no https address or reading date", hit.chunk_id
        )
        return None
    try:
        item = EvidenceItem(
            id=stored_passage_id(hit),
            adapter=STORED_PASSAGES_ADAPTER,
            tier=PASSAGE_TIER,
            source_type=source.kind,
            url=ref["url"],
            title=source.title,
            authors=ref["authors"],
            published=str(source.year) if source.year else None,
            retrieved_at=source.retrievedAt,
            licence=source.licence,
            attribution=source.attribution,
            doi=source.doi,
            publisher=source.publisher,
            trust=source.reliability,
        )
    except ValidationError as error:
        logger.warning("stored passage %s cannot be cited from source %s: %s", hit.chunk_id, source.id, error)
        return None
    return passage_document(item, hit)


def passage_document(item: EvidenceItem, hit: ChunkHit) -> SourceDocument:
    digest = hashlib.sha256(hit.text.encode("utf-8")).hexdigest()
    return SourceDocument(
        item=item, text=hit.text, text_sha256=digest, truncated=False, content=PASSAGE_CONTENT
    )
