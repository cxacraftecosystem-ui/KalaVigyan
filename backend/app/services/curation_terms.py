from __future__ import annotations

import logging
import uuid
from collections.abc import Collection, Mapping, Sequence
from datetime import datetime
from typing import Any

from pydantic import TypeAdapter, ValidationError
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Refused
from app.models import Claim, ClaimSource, Craft, CuratedCraft, TermSummary
from app.research.retrieval import OPEN_CHUNK_ACLS
from app.research.terms import Term
from app.research.vocabulary import CANONICAL_LANGUAGE

from . import knowledge_view
from .curated_index import CuratedPage, IndexTerm
from .term_research import GlossaryTerm
from .term_store import glossary_terms, kept_summary
from .term_summaries import STORED_BASIS, StoredClaims, term_view

__all__ = ["curated_term_claims", "write_curated_term_summaries"]

logger = logging.getLogger(__name__)

GLOSSARY_KEY = CuratedPage.model_fields["glossary"].alias or "glossary"
GLOSSARY = TypeAdapter(list[IndexTerm])


async def write_curated_term_summaries(session: AsyncSession, *, keys: Collection[str] | None = None) -> int:
    claims = await curated_term_claims(session)
    if keys is not None:
        claims = {key: claim_ids for key, claim_ids in claims.items() if key in keys}
    if not claims:
        return 0
    terms = await glossary_terms(session, sorted(claims))
    every = [claim_id for claim_ids in claims.values() for claim_id in claim_ids]
    views, sources = await knowledge_view.claims_by_id(session, every, acls=OPEN_CHUNK_ACLS)
    shown = {str(key): knowledge_view.source_ref(source) for key, source in sources.items()}
    changed = await _changed_at(session, list(views))
    current = await _english_payloads(session, [term.id for term in terms.values()])
    written: list[uuid.UUID] = []
    for key in sorted(terms):
        term = terms[key]
        stored = _stored(claims[key], views, shown, changed)
        summary = _summary(term, stored)
        if summary is None or current.get(term.id) == summary.model_dump(mode="json", by_alias=True):
            continue
        await kept_summary(session, term.id, summary)
        written.append(term.id)
    if written:
        await session.execute(
            delete(TermSummary).where(
                TermSummary.termId.in_(written), TermSummary.language != CANONICAL_LANGUAGE
            )
        )
    return len(written)


async def curated_term_claims(session: AsyncSession) -> dict[str, list[uuid.UUID]]:
    rows = await session.execute(
        select(Craft.slug, CuratedCraft.page[GLOSSARY_KEY])
        .join(Craft, Craft.id == CuratedCraft.craftId)
        .order_by(Craft.slug)
    )
    found: dict[str, list[uuid.UUID]] = {}
    for slug, glossary in rows.all():
        try:
            terms = GLOSSARY.validate_python(glossary or [])
        except ValidationError:
            logger.warning(
                "the curated glossary of %s no longer meets its model; its terms are skipped", slug
            )
            continue
        for term in terms:
            if term.term_key is not None:
                found.setdefault(term.term_key, []).extend(term.claim_ids)
    return {key: list(dict.fromkeys(claim_ids)) for key, claim_ids in found.items()}


def _stored(
    claim_ids: Sequence[uuid.UUID],
    views: Mapping[uuid.UUID, knowledge_view.ClaimView],
    sources: Mapping[str, dict[str, Any]],
    changed: Mapping[uuid.UUID, datetime],
) -> StoredClaims:
    own = [views[claim_id] for claim_id in claim_ids if claim_id in views]
    stamps = [changed[view.id] for view in own if view.id in changed]
    return StoredClaims(views=own, sources=sources, changed_at=max(stamps) if stamps else None)


def _summary(term: GlossaryTerm, stored: StoredClaims) -> Term | None:
    if not stored.views or stored.changed_at is None:
        return None
    try:
        return term_view(
            term, STORED_BASIS, stored, language=CANONICAL_LANGUAGE, checked_at=stored.changed_at
        )
    except Refused:
        logger.info(
            "the curated claims of term %s state no cited fact, so it keeps no stored summary", term.key
        )
        return None


async def _changed_at(session: AsyncSession, claim_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, datetime]:
    if not claim_ids:
        return {}
    stamps = dict(
        (await session.execute(select(Claim.id, Claim.updatedAt).where(Claim.id.in_(claim_ids)))).all()
    )
    cited = await session.execute(
        select(ClaimSource.claimId, func.max(ClaimSource.updatedAt))
        .where(ClaimSource.claimId.in_(claim_ids))
        .group_by(ClaimSource.claimId)
    )
    for claim_id, stamp in cited.all():
        stamps[claim_id] = max(stamps.get(claim_id, stamp), stamp)
    return stamps


async def _english_payloads(session: AsyncSession, term_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, Any]:
    if not term_ids:
        return {}
    rows = await session.execute(
        select(TermSummary.termId, TermSummary.payload).where(
            TermSummary.termId.in_(term_ids), TermSummary.language == CANONICAL_LANGUAGE
        )
    )
    return dict(rows.all())
