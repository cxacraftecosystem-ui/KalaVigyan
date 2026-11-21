from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Refused
from app.core.roles import Capability, can
from app.models import Craft, CraftCategory, LayoutProposal, User
from app.research.layout_proposals import (
    STORED,
    WRITTEN,
    LayoutProposalDraft,
    LayoutProposalResult,
    LayoutSubject,
)

from .open_work_subjects import CATEGORY, WorkSubject, subject_by_key
from .page_layouts import STALE_LAYOUT, layout_of, store_layout, subject_path

__all__ = [
    "APPROVED",
    "PENDING",
    "REJECTED",
    "current_version",
    "proposal_subject",
    "propose_layout",
]

PENDING, APPROVED, REJECTED = "PENDING", "APPROVED", "REJECTED"
STALE = (
    "The layout of {slug} is at version {current}, not {base}. Read it with get_page and build on "
    "version {current}."
)
MESSAGES = {
    STORED: (
        "Stored for review: an Admin approves or rejects it, and approval writes it as the page's next layout "
        "version. Who proposed it is kept privately."
    ),
    WRITTEN: "Written at once as version {version} of the page's layout, because your account reviews layouts.",
}


async def propose_layout(
    session: AsyncSession, user: User, draft: LayoutProposalDraft, *, origin: str, site: str, now: datetime
) -> LayoutProposalResult:
    subject = await subject_by_key(session, draft.subject.kind, draft.subject.slug)
    current = await current_version(session, subject)
    if draft.base_version != current:
        raise Refused(STALE_LAYOUT, STALE.format(slug=subject.slug, current=current, base=draft.base_version))
    written = None
    if can(user, Capability.REVIEW_CONTRIBUTIONS):
        written = (await store_layout(session, subject, draft.entries, actor=user)).version
    row = _row(draft, subject, user, origin=origin, written=written, now=now)
    session.add(row)
    await session.flush()
    outcome = STORED if written is None else WRITTEN
    return LayoutProposalResult(
        outcome=outcome,
        proposal_id=row.id,
        status=row.status,
        subject=LayoutSubject(kind=subject.kind, slug=subject.slug),
        base_version=draft.base_version,
        version=written,
        page_url=f"{site}{subject_path(subject)}",
        message=MESSAGES[outcome].format(version=written),
    )


async def current_version(session: AsyncSession, subject: WorkSubject) -> int:
    layout = await layout_of(session, subject)
    return 0 if layout is None else layout.version


async def proposal_subject(session: AsyncSession, row: LayoutProposal) -> WorkSubject:
    owner = (
        await session.get(CraftCategory, row.categoryId)
        if row.subjectKind == CATEGORY
        else await session.get(Craft, row.craftId)
    )
    if owner is None:
        raise Refused(STALE_LAYOUT, "The page this layout was proposed for no longer exists.")
    return await subject_by_key(session, row.subjectKind, owner.slug)


def _row(
    draft: LayoutProposalDraft,
    subject: WorkSubject,
    user: User,
    *,
    origin: str,
    written: int | None,
    now: datetime,
) -> LayoutProposal:
    category = subject.kind == CATEGORY
    return LayoutProposal(
        id=uuid.uuid4(),
        proposerId=user.id,
        subjectKind=subject.kind,
        craftId=None if category else subject.id,
        categoryId=subject.id if category else None,
        baseVersion=draft.base_version,
        entries=[entry.model_dump(mode="json", by_alias=True, exclude_none=True) for entry in draft.entries],
        note=draft.note,
        origin=origin,
        status=PENDING if written is None else APPROVED,
        reviewedById=None if written is None else user.id,
        reviewedAt=None if written is None else now,
        layoutVersion=written,
    )
