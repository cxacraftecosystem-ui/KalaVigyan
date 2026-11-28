from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from functools import partial
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import COMPONENT_PROPOSALS, FACT_PROPOSALS, LAYOUT_PROPOSALS, STRUCTURE_PROPOSALS
from app.models import User
from app.research.fetcher import Fetcher
from app.research.knowledge_writes import FactProposal
from app.research.layout_proposals import LayoutProposalDraft, LayoutSubject
from app.research.page_proposals import (
    ACCEPTED,
    COMPONENT,
    FACT,
    LAYOUT,
    PICTURE,
    REFUSED,
    SECTION,
    STRUCTURE,
    WITHDRAWAL,
    PageBundle,
    PageComponent,
    PageLayoutPart,
    PagePicture,
    PageProposalResult,
    PageSubject,
    PageWithdrawal,
    PartReport,
)
from app.research.review_switch import REFUSED as FACT_REFUSED
from app.research.section_proposals import REFUSED as SECTION_REFUSED, SectionPart
from app.research.structure_proposals import REFUSED as STRUCTURE_REFUSED, StructureProposal
from app.research.structured import StructuredModel
from app.research.upload_links import OPEN, SlotDeclaration, UploadSlot, UploadStart

from .component_lifecycle import withdraw_registered
from .component_proposals import CheckedProposal, stored_proposal
from .component_withdrawals import ASKED_STATUS, ask_withdrawal, withdrawable_piece
from .fact_proposals import ProposalAdapters, propose_fact
from .open_work_subjects import WorkSubject, subject_by_key
from .page_layout_proposals import propose_layout
from .page_layouts import subject_path
from .page_part_checks import PartRun, part_checked
from .page_preview_pictures import given_picture_report
from .page_proposals_parts import (
    BundleFacts,
    accepted,
    checked_part,
    component_report,
    picture_claims,
    refused,
)
from .page_renders import refuse_a_failed_drawing
from .page_translations import checked_translation
from .section_proposals import SectionContext, propose_section
from .structure_proposals import propose_structure

__all__ = ["PageTools", "PictureStarter", "propose_page"]

PictureStarter = Callable[[UploadSlot, SlotDeclaration | None], Awaitable[UploadStart]]
SUMMARY = (
    "{accepted} of {total} parts of the bundle were accepted and {refused} refused, each with its reason."
)
WITHDRAWN_STATUS = "WITHDRAWN"
WITHDRAWN = "Withdrawn: {label} is off every page that placed it, and kept in the record."


@dataclass(frozen=True)
class PageTools:
    gates: ProposalAdapters
    fetcher: Fetcher
    start_picture: PictureStarter
    spend: Callable[[str], Awaitable[None]]
    origin: str
    site: str
    judges: Sequence[StructuredModel] = ()


@dataclass
class _Run:
    session: AsyncSession
    user: User
    bundle: PageBundle
    subject: WorkSubject
    tools: PageTools
    now: datetime
    checks: PartRun
    reports: list[PartReport] = field(default_factory=list)

    @property
    def facts(self) -> BundleFacts:
        return self.checks.facts


async def propose_page(
    session: AsyncSession, user: User, bundle: PageBundle, *, tools: PageTools, now: datetime
) -> PageProposalResult:
    subject = await subject_by_key(session, bundle.subject.kind, bundle.subject.slug)
    await refuse_a_failed_drawing(session, user.id, subject, now=now)
    checks = PartRun(session, user, bundle, subject, BundleFacts(), now)
    run = _Run(session, user, bundle, subject, tools, now, checks)
    for index, fact in enumerate(bundle.facts):
        await _record(run, FACT, index, partial(_fact, run, index, fact))
    for index, item in enumerate(bundle.structure):
        await _record(run, STRUCTURE, index, partial(_structure, run, index, item))
    for index, component in enumerate(bundle.components):
        await _record(run, COMPONENT, index, partial(_component, run, index, component))
    if bundle.layout is not None:
        await _record(run, LAYOUT, 0, partial(_layout, run, bundle.layout))
    for index, picture in enumerate(bundle.pictures):
        await _record(run, PICTURE, index, partial(_picture, run, index, picture))
    if bundle.translation is not None:
        run.reports += await checked_translation(
            session, user, subject, bundle.translation, origin=tools.origin, now=now
        )
    for index, withdrawal in enumerate(bundle.withdrawals):
        await _record(run, WITHDRAWAL, index, partial(_withdrawal, run, index, withdrawal))
    for index, section in enumerate(bundle.sections):
        await _record(run, SECTION, index, partial(_section, run, index, section))
    count = sum(report.outcome == REFUSED for report in run.reports)
    total = len(run.reports)
    return PageProposalResult(
        subject=PageSubject(kind=run.subject.kind, slug=run.subject.slug),
        page_url=f"{tools.site}{subject_path(run.subject)}",
        accepted=total - count,
        refused=count,
        parts=run.reports,
        message=SUMMARY.format(accepted=total - count, total=total, refused=count),
    )


async def _record(run: _Run, part: str, index: int, work: Callable[[], Awaitable[PartReport]]) -> None:
    report = await checked_part(run.session, part, index, work)
    if part == FACT and report.outcome == REFUSED:
        run.facts.refuse(index)
    run.reports.append(report)


async def _checked(run: _Run, part: str, index: int, item: object) -> Any:
    return await part_checked(run.checks, part, index, item)


async def _fact(run: _Run, index: int, proposal: FactProposal) -> PartReport:
    await run.tools.spend(FACT_PROPOSALS)
    await _checked(run, FACT, index, proposal)
    reply = await propose_fact(
        run.session, proposal, run.user, run.tools.origin, adapters=run.tools.gates, now=run.now
    )
    if reply.outcome == FACT_REFUSED:
        return refused(FACT, index, status=reply.status, ident=reply.claim_id, message=reply.message)
    run.facts.keep(index, reply.claim_id, proposal)
    return accepted(FACT, index, status=reply.status, ident=reply.claim_id, message=reply.message)


async def _structure(run: _Run, index: int, proposal: StructureProposal) -> PartReport:
    await run.tools.spend(STRUCTURE_PROPOSALS)
    await _checked(run, STRUCTURE, index, proposal)
    context = (run.tools.origin, run.tools.fetcher, run.tools.site)
    result = await propose_structure(run.session, run.user, proposal, context=context, now=run.now)
    made = refused if result.outcome == STRUCTURE_REFUSED else accepted
    return made(STRUCTURE, index, status=result.status, ident=result.proposal_id, message=result.message)


async def _component(run: _Run, index: int, component: PageComponent) -> PartReport:
    await run.tools.spend(COMPONENT_PROPOSALS)
    checked: CheckedProposal = await _checked(run, COMPONENT, index, component)
    if checked.refused is not None:
        return component_report(index, checked.refused)
    result = await stored_proposal(run.session, run.user, checked, now=run.now)
    run.checks.made.add(checked.draft.label)
    return component_report(index, result)


async def _layout(run: _Run, part: PageLayoutPart) -> PartReport:
    await run.tools.spend(LAYOUT_PROPOSALS)
    await _checked(run, LAYOUT, 0, part)
    draft = LayoutProposalDraft(
        subject=LayoutSubject(kind=run.subject.kind, slug=run.subject.slug),
        base_version=part.base_version,
        entries=list(part.entries),
        note=part.note,
    )
    result = await propose_layout(
        run.session, run.user, draft, origin=run.tools.origin, site=run.tools.site, now=run.now
    )
    return accepted(LAYOUT, 0, status=result.status, ident=result.proposal_id, message=result.message)


async def _section(run: _Run, index: int, part: SectionPart) -> PartReport:
    await run.tools.spend(STRUCTURE_PROPOSALS)
    await _checked(run, SECTION, index, part)
    context = SectionContext(origin=run.tools.origin, judges=run.tools.judges, site=run.tools.site)
    result = await propose_section(run.session, run.user, run.subject, part, context=context, now=run.now)
    made = refused if result.outcome == SECTION_REFUSED else accepted
    return made(SECTION, index, status=result.status, ident=result.proposal_id, message=result.message)


async def _withdrawal(run: _Run, index: int, withdrawal: PageWithdrawal) -> PartReport:
    await run.tools.spend(COMPONENT_PROPOSALS)
    await _checked(run, WITHDRAWAL, index, withdrawal)
    found = await withdrawable_piece(run.session, run.user, withdrawal.label, run.subject, lock=True)
    if found.waits:
        asked = await ask_withdrawal(
            run.session, run.user, found.piece, reason=withdrawal.reason, origin=run.tools.origin, now=run.now
        )
        return PartReport(part=WITHDRAWAL, index=index, outcome=ACCEPTED, status=ASKED_STATUS, message=asked)
    retired = await withdraw_registered(
        run.session, run.user, withdrawal.label, reason=withdrawal.reason, now=run.now
    )
    message = WITHDRAWN.format(label=retired.label)
    return accepted(WITHDRAWAL, index, status=WITHDRAWN_STATUS, ident=retired.piece_id, message=message)


async def _picture(run: _Run, index: int, picture: PagePicture) -> PartReport:
    await _checked(run, PICTURE, index, picture)
    if picture.contribution_id is not None:
        return await given_picture_report(run.session, run.user, run.subject, index, picture.contribution_id)
    claim_ids = picture_claims(picture, run.facts)
    slot = UploadSlot(craft_slug=run.subject.slug, stage_id=picture.stage_id, claim_ids=claim_ids)
    started = await run.tools.start_picture(slot, picture.declaration)
    return PartReport(
        part=PICTURE, index=index, outcome=ACCEPTED, status=OPEN, message=started.next_step, upload=started
    )
