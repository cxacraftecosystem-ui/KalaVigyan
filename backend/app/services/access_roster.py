import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import ColumnElement, exists, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import AccessRoster, User

from .share_owners import withdraw_shares
from .shared_files import FileDeleter

logger = logging.getLogger(__name__)

MAX_EMAIL_LENGTH = 254

ACTIVE = "ACTIVE"
PENDING = "PENDING"
REJECTED = "REJECTED"
SUSPENDED = "SUSPENDED"
NOT_RECORDED = "NOT_RECORDED"

BARRED = (REJECTED, SUSPENDED)
STATUSES = frozenset({ACTIVE, PENDING, REJECTED, SUSPENDED})


def normalise_email(email: Any) -> str:
    return str(email or "").strip().lower()


def status_of(row: Any) -> str:
    if row is None:
        return ""
    return str(getattr(row, "status", "") or "")


def admits(row: Any) -> bool:
    return status_of(row) == ACTIVE


def role_of(row: Any) -> str | None:
    if row is None:
        return None
    return getattr(row, "admitRole", None) or None


def pending_cap() -> int:
    return max(1, int(get_settings().access_pending_max))


async def access_row(session: AsyncSession, email: Any) -> AccessRoster | None:
    address = normalise_email(email)
    if not address or len(address) > MAX_EMAIL_LENGTH:
        return None
    return (
        await session.execute(select(AccessRoster).where(AccessRoster.email == address))
    ).scalar_one_or_none()


async def pending_count(session: AsyncSession) -> int:
    return int(
        (
            await session.execute(
                select(func.count()).select_from(AccessRoster).where(AccessRoster.status == PENDING)
            )
        ).scalar_one()
    )


async def admit(
    session: AsyncSession,
    email: Any,
    *,
    admit_role: str | None = None,
    actor_id: Any = None,
    full_name: str | None = None,
    note: str | None = None,
    decided: bool = True,
) -> AccessRoster:
    address = normalise_email(email)
    if not address:
        raise ValueError("an access roster row needs an email address")
    now = datetime.now(UTC)
    row = await access_row(session, address)
    if row is None:
        row = AccessRoster(email=address, addedById=actor_id, status=ACTIVE, joinedAt=now)
        session.add(row)
    else:
        row.status = ACTIVE
        row.joinedAt = row.joinedAt or now
    if admit_role:
        row.admitRole = admit_role
    if full_name is not None:
        row.fullName = full_name
    if note is not None:
        row.notes = note
    if decided:
        row.decidedAt = now
        row.decidedById = actor_id
    await session.flush()
    return row


async def record_refused_attempt(session: AsyncSession, email: Any, row: AccessRoster | None) -> str:
    address = normalise_email(email)
    now = datetime.now(UTC)
    if row is not None:
        await session.execute(
            update(AccessRoster)
            .where(AccessRoster.id == row.id)
            .values(attemptCount=AccessRoster.attemptCount + 1, lastAttemptAt=now)
        )
        await session.commit()
        return status_of(row)
    if not address or len(address) > MAX_EMAIL_LENGTH:
        return NOT_RECORDED
    waiting = await pending_count(session)
    if waiting >= pending_cap():
        logger.error(
            "the pending access queue holds %s requests, at or past the %s cap; a new request was not recorded",
            waiting,
            pending_cap(),
        )
        return NOT_RECORDED
    statement = (
        insert(AccessRoster)
        .values(email=address, status=PENDING, requestedAt=now, attemptCount=1, lastAttemptAt=now)
        .on_conflict_do_update(
            index_elements=[AccessRoster.email],
            set_={"attemptCount": AccessRoster.attemptCount + 1, "lastAttemptAt": now},
        )
        .returning(AccessRoster.status)
    )
    outcome = (await session.execute(statement)).scalar_one()
    await session.commit()
    return str(outcome)


async def mark_access_seen(session: AsyncSession, row: AccessRoster | None) -> None:
    if row is None or row.firstSeenAt is not None:
        return
    await session.execute(
        update(AccessRoster)
        .where(AccessRoster.id == row.id, AccessRoster.firstSeenAt.is_(None))
        .values(firstSeenAt=datetime.now(UTC))
    )


async def end_sessions_for_email(session: AsyncSession, email: Any) -> int:
    address = normalise_email(email)
    result = await session.execute(
        update(User)
        .where(func.lower(User.email) == address)
        .values(tokenVersion=User.tokenVersion + 1, sessionsValidFrom=datetime.now(UTC))
    )
    return int(result.rowcount or 0)


async def bar_account(
    session: AsyncSession, email: Any, *, actor: Any, cause: str, objects: FileDeleter | None
) -> None:
    await end_sessions_for_email(session, email)
    owners = await session.execute(select(User.id).where(func.lower(User.email) == normalise_email(email)))
    for owner_id in owners.scalars().all():
        await withdraw_shares(session, owner_id, actor=actor, cause=cause, objects=objects)


def account_in_good_standing(user_id: ColumnElement[Any]) -> ColumnElement[bool]:
    barred = exists().where(AccessRoster.email == func.lower(User.email), AccessRoster.status.in_(BARRED))
    return exists().where(User.id == user_id, User.deletedAt.is_(None), ~barred)


def _iso(value: Any) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else None


def access_payload(row: AccessRoster, people: dict[Any, User] | None = None) -> dict[str, Any]:
    people = people or {}
    added_by = people.get(row.addedById)
    decided_by = people.get(row.decidedById)
    return {
        "id": str(row.id),
        "email": row.email,
        "fullName": row.fullName,
        "affiliation": row.affiliation,
        "status": status_of(row),
        "admitRole": role_of(row),
        "joinedAt": _iso(row.joinedAt),
        "requestedAt": _iso(row.requestedAt),
        "attemptCount": row.attemptCount,
        "lastAttemptAt": _iso(row.lastAttemptAt),
        "decidedAt": _iso(row.decidedAt),
        "decidedById": str(row.decidedById) if row.decidedById else None,
        "firstSeenAt": _iso(row.firstSeenAt),
        "notes": row.notes,
        "createdAt": _iso(row.createdAt),
        "updatedAt": _iso(row.updatedAt),
        "addedById": str(row.addedById) if row.addedById else None,
        "addedByName": (added_by.name or added_by.email) if added_by else None,
        "decidedByName": (decided_by.name or decided_by.email) if decided_by else None,
    }


async def people_for(session: AsyncSession, rows: list[AccessRoster]) -> dict[Any, User]:
    ids = {row.addedById for row in rows if row.addedById} | {
        row.decidedById for row in rows if row.decidedById
    }
    if not ids:
        return {}
    users = (await session.execute(select(User).where(User.id.in_(ids)))).scalars().all()
    return {user.id: user for user in users}
