from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput
from app.models import PageProposal, User
from app.research.monograph_document import MonographDocument
from app.research.page_changes import page_changes
from app.research.page_proposal_parts import proposal_parts
from app.research.page_proposals import PageBundle, PageProposalResult

from .monograph_generated import generated_document_of
from .page_preview import previewed_document
from .page_proposal_pictures import move_preview_pictures
from .page_translation_preview import only_translation

__all__ = ["NO_SNAPSHOT", "PageSnapshot", "page_snapshot", "record_page_proposal"]


@dataclass(frozen=True)
class PageSnapshot:
    before: MonographDocument | None = None
    after: MonographDocument | None = None


NO_SNAPSHOT = PageSnapshot()


async def page_snapshot(
    session: AsyncSession, user: User, bundle: PageBundle, *, now: datetime
) -> PageSnapshot:
    if only_translation(bundle):
        return NO_SNAPSHOT
    try:
        previewed = await previewed_document(session, user, bundle, now=now)
    except InvalidInput:
        return NO_SNAPSHOT
    before = await generated_document_of(session, previewed.subject)
    return PageSnapshot(before=before, after=previewed.document)


async def record_page_proposal(
    session: AsyncSession,
    user: User,
    work: tuple[PageBundle, PageProposalResult, PageSnapshot],
    *,
    origin: str,
    now: datetime,
) -> PageProposal | None:
    bundle, result, snapshot = work
    parts = proposal_parts(bundle, result.parts, snapshot.after)
    if not parts:
        return None
    changes = [] if snapshot.after is None else page_changes(snapshot.before, snapshot.after)
    after = _stored(snapshot.after)
    row = PageProposal(
        userId=user.id,
        subjectKind=result.subject.kind,
        subjectSlug=result.subject.slug,
        origin=origin,
        parts=[part.model_dump(mode="json") for part in parts],
        changes=[chapter.model_dump(mode="json") for chapter in changes],
        before=_stored(snapshot.before),
        after=after,
        decisions=[],
        createdAt=now,
    )
    session.add(row)
    await session.flush()
    await move_preview_pictures(session, row, after, now=now)
    return row


def _stored(document: MonographDocument | None) -> dict[str, Any] | None:
    return None if document is None else document.model_dump(mode="json", by_alias=True)
