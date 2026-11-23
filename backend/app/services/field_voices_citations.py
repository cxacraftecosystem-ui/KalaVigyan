from __future__ import annotations

from collections.abc import Mapping, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.composer.candidates import field_evidence_id
from app.models import Source
from app.research.evidence import EvidenceItem, SourceDocument
from app.research.evidence_pack import EvidencePack
from app.research.field_voices import FIELD_SOURCE_KIND, FIELD_VOICES_ADAPTER
from app.research.retrieval import ChunkHit

from .write_back_stored import PASSAGE_TIER, passage_document

__all__ = ["FIELD_TRUST", "field_documents", "field_hit_documents", "field_hits"]

FIELD_TRUST = "A"


def field_hits(pack: EvidencePack) -> list[ChunkHit]:
    return [hit for hit in pack.stored.chunks if hit.source_kind == FIELD_SOURCE_KIND]


async def field_documents(session: AsyncSession, pack: EvidencePack) -> Mapping[str, SourceDocument]:
    return await field_hit_documents(session, field_hits(pack))


async def field_hit_documents(session: AsyncSession, hits: Sequence[ChunkHit]) -> dict[str, SourceDocument]:
    if not hits:
        return {}
    sources = {
        row.id: row
        for row in await session.scalars(
            select(Source).where(
                Source.id.in_({hit.source_id for hit in hits}), Source.kind == FIELD_SOURCE_KIND
            )
        )
    }
    documents: dict[str, SourceDocument] = {}
    for hit in hits:
        source = sources.get(hit.source_id)
        if source is None or not (source.url or "").startswith("https://") or source.retrievedAt is None:
            continue
        document = passage_document(_item(hit, source), hit)
        documents[document.item.id] = document
    return documents


def _item(hit: ChunkHit, source: Source) -> EvidenceItem:
    return EvidenceItem(
        id=field_evidence_id(hit),
        adapter=FIELD_VOICES_ADAPTER,
        tier=PASSAGE_TIER,
        source_type=FIELD_SOURCE_KIND,
        url=source.url or "",
        title=source.title,
        authors=[str(author) for author in source.authors],
        published=str(source.year) if source.year else None,
        retrieved_at=source.retrievedAt,
        attribution=source.attribution,
        publisher=source.publisher,
        trust=FIELD_TRUST,
    )
