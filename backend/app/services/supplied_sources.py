from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import token_matches_user
from app.core.errors import InvalidInput
from app.core.roles import Capability, can
from app.core.security import TOKEN_VERSION_CLAIM
from app.models import SuppliedSource, User
from app.research.evidence import EvidenceItem
from app.research.supplied_sources import (
    AWAITING_FILE,
    READY,
    SUPPLIED_TEXT_MAX_CHARS,
    Confirmation,
    SupplySource,
    cite_url,
    supplied_grade,
    supplied_text,
)

from .oauth_tokens import new_secret, stored_secret
from .supplied_sources_identity import IdentityLookup
from .supplied_sources_pdf import FILE_TYPES, file_text

__all__ = [
    "SLOT_PREFIX",
    "SUPPLIED_HELD_MAX",
    "UPLOAD_LIFETIME",
    "Supplied",
    "SuppliedGone",
    "UnknownSlot",
    "fill_supplied_slot",
    "own_supplied",
    "supply_source",
    "upload_types",
]

SLOT_PREFIX = "kvss_"
UPLOAD_LIFETIME = timedelta(minutes=30)
SUPPLIED_HELD_MAX = 300
FUTURE = "The source was read on {day}, which has not come yet; give the day you read it."
TOO_MANY = "This account holds {held} supplied sources, the most one account may hold."
USED = "This upload slot has been used; supply_source gives a new one."
EXPIRED = "This upload slot has expired; supply_source gives a new one."
ACCOUNT_CHANGED = "The account behind this upload slot has changed; supply_source gives a new one."
UNKNOWN = "No supplied source of yours has the id {ident}."
EMPTY = "The file holds no text to read; supply the passages as text instead."


class UnknownSlot(Exception):
    pass


class SuppliedGone(Exception):
    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


@dataclass(frozen=True)
class Supplied:
    row: SuppliedSource
    slot_token: str | None


async def supply_source(
    session: AsyncSession, user: User, draft: SupplySource, *, lookup: IdentityLookup, now: datetime
) -> Supplied:
    if draft.access.accessed_on > now.date():
        raise InvalidInput(FUTURE.format(day=draft.access.accessed_on.isoformat()))
    held = await session.scalar(
        select(func.count()).select_from(SuppliedSource).where(SuppliedSource.userId == user.id)
    )
    if (held or 0) >= SUPPLIED_HELD_MAX:
        raise InvalidInput(TOO_MANY.format(held=held))
    confirmed = await lookup(draft.identity)
    slot = new_secret(SLOT_PREFIX) if draft.upload is not None else None
    row = _row(user, draft, confirmed, slot, now)
    session.add(row)
    await session.flush()
    return Supplied(row=row, slot_token=slot)


async def fill_supplied_slot(
    session: AsyncSession, token: str, data: bytes, *, now: datetime
) -> SuppliedSource:
    digest = stored_secret(token, SLOT_PREFIX)
    if digest is None:
        raise UnknownSlot(token)
    row = await session.scalar(
        select(SuppliedSource)
        .where(SuppliedSource.slotHash == digest)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if row is None or row.upload is None:
        raise UnknownSlot(token)
    await _require_live(session, row, now)
    text = (await file_text(data, row.upload))[:SUPPLIED_TEXT_MAX_CHARS]
    if not text.strip():
        raise InvalidInput(EMPTY)
    _ready(row, text, now)
    row.fileSha256 = hashlib.sha256(data).hexdigest()
    row.slotHash = None
    row.slotExpiresAt = None
    await session.flush()
    return row


async def own_supplied(session: AsyncSession, user: User, supplied_id: uuid.UUID) -> SuppliedSource:
    row = await session.get(SuppliedSource, supplied_id)
    if row is None or (row.userId != user.id and not can(user, Capability.REVIEW_CONTRIBUTIONS)):
        raise InvalidInput(UNKNOWN.format(ident=supplied_id))
    return row


def upload_types() -> list[str]:
    return list(FILE_TYPES.values())


def _row(
    user: User, draft: SupplySource, confirmed: EvidenceItem | None, slot: str | None, now: datetime
) -> SuppliedSource:
    grade, reason = supplied_grade(draft.identity, confirmed)
    text = draft.text if draft.text is not None else supplied_text(draft.passages) if draft.passages else None
    row = SuppliedSource(
        id=uuid.uuid4(),
        userId=user.id,
        userTokenVersion=int(user.tokenVersion or 0),
        state=AWAITING_FILE,
        citeUrl=cite_url(draft.identity, confirmed.doi if confirmed else None),
        title=confirmed.title if confirmed is not None else draft.identity.title,
        doi=draft.identity.doi or (confirmed.doi.lower() if confirmed and confirmed.doi else None),
        isbn=draft.identity.isbn,
        identity=draft.identity.model_dump(mode="json", by_alias=True),
        confirmation=None
        if confirmed is None
        else _confirmation(confirmed).model_dump(mode="json", by_alias=True),
        accessKind=draft.access.how,
        accessedOn=draft.access.accessed_on,
        accessNote=draft.access.note,
        licence=draft.licence,
        grade=grade,
        gradeReason=reason,
        passages=[passage.model_dump(mode="json", by_alias=True) for passage in draft.passages],
        upload=draft.upload,
        slotHash=None if slot is None else stored_secret(slot, SLOT_PREFIX),
        slotExpiresAt=None if slot is None else now + UPLOAD_LIFETIME,
        createdAt=now,
        updatedAt=now,
    )
    if text is not None:
        _ready(row, text, now)
    return row


def _ready(row: SuppliedSource, text: str, now: datetime) -> None:
    row.text = text
    row.textSha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
    row.characters = len(text)
    row.state = READY
    row.updatedAt = now


def _confirmation(item: EvidenceItem) -> Confirmation:
    return Confirmation(
        index=item.adapter,
        work_id=item.id,
        title=item.title,
        doi=item.doi,
        year=int(item.published[:4]) if item.published else None,
        authors=list(item.authors),
    )


async def _require_live(session: AsyncSession, row: SuppliedSource, now: datetime) -> None:
    if row.state == READY:
        raise SuppliedGone(USED)
    if row.slotExpiresAt is None or row.slotExpiresAt <= now:
        raise SuppliedGone(EXPIRED)
    user = await session.get(User, row.userId)
    claims = {TOKEN_VERSION_CLAIM: row.userTokenVersion, "iat": row.createdAt.timestamp()}
    if user is None or not token_matches_user(claims, user) or not can(user, Capability.PROPOSE_KNOWLEDGE):
        raise SuppliedGone(ACCOUNT_CHANGED)
