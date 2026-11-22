from __future__ import annotations

import logging
import uuid
from collections.abc import Collection, Sequence

from pydantic import TypeAdapter, ValidationError
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Refused
from app.models import Craft, CuratedCraft, TermSummary
from app.research.retrieval import OPEN_CHUNK_ACLS
from app.research.vocabulary import CANONICAL_LANGUAGE

from .curated_index import CuratedPage, IndexTerm
from .term_store import glossary_term, kept_summary, stored_claims
from .term_summaries import STORED_BASIS, term_view

__all__ = ["curated_term_claims", "write_curated_term_summaries"]

logger = logging.getLogger(__name__)

GLOSSARY_KEY = CuratedPage.model_fields["glossary"].alias or "glossary"
GLOSSARY = TypeAdapter(list[IndexTerm])


async def write_curated_term_summaries(session: AsyncSession, keys: Collection[str]) -> int:
    wanted = set(keys)
    if not wanted:
        return 0
    claims = await curated_term_claims(session, wanted)
    written = 0
    for key in sorted(wanted):
        written += await _written(session, key, claims.get(key, []))
    return written


async def curated_term_claims(session: AsyncSession, keys: Collection[str]) -> dict[str, list[uuid.UUID]]:
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
            if term.term_key in keys:
                found.setdefault(term.term_key, []).extend(term.claim_ids)
    return {key: list(dict.fromkeys(claim_ids)) for key, claim_ids in found.items()}


async def _written(session: AsyncSession, key: str, claim_ids: Sequence[uuid.UUID]) -> int:
    term = await glossary_term(session, key)
    if term is None or not claim_ids:
        return 0
    stored = await stored_claims(session, claim_ids, acls=OPEN_CHUNK_ACLS)
    if not stored.views or stored.changed_at is None:
        return 0
    try:
        summary = term_view(
            term, STORED_BASIS, stored, language=CANONICAL_LANGUAGE, checked_at=stored.changed_at
        )
    except Refused:
        logger.info("the curated claims of term %s state no cited fact, so it keeps no stored summary", key)
        return 0
    english = (TermSummary.termId == term.id, TermSummary.language == CANONICAL_LANGUAGE)
    if await session.scalar(select(TermSummary.payload).where(*english)) == summary.model_dump(
        mode="json", by_alias=True
    ):
        return 0
    await kept_summary(session, term.id, summary)
    await session.execute(
        delete(TermSummary).where(TermSummary.termId == term.id, TermSummary.language != CANONICAL_LANGUAGE)
    )
    return 1
