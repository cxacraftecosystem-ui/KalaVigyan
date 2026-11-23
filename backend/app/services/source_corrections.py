from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput
from app.models import Claim, ClaimSource, Source
from app.research.front_page import producer_token
from app.research.page_revalidation import PageOwners
from app.research.staged_reviews import SourceFix
from app.research.storable import storable_text

from . import audit
from .page_revalidation import claim_owners
from .review_queue_errors import DecisionConflict, UnknownItem
from .source_titles import retitle_source

__all__ = ["CORRECTED", "DIFFER_CLEARED", "clear_sources_differ", "correct_source", "source_label"]

CORRECTED = "source.corrected"
DIFFER_CLEARED = "review.sources_differ_cleared"
COLUMNS = {"authors": "authors", "year": "year", "container_title": "containerTitle", "kind": "kind"}
NO_SOURCE = "No source has the id {id}."
NO_FACT = "No fact has the id {id}."
UNCHANGED = "The source already says this, so nothing would change."
NOT_FLAGGED = "This fact is not marked as one whose sources differ."
PRODUCER_AUTHOR = "{author!r} names the program that made a file, not an author."


async def source_label(session: AsyncSession, source_id: uuid.UUID) -> str | None:
    title: str | None = await session.scalar(select(Source.title).where(Source.id == source_id))
    return title


async def correct_source(
    session: AsyncSession, source_id: uuid.UUID, fix: SourceFix, *, actor: Any
) -> PageOwners:
    source = await session.get(Source, source_id, with_for_update=True, populate_existing=True)
    if source is None:
        raise UnknownItem(NO_SOURCE.format(id=source_id))
    changes = _changes(source, fix)
    retitled = fix.title is not None and fix.title.strip() != source.title
    if not changes and not retitled:
        raise DecisionConflict(UNCHANGED)
    if retitled and fix.title is not None:
        await retitle_source(session, source_id, fix.title, actor=actor)
    if changes:
        before = {field: getattr(source, COLUMNS[field]) for field in changes}
        await session.execute(
            update(Source).where(Source.id == source_id).values({COLUMNS[f]: v for f, v in changes.items()})
        )
        detail = {field: {"from": before[field], "to": value} for field, value in changes.items()}
        await audit.record(
            session, action=CORRECTED, actor=actor, target_type="Source", target_id=source_id, detail=detail
        )
    return await claim_owners(session, await _citing(session, source_id))


async def clear_sources_differ(
    session: AsyncSession, claim_id: uuid.UUID, *, actor: Any, reason: str
) -> PageOwners:
    claim = await session.get(Claim, claim_id, with_for_update=True, populate_existing=True)
    if claim is None:
        raise UnknownItem(NO_FACT.format(id=claim_id))
    if not claim.sourcesDiffer:
        raise DecisionConflict(NOT_FLAGGED)
    about = claim.differsOn
    await session.execute(
        update(Claim).where(Claim.id == claim_id).values(sourcesDiffer=False, differsOn=None)
    )
    await audit.record(
        session,
        action=DIFFER_CLEARED,
        actor=actor,
        target_type="Claim",
        target_id=claim_id,
        detail={"differsOn": about, "reason": reason},
    )
    return await claim_owners(session, [claim_id])


def _changes(source: Source, fix: SourceFix) -> dict[str, Any]:
    wanted: dict[str, Any] = {}
    if fix.authors is not None:
        authors = [storable_text(" ".join(author.split())) for author in fix.authors]
        for author in authors:
            if producer_token(author):
                raise InvalidInput(PRODUCER_AUTHOR.format(author=author))
        wanted["authors"] = authors
    if fix.container_title is not None:
        wanted["container_title"] = storable_text(fix.container_title.strip())
    if fix.year is not None:
        wanted["year"] = fix.year
    if fix.kind is not None:
        wanted["kind"] = fix.kind
    return {field: value for field, value in wanted.items() if getattr(source, COLUMNS[field]) != value}


async def _citing(session: AsyncSession, source_id: uuid.UUID) -> list[uuid.UUID]:
    rows = await session.scalars(select(ClaimSource.claimId).where(ClaimSource.sourceId == source_id))
    return list(rows.all())
