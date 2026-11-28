from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput, Refused
from app.models import KnowledgePiece, User
from app.research.review_queue import COMPONENTS, REASON_MAX_CHARS
from app.research.review_switch import AGENT, CONTRIBUTION
from app.research.staged_reviews import BATCH_DAYS, REMOVE, STAGED_REASON_MIN_CHARS, StagedDecision

from .component_library_applies import applies_on
from .component_lifecycle import NOT_RETIRING, NOT_YOURS, live_piece, piece_owners
from .component_retirers import may_retire, stewards_piece
from .open_work_subjects import CATEGORY, WorkSubject
from .staged_reviews import request_problem, stage_request

__all__ = [
    "ASKED_STATUS",
    "Withdrawable",
    "ask_withdrawal",
    "reason_problem",
    "replacement_waits",
    "retirement_waits",
    "withdrawable_piece",
    "withdrawal_decision",
    "withdrawal_problem",
]

ASKED_STATUS = "STAGED"
OFF_THE_PAGE = (
    "{label} is not on {page}'s page, so this page's bundle cannot withdraw it: withdraw it in the bundle of "
    "a page that places it."
)
REASON_NEEDED = (
    "{label} was proposed by another account or curated, so a steward's withdrawal of it waits for an "
    "Admin, who reads its reason: give one of {least} to {most} characters."
)
ASKED = (
    "Asked: {label} stays on its pages until an Admin confirms its withdrawal on the Review page, because "
    "this account stewards its craft but did not propose it; unconfirmed, the request lapses after {days} "
    "days."
)
REQUEST_CLIENTS = MappingProxyType({AGENT: "propose_page over MCP", CONTRIBUTION: "the site's page proposal"})


@dataclass(frozen=True)
class Withdrawable:
    piece: KnowledgePiece
    waits: bool


async def retirement_waits(session: AsyncSession, user: User, piece: KnowledgePiece) -> bool:
    if await may_retire(session, user, piece):
        return False
    if await stewards_piece(session, user, piece):
        return True
    raise Refused(NOT_RETIRING, NOT_YOURS.format(label=piece.label))


async def replacement_waits(session: AsyncSession, user: User, label: str | None) -> bool:
    if label is None:
        return False
    return await retirement_waits(session, user, await live_piece(session, label))


async def withdrawable_piece(
    session: AsyncSession, user: User, label: str, subject: WorkSubject, *, lock: bool = False
) -> Withdrawable:
    piece = await live_piece(session, label, lock=lock)
    waits = await retirement_waits(session, user, piece)
    if not await _on_page(session, piece, subject):
        raise InvalidInput(OFF_THE_PAGE.format(label=label, page=subject.name))
    return Withdrawable(piece, waits)


def reason_problem(found: Withdrawable, reason: str | None) -> str | None:
    if not found.waits or _gives_a_reason(reason):
        return None
    return _reason_needed(found.piece)


async def ask_withdrawal(
    session: AsyncSession,
    user: User,
    piece: KnowledgePiece,
    *,
    reason: str | None,
    origin: str,
    now: datetime,
) -> str:
    if reason is None or not _gives_a_reason(reason):
        raise InvalidInput(_reason_needed(piece))
    decision = withdrawal_decision(piece, reason)
    await stage_request(session, decision, user, client_name=REQUEST_CLIENTS[origin], now=now)
    return ASKED.format(label=piece.label, days=BATCH_DAYS)


def withdrawal_decision(piece: KnowledgePiece, reason: str) -> StagedDecision:
    return StagedDecision(kind=COMPONENTS, id=piece.id, action=REMOVE, reason=reason)


async def withdrawal_problem(
    session: AsyncSession, found: Withdrawable, reason: str | None, *, now: datetime
) -> str | None:
    problem = reason_problem(found, reason)
    if problem is not None or not found.waits or reason is None:
        return problem
    return await request_problem(session, withdrawal_decision(found.piece, reason), now=now)


async def _on_page(session: AsyncSession, piece: KnowledgePiece, subject: WorkSubject) -> bool:
    if subject.kind == CATEGORY:
        categories = (await piece_owners(session, piece)).categories
        return subject.slug.casefold() in {slug.casefold() for slug in categories}
    return await applies_on(session, piece.id, subject.id)


def _gives_a_reason(reason: str | None) -> bool:
    return reason is not None and STAGED_REASON_MIN_CHARS <= len(reason) <= REASON_MAX_CHARS


def _reason_needed(piece: KnowledgePiece) -> str:
    return REASON_NEEDED.format(label=piece.label, least=STAGED_REASON_MIN_CHARS, most=REASON_MAX_CHARS)
