import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth_session import SAME_PASSWORD_DETAIL, adopt_admitted_role, find_user
from app.core.db import get_session, session_scope
from app.core.deps import is_configured_master_admin, require
from app.core.rate_limit import client_ip, forgot_password_attempt, ip_hash
from app.core.roles import Capability, may_manage_target
from app.core.security import hash_password, verify_password
from app.core.throttle_refusal import refuse_when_throttled, too_many_requests
from app.models import AccessRoster, PasswordResetRequest, PasswordResetToken, RoleRequest, User
from app.schemas.auth import (
    ForgotPasswordRequest,
    IssuePasswordLinkRequest,
    PasswordLinkCheckRequest,
    SetPasswordRequest,
)
from app.services import access_roster, audit, credential_links, mailer

router = APIRouter()

RESETS_SPENT_DETAIL = "Too many reset requests. Try again later."
LINKS_SPENT_DETAIL = "Several links were issued this hour. Wait, or use one of them."
LINKS_SPENT_WAIT_SECONDS = 3600
FORGOT_PASSWORD_MESSAGE = "If that address has a password here, a reset link is on its way."

SET_PASSWORD_REFUSALS = {
    credential_links.MISSING: "This link is incomplete. Open the whole link.",
    credential_links.MALFORMED: "This is not a link this site issued.",
    credential_links.EXPIRED: "This link has expired. Ask for a new one.",
    credential_links.REVOKED: "This link was withdrawn. Ask for a new one.",
    credential_links.SPENT: "This link has already been used. Sign in with the password you set.",
    credential_links.UNKNOWN_ACCOUNT: "This link no longer points at an account.",
}


@router.post("/password-links", status_code=status.HTTP_201_CREATED)
async def issue_password_link(
    payload: IssuePasswordLinkRequest,
    actor: User = Depends(require(Capability.MANAGE_ACCESS)),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    target = await _link_target(session, actor, payload.userId)
    if payload.delivery == "EMAIL" and not mailer.mail_configured():
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "Copy the link instead and pass it on yourself."
        )
    purpose = credential_links.purpose_for(target)
    try:
        issued, _raw = await credential_links.issue_link(
            session, user=target, purpose=purpose, issued_by_id=actor.id
        )
    except credential_links.IssueThrottled as exc:
        raise too_many_requests(LINKS_SPENT_DETAIL, LINKS_SPENT_WAIT_SECONDS) from exc
    await audit.record(
        session,
        action="auth.password_link_issued",
        actor=actor,
        target_type="User",
        target_id=target.id,
        detail={"purpose": purpose, "delivery": payload.delivery},
    )
    await session.commit()
    delivered = await _delivered_by(payload.delivery, target, issued, purpose)
    return {
        "id": issued.id,
        "link": issued.link if delivered == "COPY_LINK" else None,
        "expiresAt": issued.expiresAt,
        "purpose": issued.purpose,
        "deliveredBy": delivered,
    }


@router.post("/password-links/{link_id}/revoke")
async def revoke_password_link(
    link_id: uuid.UUID,
    actor: User = Depends(require(Capability.MANAGE_ACCESS)),
    session: AsyncSession = Depends(get_session),
) -> dict[str, bool]:
    row = await session.get(PasswordResetToken, link_id)
    target = await session.get(User, row.userId) if row is not None else None
    if row is None or target is None or not may_manage_target(actor, target):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Link not found")
    if not await credential_links.revoke_link(session, link_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Link not found")
    await audit.record(
        session, action="auth.password_link_revoked", actor=actor, target_type="User", target_id=target.id
    )
    await session.commit()
    return {"ok": True}


@router.get("/set-password")
async def check_set_password_token(
    token: str = "", session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    return await _link_check(session, token)


@router.post("/set-password/check")
async def check_set_password_token_in_body(
    payload: PasswordLinkCheckRequest, session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    return await _link_check(session, payload.token)


@router.post("/set-password")
async def set_password(
    payload: SetPasswordRequest, session: AsyncSession = Depends(get_session)
) -> dict[str, bool]:
    verdict = await credential_links.describe_token(session, payload.token)
    account = await _link_account(session, verdict)
    if account.passwordHash and await asyncio.to_thread(
        verify_password, payload.password, account.passwordHash
    ):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, SAME_PASSWORD_DETAIL)
    had_password = account.passwordHash is not None
    now = datetime.now(UTC)
    account.passwordHash = await asyncio.to_thread(hash_password, payload.password)
    account.passwordSetAt = now
    account.mustChangePassword = False
    account.passwordIssuerKnown = False
    account.sessionsValidFrom = now
    account.tokenVersion += 1
    if account.emailVerifiedAt is None:
        account.emailVerifiedAt = now
        await adopt_admitted_role(session, account, await access_roster.access_row(session, account.email))
        await _record_verified_request(session, account)
    await credential_links.mark_used_and_revoke_rest(session, verdict)
    await audit.record(
        session,
        action="auth.password_set_by_link",
        actor=None,
        target_type="User",
        target_id=account.id,
        detail={"purpose": verdict.purpose},
    )
    await session.commit()
    if had_password:
        await mailer.send(mailer.password_changed_mail(account.email))
    return {"ok": True}


@router.post("/forgot-password")
async def forgot_password(
    payload: ForgotPasswordRequest, request: Request, response: Response, background: BackgroundTasks
) -> dict[str, str]:
    refuse_when_throttled(await forgot_password_attempt(request), RESETS_SPENT_DETAIL)
    background.add_task(
        _request_password_reset,
        str(payload.email).strip().lower(),
        ip_hash(client_ip(request)),
        request.headers.get("user-agent"),
    )
    response.headers["Cache-Control"] = "no-store"
    return {"message": FORGOT_PASSWORD_MESSAGE}


async def _link_target(session: AsyncSession, actor: User, user_id: str) -> User:
    try:
        target_id = uuid.UUID(user_id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found") from exc
    target = await session.get(User, target_id)
    if target is None or target.deletedAt is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if target.id == actor.id or not may_manage_target(actor, target) or is_configured_master_admin(target):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can't issue a password link for this account.")
    return target


async def _delivered_by(
    delivery: str, target: User, issued: credential_links.IssuedLink, purpose: str
) -> str:
    if delivery != "EMAIL":
        return "COPY_LINK"
    minutes = credential_links.minutes_for(purpose)
    mail = (mailer.invite_link_mail if purpose == "INVITE" else mailer.reset_link_mail)(
        target.email, issued.link, minutes
    )
    return "EMAIL" if await mailer.send(mail) else "COPY_LINK"


async def _link_check(session: AsyncSession, raw: str | None) -> dict[str, Any]:
    verdict = await credential_links.describe_token(session, raw)
    return {"valid": verdict.ok, "reason": verdict.reason, "purpose": verdict.purpose}


async def _link_account(session: AsyncSession, verdict: credential_links.TokenVerdict) -> User:
    if not verdict.ok or verdict.user_id is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            SET_PASSWORD_REFUSALS.get(verdict.reason or "", "This password link is not valid."),
        )
    account = await session.get(User, verdict.user_id)
    if account is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, SET_PASSWORD_REFUSALS[credential_links.UNKNOWN_ACCOUNT]
        )
    return account


async def _record_verified_request(session: AsyncSession, account: User) -> None:
    if await access_roster.access_row(session, account.email) is not None:
        return
    request = (
        await session.execute(
            select(RoleRequest)
            .where(RoleRequest.userId == account.id, RoleRequest.status == "PENDING")
            .order_by(RoleRequest.createdAt.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if request is None:
        return
    if await access_roster.pending_count(session) >= access_roster.pending_cap():
        return
    now = datetime.now(UTC)
    session.add(
        AccessRoster(
            email=account.email,
            status=access_roster.PENDING,
            requestedAt=now,
            attemptCount=1,
            lastAttemptAt=now,
            fullName=account.name[:180],
            affiliation=request.affiliation,
            notes=request.note,
        )
    )


async def _request_password_reset(email: str, ip: str | None, user_agent: str | None) -> None:
    async with session_scope() as session:
        account = await find_user(session, email)
        outcome = "NO_ACCOUNT"
        if account is not None and account.deletedAt is None and account.passwordHash is not None:
            try:
                issued, _raw = await credential_links.issue_link(
                    session, user=account, purpose="RESET", issued_by_id=None
                )
            except credential_links.IssueThrottled:
                outcome = "THROTTLED"
            else:
                outcome = (
                    "SENT"
                    if await mailer.send(
                        mailer.reset_link_mail(account.email, issued.link, credential_links.RESET_MINUTES)
                    )
                    else "MAIL_UNAVAILABLE"
                )
        elif account is not None:
            outcome = "NO_PASSWORD"
        session.add(
            PasswordResetRequest(
                email=email[:320],
                accountId=account.id if account else None,
                outcome=outcome,
                ipHash=ip,
                userAgent=(user_agent or "")[:400] or None,
            )
        )
