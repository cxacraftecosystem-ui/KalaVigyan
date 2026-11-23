from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput
from app.core.roles import PROFESSOR, ROLE_LABELS, has_rank
from app.models import StructureProposal as ProposalRow, User
from app.research.candidate_gates import Candidate
from app.research.evidence import canonical_url
from app.research.fetcher import Fetcher
from app.research.structure_proposals import (
    APPROVED_STATUS,
    CONFLICT,
    GROUP_NAME,
    PENDING_STATUS,
    REFUSED,
    REFUSED_STATUS,
    STORED,
    WRITTEN,
    GroupNameItem,
    StructureCheck,
    StructureProposal,
    StructureProposalResult,
    StructureSubject,
)
from app.research.structure_proposals_values import stated_check

from .candidate_gates import first_gates
from .candidate_sources import ReadSource, read_source
from .fact_proposals import role_now
from .fact_task_checks import check_question_task
from .live_source_store import keep_document
from .proposal_writes import mark_contributed
from .structure_proposals_dossier import dossier_problem
from .structure_proposals_owner import StructureOwner, owner_page, subject_owner
from .structure_proposals_page import OwnerPage, target_problem
from .structure_proposals_review import approve_structure
from .structure_proposals_write import held_claims
from .supplied_sources_gate import keep_supplied
from .task_reservations import complete_task, give_back_task

__all__ = ["CANDIDATE_REF", "curated_subject", "propose_structure"]

CANDIDATE_REF = "structure"
NOT_CURATED = (
    "{slug} has no curated page yet, so its structure arrives with its first dossier. Propose facts for it "
    "with propose_facts instead."
)
MESSAGES = {
    STORED: (
        "Stored for review: a Professor or Admin approves or rejects it, and approval writes it into the page and "
        "its dossier with its fact. Who proposed it is kept privately."
    ),
    WRITTEN: "Written at once into the page and its dossier, because your account reviews structure.",
    REFUSED: "Not added: the {check} check refused it. {reason}",
}
NAME_MESSAGES = {
    STORED: (
        "Stored for review: a Professor or Admin approves or rejects it, and approval adds the name to the "
        "craft's list of names kept out of AI pictures, which readers never see. Who proposed it is kept "
        "privately."
    ),
    WRITTEN: (
        "Added at once to the craft's list of names kept out of AI pictures, because your account reviews "
        "structure. Readers never see the list."
    ),
}


@dataclass(frozen=True)
class _Checked:
    checks: tuple[StructureCheck, ...]
    read: tuple[ReadSource, ...]

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks)


async def curated_subject(
    session: AsyncSession, subject: StructureSubject
) -> tuple[StructureOwner, OwnerPage]:
    owner = await subject_owner(session, subject)
    page = await owner_page(session, owner, lock=False)
    if page is None:
        raise InvalidInput(NOT_CURATED.format(slug=owner.slug))
    return owner, page


async def propose_structure(
    session: AsyncSession,
    user: User,
    proposal: StructureProposal,
    *,
    context: tuple[str, Fetcher, str],
    now: datetime,
) -> StructureProposalResult:
    origin, fetcher, site = context
    role = await role_now(session, user.id)
    owner = await _fitting_owner(session, proposal)
    await check_question_task(session, proposal.task_key, tuple(filter(None, (proposal.field,))))
    checked = await _checked(session, fetcher, proposal, user.id)
    kept = await _kept(session, checked.read, user.id) if checked.passed else {}
    row = _row(proposal, (owner, user.id, origin), checked, kept, now)
    session.add(row)
    await session.flush()
    if proposal.task_key is not None:
        settle = complete_task if checked.passed else give_back_task
        await settle(session, user.id, proposal.task_key, now=now)
    if checked.passed and has_rank(role, PROFESSOR):
        note = f"approved at once: proposed by a {ROLE_LABELS.get(role, role)} account"
        await approve_structure(session, row, user, note=note, now=now)
    return _result(row, owner, checked.checks, site)


async def _fitting_owner(session: AsyncSession, proposal: StructureProposal) -> StructureOwner:
    if proposal.item.kind == GROUP_NAME:
        owner = await subject_owner(session, proposal.subject)
        problem = dossier_problem(proposal)
    else:
        owner, page = await curated_subject(session, proposal.subject)
        held = await held_claims(session, owner)
        problem = dossier_problem(proposal) or target_problem(page, proposal.item, held=held)
    if problem is not None:
        raise InvalidInput(problem)
    return owner


async def _checked(
    session: AsyncSession, fetcher: Fetcher, proposal: StructureProposal, proposer_id: uuid.UUID
) -> _Checked:
    if proposal.item.kind == CONFLICT:
        return _Checked(checks=(), read=())
    quotes = [quote.text for source in proposal.sources for quote in source.quotes]
    stated = stated_check(proposal.item, quotes)
    if not stated.passed:
        return _Checked(checks=(stated,), read=())
    read = tuple([await read_source(session, fetcher, s, proposer_id=proposer_id) for s in proposal.sources])
    candidate = Candidate(ref=CANDIDATE_REF, statement=_gated_statement(proposal), field=proposal.field)
    outcomes = first_gates(candidate, [source.cited for source in read])
    gates = [
        StructureCheck(check=item.gate, passed=item.passed, reasons=list(item.reasons)) for item in outcomes
    ]
    return _Checked(checks=(stated, *gates), read=read)


def _gated_statement(proposal: StructureProposal) -> str:
    if isinstance(proposal.item, GroupNameItem):
        return proposal.item.name
    return proposal.statement or ""


async def _kept(
    session: AsyncSession, read: Sequence[ReadSource], proposer_id: uuid.UUID
) -> dict[str, uuid.UUID]:
    kept: dict[str, uuid.UUID] = {}
    for source in read:
        if source.document is None:
            continue
        source_id = await (keep_supplied if source.supplied else keep_document)(session, source.document)
        if source.stored is None:
            await mark_contributed(session, source_id, proposer_id)
        kept[canonical_url(source.proposed.url)] = source_id
    await session.flush()
    return kept


def _row(
    proposal: StructureProposal,
    owners: tuple[StructureOwner, uuid.UUID, str],
    checked: _Checked,
    kept: Mapping[str, uuid.UUID],
    now: datetime,
) -> ProposalRow:
    owner, proposer_id, origin = owners
    return ProposalRow(
        id=uuid.uuid4(),
        createdAt=now,
        proposerId=proposer_id,
        **owner.row_owner(),
        kind=proposal.item.kind,
        item=proposal.item.model_dump(mode="json"),
        field=proposal.field,
        statement=proposal.statement,
        sources=[_stored_source(source, kept) for source in proposal.sources],
        checks=[check.model_dump(mode="json") for check in checked.checks],
        taskKey=proposal.task_key,
        note=proposal.note,
        origin=origin,
        status=PENDING_STATUS if checked.passed else REFUSED_STATUS,
        reviewedById=None,
        reviewedAt=None,
        reviewNote=None,
        claimId=None,
    )


def _stored_source(source: Any, kept: Mapping[str, uuid.UUID]) -> dict[str, Any]:
    source_id = kept.get(canonical_url(source.url))
    return {
        "url": source.url,
        "title": source.title,
        "licence": source.licence,
        "language": source.language,
        "quotes": [{"text": quote.text, "locator": quote.locator} for quote in source.quotes],
        "sourceId": None if source_id is None else str(source_id),
    }


def _result(
    row: ProposalRow, owner: StructureOwner, checks: Sequence[StructureCheck], site: str
) -> StructureProposalResult:
    outcome = (
        REFUSED if row.status == REFUSED_STATUS else WRITTEN if row.status == APPROVED_STATUS else STORED
    )
    refused = next((check for check in checks if not check.passed), None)
    message = (NAME_MESSAGES if row.kind == GROUP_NAME else MESSAGES).get(outcome, MESSAGES[outcome])
    if refused is not None:
        message = message.format(check=refused.check, reason=refused.reasons[0])
    return StructureProposalResult(
        outcome=outcome,
        proposal_id=row.id,
        status=row.status,
        kind=row.kind,
        subject=owner.subject,
        claim_id=row.claimId,
        checks=list(checks),
        page_url=owner.page_url(site),
        message=message,
    )
