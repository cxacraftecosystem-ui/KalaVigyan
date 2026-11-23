import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.access_filters import roster_filter, roster_ordering
from app.api.auth_session import role_for_email
from app.core.db import get_session
from app.core.deps import refuse_unless_assignable, require
from app.core.roles import (
    Capability,
    assignable_roles,
    is_master_admin,
    may_assign,
    may_manage_target,
)
from app.core.security import hash_password
from app.models import AccessRoster, User
from app.schemas.admin import AccessDecision, AccessRosterCreate, AccessRosterUpdate
from app.schemas.common import normalize_pagination, page_payload
from app.services import access_guards, access_roster, audit, reader_profiles
from app.services.access_roster import access_payload, normalise_email, people_for
from app.services.object_store import media_bucket

router = APIRouter(prefix="/access", tags=["access"])

manager = require(Capability.MANAGE_ACCESS)


def _clean(value: Any) -> Any:
    return (value.strip() or None) if isinstance(value, str) else value


async def _row_or_404(session: AsyncSession, row_id: uuid.UUID) -> AccessRoster:
    row = await session.get(AccessRoster, row_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Record not found")
    return row


async def _account_at(session: AsyncSession, email: str) -> User | None:
    return (
        await session.execute(select(User).where(func.lower(User.email) == normalise_email(email)))
    ).scalar_one_or_none()


async def _refuse_when(
    session: AsyncSession, actor: User, row: AccessRoster, guard: access_guards.Guard
) -> None:
    refusal = guard(actor, row, await _account_at(session, row.email))
    if refusal is not None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, refusal)


async def _apply_role_to_account(
    session: AsyncSession, actor: User, email: str, role: str | None
) -> str | None:
    if not role:
        return None
    account = await _account_at(session, email)
    if account is None or account.role == role or is_master_admin(account):
        return None
    if not may_manage_target(actor, account) or not may_assign(actor, role):
        return f"The account at {account.email} keeps its {account.role} role."
    before = account.role
    await reader_profiles.apply_role_change(session, account, role, objects=media_bucket())
    account.role = role
    account.tokenVersion += 1
    await audit.record(
        session,
        action="users.role_changed",
        actor=actor,
        target_type="User",
        target_id=account.id,
        detail={"before": before, "after": role, "via": "access"},
    )
    return None


async def _payload(session: AsyncSession, row: AccessRoster, **extra: Any) -> dict[str, Any]:
    await session.refresh(row)
    return access_payload(row, await people_for(session, [row])) | extra


@router.get("/roster/pending-count")
async def pending_request_count(
    _: User = Depends(manager), session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    waiting = await access_roster.pending_count(session)
    cap = access_roster.pending_cap()
    return {"pending": waiting, "capacity": cap, "capReached": waiting >= cap}


async def _roster_page(
    session: AsyncSession, where: Any, ordering: Any, skip: int, size: int
) -> tuple[int, list[AccessRoster]]:
    count_query: Select[Any] = select(func.count()).select_from(AccessRoster)
    rows_query = select(AccessRoster).order_by(ordering, AccessRoster.id).offset(skip).limit(size)
    if where is not None:
        count_query = count_query.where(where)
        rows_query = rows_query.where(where)
    total = int((await session.execute(count_query)).scalar_one())
    return total, list((await session.execute(rows_query)).scalars().all())


async def _roster_items(session: AsyncSession, actor: User, rows: list[AccessRoster]) -> list[dict[str, Any]]:
    people = await people_for(session, rows)
    accounts = await access_guards.accounts_at(session, rows)
    return [
        access_payload(r, people)
        | {"offers": access_guards.entry_offers(actor, r, accounts.get(normalise_email(r.email)))}
        for r in rows
    ]


@router.get("/roster")
async def list_access_roster(
    *,
    page: int = Query(1, ge=1),
    pageSize: int = Query(50, ge=1, le=200),
    search: str | None = Query(default=None, max_length=200),
    status_filter: list[str] | None = Query(default=None, alias="status"),
    roles: list[str] | None = Query(default=None),
    dateField: str | None = Query(default=None),
    dateFrom: datetime | None = Query(default=None),
    dateTo: datetime | None = Query(default=None),
    sort: str | None = Query(default=None),
    dir: str | None = Query(default=None),
    _: User = Depends(manager),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    where = roster_filter(
        status_filter, search, roles, date_field=dateField, date_from=dateFrom, date_to=dateTo
    )
    ordering = roster_ordering(sort, dir)
    clean_page, clean_size, skip = normalize_pagination(page, pageSize)
    total, rows = await _roster_page(session, where, ordering, skip, clean_size)
    items = await _roster_items(session, _, rows)
    return page_payload(items, total, clean_page, clean_size) | {
        "roleMatchTruncated": False,
        "assignableRoles": assignable_roles(_),
    }


async def _refuse_listed(session: AsyncSession, email: str) -> None:
    existing = await access_roster.access_row(session, email)
    if existing is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"{existing.email} is already on the access roster as {existing.status}. Decide or update that entry.",
        )


async def _create_account(session: AsyncSession, email: str, payload: AccessRosterCreate) -> bool:
    if payload.password is None:
        return False
    if await _account_at(session, email) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "An account already exists for this address.")
    now = datetime.now(UTC)
    session.add(
        User(
            email=email,
            name=(_clean(payload.fullName) or email.split("@")[0])[:160],
            passwordHash=await asyncio.to_thread(hash_password, payload.password),
            passwordSetAt=now,
            passwordIssuerKnown=True,
            mustChangePassword=payload.mustChangePassword,
            role=payload.role or role_for_email(email),
            affiliation=_clean(payload.affiliation),
        )
    )
    return True


@router.post("/roster", status_code=status.HTTP_201_CREATED)
async def add_to_access_roster(
    payload: AccessRosterCreate, actor: User = Depends(manager), session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    email = normalise_email(payload.email)
    refuse_unless_assignable(actor, payload.role or role_for_email(email))
    await _refuse_listed(session, email)
    row = await access_roster.admit(
        session,
        email,
        admit_role=payload.role,
        actor_id=actor.id,
        full_name=_clean(payload.fullName),
        note=_clean(payload.notes),
    )
    row.affiliation = _clean(payload.affiliation)
    account_created = await _create_account(session, email, payload)
    held = await _apply_role_to_account(session, actor, email, payload.role)
    await audit.record(
        session,
        action="access.added",
        actor=actor,
        target_type="AccessRoster",
        target_id=row.id,
        detail={"role": payload.role, "accountCreated": account_created},
    )
    await session.commit()
    return await _payload(session, row, accountPromotionHeld=held, accountCreated=account_created)


async def _reject_request(
    session: AsyncSession, actor: User, row: AccessRoster, payload: AccessDecision
) -> dict[str, Any]:
    await _refuse_when(session, actor, row, access_guards.bar_refusal)
    row.status = access_roster.REJECTED
    row.decidedAt = datetime.now(UTC)
    row.decidedById = actor.id
    if payload.notes is not None:
        row.notes = _clean(payload.notes)
    await access_roster.bar_account(
        session, row.email, actor=actor, cause="access.rejected", objects=media_bucket()
    )
    await audit.record(
        session, action="access.rejected", actor=actor, target_type="AccessRoster", target_id=row.id
    )
    await session.commit()
    return await _payload(session, row, accountPromotionHeld=None)


async def _approve_request(
    session: AsyncSession, actor: User, row: AccessRoster, payload: AccessDecision
) -> dict[str, Any]:
    await _refuse_when(session, actor, row, access_guards.reinstate_refusal)
    granted = payload.role or access_roster.role_of(row) or role_for_email(row.email)
    refuse_unless_assignable(actor, granted)
    row = await access_roster.admit(
        session,
        row.email,
        admit_role=granted,
        actor_id=actor.id,
        note=_clean(payload.notes) if payload.notes is not None else None,
    )
    held = await _apply_role_to_account(session, actor, row.email, granted)
    await audit.record(
        session,
        action="access.approved",
        actor=actor,
        target_type="AccessRoster",
        target_id=row.id,
        detail={"role": granted},
    )
    await session.commit()
    return await _payload(session, row, accountPromotionHeld=held)


@router.post("/roster/{row_id}/decision")
async def decide_access_request(
    row_id: uuid.UUID,
    payload: AccessDecision,
    actor: User = Depends(manager),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    row = await _row_or_404(session, row_id)
    if payload.decision == "REJECT":
        return await _reject_request(session, actor, row, payload)
    return await _approve_request(session, actor, row, payload)


@router.patch("/roster/{row_id}")
async def update_access_entry(
    row_id: uuid.UUID,
    payload: AccessRosterUpdate,
    actor: User = Depends(manager),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    row = await _row_or_404(session, row_id)
    values = payload.model_dump(exclude_unset=True)
    if values:
        await _refuse_when(session, actor, row, access_guards.change_refusal)
    held = None
    if "role" in values:
        refuse_unless_assignable(actor, values["role"] or role_for_email(row.email))
        row.admitRole = values["role"]
        if access_roster.admits(row):
            held = await _apply_role_to_account(session, actor, row.email, values["role"])
    for key in ("fullName", "notes", "affiliation"):
        if key in values:
            setattr(row, key, _clean(values[key]))
    if values:
        await audit.record(
            session,
            action="access.updated",
            actor=actor,
            target_type="AccessRoster",
            target_id=row.id,
            detail={"fields": sorted(values)},
        )
        await session.commit()
    return await _payload(session, row, accountPromotionHeld=held)


@router.delete("/roster/{row_id}")
async def suspend_access_entry(
    row_id: uuid.UUID, actor: User = Depends(manager), session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    row = await _row_or_404(session, row_id)
    if access_roster.status_of(row) == access_roster.SUSPENDED:
        return await _payload(session, row)
    await _refuse_when(session, actor, row, access_guards.bar_refusal)
    row.status = access_roster.SUSPENDED
    row.decidedAt = row.decidedAt or datetime.now(UTC)
    row.decidedById = row.decidedById or actor.id
    await access_roster.bar_account(
        session, row.email, actor=actor, cause="access.suspended", objects=media_bucket()
    )
    await audit.record(
        session, action="access.suspended", actor=actor, target_type="AccessRoster", target_id=row.id
    )
    await session.commit()
    return await _payload(session, row)
