from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import replace
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Chunk, ClaimSource
from app.research.retrieval import OPEN_CHUNK_ACLS, PASSAGE_CHUNK_KIND, RESTRICTED_SENSITIVITY

from .answer_events import CitedClaims

__all__ = ["CONTEXT_ACLS", "with_contexts"]

CONTEXT_ACLS: tuple[str, ...] = OPEN_CHUNK_ACLS


async def with_contexts(session: AsyncSession, cited: CitedClaims) -> CitedClaims:
    cite_ids = {_uuid(c["id"]) for view in cited.views.values() for c in view.citations if c.get("quote")}
    passages = await _passages(session, {cite for cite in cite_ids if cite is not None})
    if not passages:
        return cited
    views = {
        claim_id: replace(view, citations=[_placed(citation, passages) for citation in view.citations])
        for claim_id, view in cited.views.items()
    }
    return CitedClaims(views=views, sources=cited.sources)


async def _passages(session: AsyncSession, cite_ids: set[uuid.UUID]) -> dict[str, str]:
    if not cite_ids:
        return {}
    rows = await session.execute(
        select(ClaimSource.id, Chunk.text)
        .join(Chunk, Chunk.id == ClaimSource.chunkId)
        .where(
            ClaimSource.id.in_(cite_ids),
            Chunk.acl.in_(CONTEXT_ACLS),
            Chunk.kind == PASSAGE_CHUNK_KIND,
            Chunk.sensitivity != RESTRICTED_SENSITIVITY,
        )
    )
    return {str(cite_id): text for cite_id, text in rows}


def _placed(citation: Mapping[str, Any], passages: Mapping[str, str]) -> dict[str, Any]:
    passage = passages.get(citation["id"]) if citation.get("quote") else None
    return {**citation, "context": passage} if passage else dict(citation)


def _uuid(text: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(text)
    except ValueError:
        return None
