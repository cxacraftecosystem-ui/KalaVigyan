from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput, Refused
from app.core.roles import PROFESSOR, ROLE_LABELS, has_rank
from app.models import Craft, CraftCategory, SectionProposal, User
from app.research.open_work import task_key
from app.research.section_proposals import (
    APPROVED_STATUS,
    PENDING_STATUS,
    REFUSED,
    REFUSED_STATUS,
    REJECTED_STATUS,
    SENTENCES,
    STORED,
    WRITTEN,
    SectionCheck,
    SectionOutcome,
    SectionPart,
    first_refusal,
)
from app.research.structured import StructuredModel

from . import audit
from .fact_proposals import role_now
from .monograph_document import has_authored_content
from .monograph_generated_sections import ReviewedBy, SectionOwner, publish_reviewed_section
from .open_work_subjects import CATEGORY, WorkSubject, craft_subject, subject_by_key
from .section_gates import ShownFacts, faithful_check, field_facts, section_checks, shown_facts, stale_problem
from .task_reservations import complete_task

__all__ = [
    "MESSAGES",
    "CheckedSection",
    "SectionContext",
    "approve_section",
    "checked_section",
    "propose_section",
    "refusal_message",
    "reject_section",
    "row_part",
    "row_subject",
    "section_owner",
]

SECTION_TASK = "SECTION"
TARGET = "SectionProposal"
STALE_SECTION = "stale_section"
AUTHORED = "{slug}'s page is authored and drawn from its own text, so a section cannot be proposed for it."
NO_PAGE = "The page of this proposal is no longer held."
MOVED_ON = "The page has moved on since this was proposed: {problem}."
MESSAGES = {
    STORED: (
        "Stored for review: a Professor or Admin reads it beside the field's published section, and approval "
        "puts it in that section's place, the replaced one kept in the record. Who proposed it is kept privately."
    ),
    WRITTEN: (
        "Written at once in place of the field's published section, the replaced one kept in the record, "
        "because your account reviews sections; the page shows it after its next refresh."
    ),
    REFUSED: "Not stored for review: the {check} check refused the whole section, as one unit. {reason}.",
}
SAID = " The {check} check says: {reason}."
APPROVED_AT_ONCE = "approved at once: proposed by a {role} account"


@dataclass(frozen=True)
class CheckedSection:
    facts: ShownFacts
    checks: tuple[SectionCheck, ...]


@dataclass(frozen=True)
class SectionContext:
    origin: str
    judges: Sequence[StructuredModel]
    site: str


async def propose_section(
    session: AsyncSession,
    user: User,
    subject: WorkSubject,
    part: SectionPart,
    *,
    context: SectionContext,
    now: datetime,
) -> SectionOutcome:
    checked = await checked_section(session, subject, part)
    facts, checks = checked.facts, list(checked.checks)
    if first_refusal(checks) is None:
        checks.append(await faithful_check(part, facts, context.judges))
    row = _row(user, subject, part, checks, context)
    row.createdAt = now
    session.add(row)
    await session.flush()
    role = await role_now(session, user.id)
    if row.status == PENDING_STATUS and has_rank(role, PROFESSOR):
        note = APPROVED_AT_ONCE.format(role=ROLE_LABELS.get(role, role))
        await approve_section(session, row, user, note=note, now=now)
    return _outcome(row, checks)


async def checked_section(session: AsyncSession, subject: WorkSubject, part: SectionPart) -> CheckedSection:
    if has_authored_content(subject.slug):
        raise InvalidInput(AUTHORED.format(slug=subject.slug))
    facts = await field_facts(session, subject, part)
    return CheckedSection(facts=facts, checks=tuple(section_checks(part, facts)))


def refusal_message(checks: Sequence[SectionCheck]) -> str | None:
    refused = first_refusal(list(checks))
    if refused is None:
        return None
    return MESSAGES[REFUSED].format(check=refused.check, reason="; ".join(refused.reasons))


async def approve_section(
    session: AsyncSession, row: SectionProposal, reviewer: User, *, note: str | None, now: datetime
) -> uuid.UUID:
    subject = await row_subject(session, row)
    if subject is None:
        raise Refused(STALE_SECTION, NO_PAGE)
    part = row_part(row)
    problem = stale_problem(part, await shown_facts(session, subject, part))
    if problem is not None:
        raise Refused(STALE_SECTION, MOVED_ON.format(problem=problem))
    reviewed = ReviewedBy(writer_id=row.proposerId, reviewer_id=reviewer.id, at=now)
    row.sectionId = await publish_reviewed_section(
        session, section_owner(row), row.field, part.sentences, reviewed
    )
    await _decided(session, row, reviewer, (APPROVED_STATUS, note, now))
    if row.taskKey is not None and row.proposerId is not None:
        await complete_task(session, row.proposerId, row.taskKey, now=now)
    return row.sectionId


async def reject_section(
    session: AsyncSession, row: SectionProposal, reviewer: User, *, reason: str, now: datetime
) -> None:
    await _decided(session, row, reviewer, (REJECTED_STATUS, reason, now))


def row_part(row: SectionProposal) -> SectionPart:
    return SectionPart.model_validate({"field": row.field, "sentences": row.sentences, "note": row.note})


def section_owner(row: SectionProposal) -> SectionOwner:
    if row.categoryId is not None:
        return SectionOwner.category(row.categoryId)
    if row.craftId is None:
        raise Refused(STALE_SECTION, NO_PAGE)
    return SectionOwner.craft(row.craftId)


async def row_subject(session: AsyncSession, row: SectionProposal) -> WorkSubject | None:
    try:
        if row.categoryId is not None:
            slug = await session.scalar(select(CraftCategory.slug).where(CraftCategory.id == row.categoryId))
            return None if slug is None else await subject_by_key(session, CATEGORY, slug)
        slug = await session.scalar(select(Craft.slug).where(Craft.id == row.craftId))
        return None if slug is None else await craft_subject(session, slug)
    except InvalidInput:
        return None


def _row(
    user: User, subject: WorkSubject, part: SectionPart, checks: list[SectionCheck], context: SectionContext
) -> SectionProposal:
    category = subject.kind == CATEGORY
    return SectionProposal(
        id=uuid.uuid4(),
        proposerId=user.id,
        craftId=None if category else subject.id,
        categoryId=subject.id if category else None,
        field=part.field,
        sentences=[sentence.model_dump(mode="json", by_alias=True) for sentence in part.sentences],
        checks=[check.model_dump(mode="json") for check in checks],
        taskKey=task_key(SECTION_TASK, subject.task_subject(context.site), part.field),
        note=part.note,
        origin=context.origin,
        status=PENDING_STATUS if first_refusal(checks) is None else REFUSED_STATUS,
    )


def _outcome(row: SectionProposal, checks: list[SectionCheck]) -> SectionOutcome:
    message = refusal_message(checks)
    if message is not None:
        return SectionOutcome(
            outcome=REFUSED, proposal_id=row.id, status=row.status, checks=checks, message=message
        )
    outcome = WRITTEN if row.status == APPROVED_STATUS else STORED
    counted = next(check for check in checks if check.check == SENTENCES)
    message = MESSAGES[outcome] + SAID.format(check=counted.check, reason=counted.reasons[0])
    return SectionOutcome(
        outcome=outcome, proposal_id=row.id, status=row.status, checks=checks, message=message
    )


async def _decided(
    session: AsyncSession, row: SectionProposal, reviewer: User, decision: tuple[str, str | None, datetime]
) -> None:
    status, note, now = decision
    row.status, row.reviewedById, row.reviewedAt, row.reviewNote = status, reviewer.id, now, note
    await audit.record(
        session,
        action=f"review.section_{status.lower()}",
        actor=reviewer,
        target_type=TARGET,
        target_id=row.id,
        detail={
            "from": PENDING_STATUS,
            "to": status,
            "field": row.field,
            "section": None if row.sectionId is None else str(row.sectionId),
        },
    )
    await session.flush()
