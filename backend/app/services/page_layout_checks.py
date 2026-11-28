from __future__ import annotations

from collections.abc import Collection, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ComponentProposal, KnowledgePiece
from app.models.open_work import LIVE_PROPOSALS
from app.research.page_layout import PageLayout, is_component_ref, is_picture_ref
from app.research.page_proposals import PageComponent, PageLayoutPart

from .borrowed_placements import borrowed_problem, placed_labels
from .component_library_applies import registered_pieces
from .monograph_document import has_authored_content, monograph_content
from .monograph_generated import generated_document_of
from .open_work_subjects import WorkSubject
from .page_layout_proposals import stale_layout

__all__ = [
    "MISSING",
    "PUBLISHED_MISSING",
    "drawn_labels",
    "layout_problem",
    "missing_labels",
    "published_missing",
]

MISSING = (
    "The layout places components that no component in the library, no proposal waiting for review, no "
    "component this bundle makes and nothing the page draws holds, so the page would name them and draw "
    "nothing: {labels}. Make each in this draft with edit_draft and propose it in the same bundle, or take it "
    "out of the layout; list_components gives the labels the library holds."
)
PUBLISHED_MISSING = (
    "The published layout, version {version}, places components that no component in the library, no "
    "proposal waiting for review and nothing this bundle makes holds, so the page is drawn without them: "
    "{labels}. Make each in this draft with edit_draft and propose it with propose_page, or send a layout "
    "without it on version {version}, read with get_page and parts layout."
)


async def layout_problem(
    session: AsyncSession,
    subject: WorkSubject,
    work: tuple[Sequence[PageComponent], PageLayoutPart],
    made: Collection[str],
) -> str | None:
    components, part = work
    stale = await stale_layout(session, subject, part.base_version)
    if stale is not None:
        return stale
    missing = await missing_labels(session, [entry.ref for entry in part.entries], made)
    drawn = await drawn_labels(session, subject) if missing else set()
    missing = [label for label in missing if label not in drawn]
    if missing:
        return MISSING.format(labels=", ".join(missing))
    return await borrowed_problem(session, subject, placed_labels(components, part))


async def published_missing(
    session: AsyncSession, layout: PageLayout | None, known: Collection[str]
) -> str | None:
    if layout is None:
        return None
    missing = await missing_labels(session, [entry.ref for entry in layout.entries], known)
    if not missing:
        return None
    return PUBLISHED_MISSING.format(version=layout.version, labels=", ".join(missing))


async def missing_labels(session: AsyncSession, refs: Sequence[str], known: Collection[str]) -> list[str]:
    wanted = [
        ref
        for ref in dict.fromkeys(refs)
        if is_component_ref(ref) and not is_picture_ref(ref) and ref not in known
    ]
    if not wanted:
        return []
    held = set(
        await session.scalars(
            select(KnowledgePiece.label).where(KnowledgePiece.label.in_(wanted), *registered_pieces())
        )
    )
    held |= set(
        await session.scalars(
            select(ComponentProposal.label).where(
                ComponentProposal.label.in_(wanted), ComponentProposal.status.in_(LIVE_PROPOSALS)
            )
        )
    )
    return [ref for ref in wanted if ref not in held]


async def drawn_labels(session: AsyncSession, subject: WorkSubject) -> set[str]:
    if has_authored_content(subject.slug):
        return {component.label for component in monograph_content(subject.slug).components}
    document = await generated_document_of(session, subject)
    return set() if document is None else {component.label for component in document.content.components}
