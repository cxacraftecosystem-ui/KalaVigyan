from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput
from app.models import User
from app.research.knowledge_writes import FactProposal
from app.research.page_proposals import (
    COMPONENT,
    FACT,
    LAYOUT,
    PICTURE,
    SECTION,
    STRUCTURE,
    WITHDRAWAL,
    PageBundle,
    PageComponent,
    PageLayoutPart,
    PagePicture,
    PageWithdrawal,
)
from app.research.section_proposals import SectionPart
from app.research.structure_proposals import StructureProposal
from app.research.upload_links import UploadSlot

from .borrowed_placements import borrowed_problem, linked_labels
from .component_proposals import CheckedProposal, checked_proposal
from .component_withdrawals import Withdrawable, withdrawable_piece, withdrawal_problem
from .fact_task_checks import check_question_task
from .open_work_subjects import CATEGORY, WorkSubject
from .page_layout_checks import layout_problem
from .page_preview_pictures import NO_CATEGORY, checked_given
from .page_proposals_parts import (
    BundleFacts,
    fact_subject_problem,
    keyed_problem,
    known_texts,
    picture_claims,
    refuse_on,
    resolved_component,
    structure_subject_problem,
)
from .section_proposals import CheckedSection, checked_section
from .structure_proposals import fitting_structure
from .upload_links import checked_slot

__all__ = ["PART_CHECKS", "PartRun", "part_checked"]

PartCheck = Callable[["PartRun", int, Any], Awaitable[Any]]


@dataclass
class PartRun:
    session: AsyncSession
    user: User
    bundle: PageBundle
    subject: WorkSubject
    facts: BundleFacts
    now: datetime
    made: set[str] = field(default_factory=set)


async def part_checked(run: PartRun, part: str, index: int, item: Any) -> Any:
    return await PART_CHECKS[part](run, index, item)


async def _fact(run: PartRun, index: int, fact: FactProposal) -> None:
    refuse_on(fact_subject_problem(run.bundle, run.subject, index, fact))
    await check_question_task(run.session, fact.task_key, (fact.field, *fact.fields))


async def _structure(run: PartRun, index: int, item: StructureProposal) -> None:
    refuse_on(structure_subject_problem(run.bundle, run.subject, index, item))
    await fitting_structure(run.session, item)


async def _component(run: PartRun, index: int, component: PageComponent) -> CheckedProposal:
    draft = resolved_component(component, run.facts)
    refuse_on(keyed_problem(run.bundle, run.subject, index, draft))
    refuse_on(await borrowed_problem(run.session, run.subject, linked_labels([component])))
    return await checked_proposal(run.session, run.user, draft, known=known_texts(run.facts, draft))


async def _layout(run: PartRun, index: int, part: PageLayoutPart) -> None:
    work = (run.bundle.components, part)
    refuse_on(await layout_problem(run.session, run.subject, work, run.made))


async def _picture(run: PartRun, index: int, picture: PagePicture) -> None:
    if run.subject.kind == CATEGORY:
        raise InvalidInput(NO_CATEGORY)
    if picture.contribution_id is not None:
        await checked_given(run.session, run.user, run.subject, [picture.contribution_id])
        return
    picture_claims(picture, run.facts)
    stored = [ref for ref in picture.claim_ids if isinstance(ref, uuid.UUID)]
    slot = UploadSlot(craft_slug=run.subject.slug, stage_id=picture.stage_id, claim_ids=stored)
    await checked_slot(run.session, run.user, slot, picture.declaration, now=run.now)


async def _withdrawal(run: PartRun, index: int, withdrawal: PageWithdrawal) -> Withdrawable:
    found = await withdrawable_piece(run.session, run.user, withdrawal.label, run.subject)
    refuse_on(await withdrawal_problem(run.session, found, withdrawal.reason, now=run.now))
    return found


async def _section(run: PartRun, index: int, part: SectionPart) -> CheckedSection:
    return await checked_section(run.session, run.subject, part)


PART_CHECKS: Mapping[str, PartCheck] = MappingProxyType(
    {
        FACT: _fact,
        STRUCTURE: _structure,
        COMPONENT: _component,
        LAYOUT: _layout,
        PICTURE: _picture,
        WITHDRAWAL: _withdrawal,
        SECTION: _section,
    }
)
