from __future__ import annotations

from functools import partial

from sqlalchemy.ext.asyncio import AsyncSession

from app.research.component_proposals import ComponentProposalDraft
from app.research.page_proposals import (
    COMPONENT,
    LISTED,
    SHOWN,
    WITHDRAWAL,
    PageWithdrawal,
    PartReport,
)

from .component_lifecycle import live_piece
from .component_withdrawals import Withdrawable
from .monograph_generated_parts import piece_subject_keys, registered_component
from .open_work_subjects import CATEGORY, WorkSubject
from .page_part_checks import PartRun, part_checked
from .page_preview_parts import SUBJECT_PREFIXES, PreviewDraft
from .page_proposals_parts import checked_part

__all__ = ["previewed_link", "previewed_withdrawals"]

SHOWN_LINK = (
    "Drawn as the registered component it links, where the page will draw it once the link is approved."
)
LISTED_LINK = (
    "{label} is another craft's own component, which the site draws only on that craft's page, so the "
    "preview lists the link without drawing it."
)
SHOWN_WITHDRAWAL = (
    "Taken off the page in the preview; propose_page takes it off every page that places it and keeps it in "
    "the record."
)
SHOWN_ASKED = (
    "Taken off the page in the preview; propose_page asks an Admin to take it off every page that places it, "
    "because this account stewards its craft but did not propose it, and it stays on until an Admin confirms."
)


async def previewed_link(
    session: AsyncSession, subject: WorkSubject, draft: PreviewDraft, index: int, link: ComponentProposalDraft
) -> PartReport:
    label = str(link.extends)
    piece = await live_piece(session, label)
    owner = None if subject.kind == CATEGORY else subject.id
    if piece.craftId is not None and piece.craftId != owner:
        return PartReport(
            part=COMPONENT, index=index, outcome=LISTED, message=LISTED_LINK.format(label=label)
        )
    held = (await piece_subject_keys(session, [piece.id])).get(piece.id, ())
    added = tuple(f"{SUBJECT_PREFIXES[each.kind]}:{each.key}" for each in link.subjects)
    keys = tuple(dict.fromkeys((*held, *added)))
    draft.components.append(registered_component(piece, keys, owner))
    return PartReport(part=COMPONENT, index=index, outcome=SHOWN, message=SHOWN_LINK)


async def previewed_withdrawals(run: PartRun, draft: PreviewDraft) -> list[PartReport]:
    reports: list[PartReport] = []
    for index, withdrawal in enumerate(run.bundle.withdrawals):
        work = partial(_withdrawn, run, draft, index, withdrawal)
        reports.append(await checked_part(run.session, WITHDRAWAL, index, work))
    return reports


async def _withdrawn(run: PartRun, draft: PreviewDraft, index: int, withdrawal: PageWithdrawal) -> PartReport:
    found: Withdrawable = await part_checked(run, WITHDRAWAL, index, withdrawal)
    draft.withdrawn.add(withdrawal.label)
    shown = SHOWN_ASKED if found.waits else SHOWN_WITHDRAWAL
    return PartReport(part=WITHDRAWAL, index=index, outcome=SHOWN, message=shown)
