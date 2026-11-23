import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import String, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import guardian_hold
from app.core.config import get_settings
from app.core.db import get_session
from app.core.deps import (
    is_configured_master_admin,
    refusal_for,
    refuse_unless_assignable,
    refuse_unless_manageable,
    require,
)
from app.core.roles import ROLE_RANK, STUDENT, Capability, can, role_value
from app.models import AccessRoster, ConsentRecord, User
from app.schemas.admin import GuardianConsentRequest, SuspendRequest, UserUpdate
from app.schemas.common import normalize_pagination, page_payload
from app.services import (
    access_roster,
    audit,
    credential_links,
    reader_profiles,
    share_owners,
    testimony_writes,
    two_factor,
)
from app.services.object_store import media_bucket
from app.services.users import serialize_user

router = APIRouter(prefix="/users", tags=["users"])

ROLE_SORT = "role"
USER_SORTS = {
    "created": "createdAt",
    "name": "name",
    "email": "email",
    ROLE_SORT: "role",
    "lastLogin": "lastLoginAt",
}

lister = require(Capability.LIST_USERS)
role_changer = require(Capability.CHANGE_ROLES)
disabler = require(Capability.DISABLE_USERS)
guardian_confirmer = require(Capability.CONFIRM_GUARDIAN_CONSENT)

NOT_A_STUDENT_DETAIL = "Guardian consent is confirmed for student accounts only."
STALE_STATEMENT_DETAIL = "Confirm the current statement, version {version}."
ALREADY_CONFIRMED_DETAIL = "Guardian consent is already confirmed for this student."


async def _target(session: AsyncSession, user_id: uuid.UUID) -> User:
    target = await session.get(User, user_id)
    if target is None or target.deletedAt is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return target


def _protect_master(target: User, actor: User) -> None:
    if is_configured_master_admin(target) and target.id != actor.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "The master admin account is protected")


async def _guardian_marks(
    session: AsyncSession, pairs: list[tuple[User, dict[str, Any]]]
) -> list[dict[str, Any]]:
    students = [user.id for user, _ in pairs if role_value(user) == STUDENT]
    confirmed = await guardian_hold.confirmed_among(session, students)
    for user, item in pairs:
        if role_value(user) == STUDENT:
            item["guardianConsent"] = "CONFIRMED" if user.id in confirmed else "NOT_CONFIRMED"
    return [item for _, item in pairs]


async def _listed(session: AsyncSession, rows: Any) -> list[dict[str, Any]]:
    master_email = get_settings().master_admin_email.strip().lower()
    pairs = [
        (
            user,
            serialize_user(
                user,
                access_status="ACTIVE"
                if user.email.lower() == master_email
                else (row_status or "NOT_LISTED"),
            ),
        )
        for user, row_status in rows
    ]
    return await _guardian_marks(session, pairs)


def _sort_column(sort: str) -> Any:
    if sort == ROLE_SORT:
        return case(ROLE_RANK, value=User.role.cast(String))
    return getattr(User, USER_SORTS[sort])


async def _with_access(session: AsyncSession, user: User) -> dict[str, Any]:
    row = await access_roster.access_row(session, user.email)
    access = "ACTIVE" if is_configured_master_admin(user) else (access_roster.status_of(row) or "NOT_LISTED")
    (item,) = await _guardian_marks(session, [(user, serialize_user(user, access_status=access))])
    return item


@router.get("")
async def list_users(
    search: str | None = Query(default=None, max_length=200),
    role: str | None = None,
    access: str | None = Query(default=None, pattern="^(ACTIVE|PENDING|REJECTED|SUSPENDED|NOT_LISTED)$"),
    sort: str = Query(default="created"),
    dir: str = Query(default="desc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    _: User = Depends(lister),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    if role is not None and role not in ROLE_RANK:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Unknown role {role!r}")
    if sort not in USER_SORTS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, f"sort must be one of {', '.join(USER_SORTS)}"
        )
    clean_page, clean_size, skip = normalize_pagination(page, pageSize)
    joined = (
        select(User, AccessRoster.status)
        .outerjoin(AccessRoster, func.lower(User.email) == AccessRoster.email)
        .where(User.deletedAt.is_(None))
    )
    if role:
        joined = joined.where(User.role == role)
    if search and search.strip():
        like = f"%{search.strip()}%"
        joined = joined.where(or_(User.name.ilike(like), User.email.ilike(like)))
    if access == "NOT_LISTED":
        joined = joined.where(AccessRoster.id.is_(None))
    elif access:
        joined = joined.where(AccessRoster.status == access)
    total = int((await session.execute(select(func.count()).select_from(joined.subquery()))).scalar_one())
    column = _sort_column(sort)
    ordering = column.asc().nulls_last() if dir == "asc" else column.desc().nulls_last()
    rows = (await session.execute(joined.order_by(ordering, User.id).offset(skip).limit(clean_size))).all()
    return page_payload(await _listed(session, rows), total, clean_page, clean_size)


@router.get("/{user_id}")
async def get_user(
    user_id: uuid.UUID, _: User = Depends(lister), session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    return await _with_access(session, await _target(session, user_id))


@router.patch("/{user_id}")
async def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    actor: User = Depends(lister),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    target = await _target(session, user_id)
    data = payload.model_dump(exclude_unset=True)
    is_self = target.id == actor.id
    if "role" in data:
        if not can(actor, Capability.CHANGE_ROLES):
            raise HTTPException(status.HTTP_403_FORBIDDEN, refusal_for(Capability.CHANGE_ROLES))
        if is_self:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You cannot change your own role.")
        refuse_unless_assignable(actor, data["role"])
        _protect_master(target, actor)
    if not is_self:
        refuse_unless_manageable(actor, target)
    if data.get("mustChangePassword") is True and target.passwordHash is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "This account has no password to change.")
    changed: list[str] = []
    for field in ("name", "affiliation", "mustChangePassword"):
        if field in data and data[field] is not None and getattr(target, field) != data[field]:
            setattr(target, field, data[field])
            changed.append(field)
    if "role" in data and data["role"] != target.role:
        before = target.role
        await reader_profiles.apply_role_change(session, target, data["role"], objects=media_bucket())
        target.role = data["role"]
        target.tokenVersion += 1
        changed.append("role")
        await credential_links.revoke_outstanding(session, target.id)
        row = await access_roster.access_row(session, target.email)
        if row is not None:
            row.admitRole = data["role"]
        await audit.record(
            session,
            action="users.role_changed",
            actor=actor,
            target_type="User",
            target_id=target.id,
            detail={"before": before, "after": data["role"], "via": "users"},
        )
    if "mustChangePassword" in changed and target.mustChangePassword:
        target.tokenVersion += 1
    if changed:
        await audit.record(
            session,
            action="users.updated",
            actor=actor,
            target_type="User",
            target_id=target.id,
            detail={"fields": changed},
        )
        await session.commit()
        await session.refresh(target)
    return await _with_access(session, target)


async def _set_access(
    session: AsyncSession, actor: User, target: User, new_status: str, note: str | None
) -> None:
    now = datetime.now(UTC)
    row = await access_roster.access_row(session, target.email)
    if row is None:
        row = AccessRoster(
            email=target.email.lower(),
            status=new_status,
            admitRole=target.role,
            addedById=actor.id,
            decidedAt=now,
            decidedById=actor.id,
            joinedAt=now if new_status == "ACTIVE" else None,
        )
        session.add(row)
    else:
        row.status = new_status
        row.decidedAt = now
        row.decidedById = actor.id
        if new_status == "ACTIVE":
            row.joinedAt = row.joinedAt or now
    if note:
        row.notes = note


@router.post("/{user_id}/suspend")
async def suspend_user(
    user_id: uuid.UUID,
    payload: SuspendRequest | None = None,
    actor: User = Depends(disabler),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    target = await _target(session, user_id)
    if target.id == actor.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You cannot suspend your own account.")
    _protect_master(target, actor)
    refuse_unless_manageable(actor, target)
    await _set_access(session, actor, target, access_roster.SUSPENDED, payload.reason if payload else None)
    target.tokenVersion += 1
    target.sessionsValidFrom = datetime.now(UTC)
    await share_owners.withdraw_shares(
        session, target.id, actor=actor, cause="users.suspended", objects=media_bucket()
    )
    await audit.record(
        session, action="users.suspended", actor=actor, target_type="User", target_id=target.id
    )
    await session.commit()
    await session.refresh(target)
    return await _with_access(session, target)


@router.post("/{user_id}/restore")
async def restore_user(
    user_id: uuid.UUID, actor: User = Depends(disabler), session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    target = await _target(session, user_id)
    refuse_unless_manageable(actor, target)
    await _set_access(session, actor, target, access_roster.ACTIVE, None)
    await audit.record(session, action="users.restored", actor=actor, target_type="User", target_id=target.id)
    await session.commit()
    await session.refresh(target)
    return await _with_access(session, target)


@router.post("/{user_id}/sign-out-everywhere")
async def sign_out_everywhere(
    user_id: uuid.UUID, actor: User = Depends(lister), session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    target = await _target(session, user_id)
    if target.id == actor.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Change your password to end your own other sessions.")
    refuse_unless_manageable(actor, target)
    target.tokenVersion += 1
    target.sessionsValidFrom = datetime.now(UTC)
    await audit.record(
        session, action="users.signed_out_everywhere", actor=actor, target_type="User", target_id=target.id
    )
    await session.commit()
    await session.refresh(target)
    return await _with_access(session, target)


@router.delete("/{user_id}/two-factor")
async def reset_two_factor(
    user_id: uuid.UUID, actor: User = Depends(disabler), session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    target = await _target(session, user_id)
    if target.id == actor.id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Use your own settings to manage two-step verification."
        )
    refuse_unless_manageable(actor, target)
    if not target.twoFactorEnabled:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Two-step verification is already off for this account."
        )
    destroyed = await two_factor.reset_by_administrator(session, target)
    await audit.record(
        session,
        action="users.two_factor_reset",
        actor=actor,
        target_type="User",
        target_id=target.id,
        detail={"recoveryCodesDestroyed": destroyed},
    )
    await session.commit()
    fresh = await session.get(User, target.id, populate_existing=True)
    assert fresh is not None
    return await _with_access(session, fresh)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: uuid.UUID, actor: User = Depends(disabler), session: AsyncSession = Depends(get_session)
) -> None:
    target = await _target(session, user_id)
    if target.id == actor.id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "You cannot delete your own account.")
    if is_configured_master_admin(target):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "The master admin account cannot be deleted")
    refuse_unless_manageable(actor, target)
    target.deletedAt = datetime.now(UTC)
    target.tokenVersion += 1
    await credential_links.revoke_outstanding(session, target.id)
    await testimony_writes.erase_artisan(session, media_bucket(), target, now=target.deletedAt)
    await share_owners.withdraw_shares(
        session, target.id, actor=actor, cause="users.deleted", objects=media_bucket()
    )
    await audit.record(session, action="users.deleted", actor=actor, target_type="User", target_id=target.id)
    await session.commit()


@router.post("/{user_id}/guardian-consent", status_code=status.HTTP_201_CREATED)
async def confirm_guardian_consent(
    user_id: uuid.UUID,
    payload: GuardianConsentRequest,
    actor: User = Depends(guardian_confirmer),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    target = await _target(session, user_id)
    refuse_unless_manageable(actor, target)
    if role_value(target) != STUDENT:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_A_STUDENT_DETAIL)
    version = guardian_hold.GUARDIAN_STATEMENT_VERSION
    if payload.noticeVersion != version:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, STALE_STATEMENT_DETAIL.format(version=version)
        )
    if await guardian_hold.guardian_confirmed(session, target.id):
        raise HTTPException(status.HTTP_409_CONFLICT, ALREADY_CONFIRMED_DETAIL)
    now = datetime.now(UTC)
    session.add(
        ConsentRecord(
            userId=target.id,
            kind=guardian_hold.GUARDIAN_CONSENT,
            noticeVersion=version,
            acceptedAt=now,
            recordedById=actor.id,
        )
    )
    await audit.record(
        session,
        action="users.guardian_consent_confirmed",
        actor=actor,
        target_type="User",
        target_id=target.id,
        detail={"noticeVersion": version},
    )
    await session.commit()
    return {"userId": str(target.id), "confirmedAt": now.isoformat()}
