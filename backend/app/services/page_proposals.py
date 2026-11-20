from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from functools import partial

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput
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
    STRUCTURE,
    PageBundle,
    PageComponent,
    PageLayoutPart,
    PagePicture,
    PageProposalResult,
    PageSubject,
    PartReport,
)
from app.research.review_switch import REFUSED as FACT_REFUSED
from app.research.structure_proposals import REFUSED as STRUCTURE_REFUSED, StructureProposal
from app.research.upload_links import OPEN, SlotDeclaration, UploadSlot, UploadStart

from .component_proposals import propose_component
from .fact_proposals import ProposalAdapters, propose_fact
from .open_work_subjects import WorkSubject, subject_by_key
from .page_layout_proposals import propose_layout
from .page_layouts import subject_path
from .page_preview_pictures import given_picture_report
from .page_proposals_parts import (
    BundleFacts,
    accepted,
    checked_part,
    fact_subject_problem,
    keyed_problem,
    known_texts,
    picture_claims,
    refuse_on,
    refused,
    resolved_component,
    structure_subject_problem,
)
from .structure_proposals import propose_structure

__all__ = ["PageTools", "PictureStarter", "propose_page"]

PictureStarter = Callable[[UploadSlot, SlotDeclaration | None], Awaitable[UploadStart]]
SUMMARY = (
    "{accepted} of {total} parts of the bundle were accepted and {refused} refused, each with its reason."
)


@dataclass(frozen=True)
class PageTools:
    gates: ProposalAdapters
    fetcher: Fetcher
    start_picture: PictureStarter
    spend: Callable[[str], None]
    origin: str
    site: str


@dataclass
class _Run:
    session: AsyncSession
    user: User
    bundle: PageBundle
    subject: WorkSubject
    tools: PageTools
    now: datetime
    facts: BundleFacts = field(default_factory=BundleFacts)
    reports: list[PartReport] = field(default_factory=list)


async def propose_page(
    session: AsyncSession, user: User, bundle: PageBundle, *, tools: PageTools, now: datetime
) -> PageProposalResult:
    subject = await subject_by_key(session, bundle.subject.kind, bundle.subject.slug)
    run = _Run(session, user, bundle, subject, tools, now)
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


async def _fact(run: _Run, index: int, proposal: FactProposal) -> PartReport:
    refuse_on(fact_subject_problem(run.bundle, run.subject, index, proposal))
    run.tools.spend(FACT_PROPOSALS)
    reply = await propose_fact(
        run.session, proposal, run.user, run.tools.origin, adapters=run.tools.gates, now=run.now
    )
    if reply.outcome == FACT_REFUSED:
        return refused(FACT, index, status=reply.status, ident=reply.claim_id, message=reply.message)
    run.facts.keep(index, reply.claim_id, proposal)
    return accepted(FACT, index, status=reply.status, ident=reply.claim_id, message=reply.message)


async def _structure(run: _Run, index: int, proposal: StructureProposal) -> PartReport:
    refuse_on(structure_subject_problem(run.bundle, run.subject, index, proposal))
    run.tools.spend(STRUCTURE_PROPOSALS)
    context = (run.tools.origin, run.tools.fetcher, run.tools.site)
    result = await propose_structure(run.session, run.user, proposal, context=context, now=run.now)
    made = refused if result.outcome == STRUCTURE_REFUSED else accepted
    return made(STRUCTURE, index, status=result.status, ident=result.proposal_id, message=result.message)


async def _component(run: _Run, index: int, component: PageComponent) -> PartReport:
    draft = resolved_component(component, run.facts)
    refuse_on(keyed_problem(run.bundle, run.subject, index, draft))
    run.tools.spend(COMPONENT_PROPOSALS)
    result = await propose_component(
        run.session, run.user, draft, now=run.now, known=known_texts(run.facts, draft)
    )
    made = refused if result.outcome == REFUSED else accepted
    return made(COMPONENT, index, status=result.status, ident=result.proposal_id, message=result.message)


async def _layout(run: _Run, part: PageLayoutPart) -> PartReport:
    run.tools.spend(LAYOUT_PROPOSALS)
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


async def _picture(run: _Run, index: int, picture: PagePicture) -> PartReport:
    if run.subject.kind == "category":
        raise InvalidInput("A picture is given to a craft's page; a category's bundle carries none.")
    if picture.contribution_id is not None:
        return await given_picture_report(run.session, run.user, run.subject, index, picture.contribution_id)
    claim_ids = picture_claims(picture, run.facts)
    slot = UploadSlot(craft_slug=run.subject.slug, stage_id=picture.stage_id, claim_ids=claim_ids)
    started = await run.tools.start_picture(slot, picture.declaration)
    return PartReport(
        part=PICTURE, index=index, outcome=ACCEPTED, status=OPEN, message=started.next_step, upload=started
    )
