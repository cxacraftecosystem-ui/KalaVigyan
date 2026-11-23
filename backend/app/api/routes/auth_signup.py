import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth_session import THROTTLED_DETAIL, find_user, role_for_email
from app.core.config import get_settings
from app.core.db import get_session, session_scope
from app.core.rate_limit import client_ip, ip_hash, sign_in_attempt_by_ip
from app.core.throttle_refusal import refuse_when_throttled
from app.models import ConsentRecord, RoleRequest, User
from app.schemas.auth import SignUpRequest
from app.services import audit, credential_links, mailer, turnstile

router = APIRouter()

SIGNUP_CLOSED_DETAIL = "Request access with Google instead."
SIGNUP_ROLE_LABELS = {
    "STUDENT": "Student",
    "ARTISAN": "Artisan",
    "RESEARCHER": "Researcher",
    "PROFESSOR": "Professor",
}


@router.post("/signup", status_code=status.HTTP_202_ACCEPTED)
async def signup(
    payload: SignUpRequest,
    request: Request,
    background: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    await _refuse_unready_signup(payload, request)
    email = str(payload.email).strip().lower()
    if email == get_settings().master_admin_email.strip().lower():
        return _signup_answer(email)
    existing = await find_user(session, email)
    if existing is not None:
        if existing.deletedAt is None and existing.emailVerifiedAt is None and existing.passwordHash is None:
            background.add_task(_send_signup_link, email, existing.id)
        return _signup_answer(email)
    user = await _record_signup(session, payload, email, request)
    await session.commit()
    background.add_task(_send_signup_link, email, user.id)
    return _signup_answer(email)


async def _refuse_unready_signup(payload: SignUpRequest, request: Request) -> None:
    refuse_when_throttled(await sign_in_attempt_by_ip(request), THROTTLED_DETAIL)
    if turnstile.required_but_missing() or not mailer.mail_configured():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, SIGNUP_CLOSED_DETAIL)
    if not await turnstile.verify(payload.turnstileToken, client_ip(request)):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The human check did not pass. Try again.")
    if not payload.ageAttested:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "Confirm you are old enough to use KalaVigyan."
        )


async def _record_signup(session: AsyncSession, payload: SignUpRequest, email: str, request: Request) -> User:
    now = datetime.now(UTC)
    user = User(
        email=email,
        name=payload.name.strip()[:200],
        role=role_for_email(email),
        authProvider="LOCAL",
        affiliation=(payload.affiliation or "").strip() or None,
        ageAttestedAt=now,
    )
    session.add(user)
    await session.flush()
    session.add(
        ConsentRecord(
            userId=user.id, kind="PRIVACY_NOTICE", noticeVersion=payload.privacyNoticeVersion, acceptedAt=now
        )
    )
    session.add(
        RoleRequest(
            userId=user.id,
            requestedRole=payload.requestedRole,
            affiliation=user.affiliation,
            profileUrl=payload.profileUrl,
            note=_signup_notes(payload),
        )
    )
    await audit.record(
        session,
        action="auth.signup",
        actor=None,
        target_type="User",
        target_id=user.id,
        ip_hash=ip_hash(client_ip(request)),
    )
    return user


def _signup_answer(email: str) -> dict[str, Any]:
    return {"status": "EMAIL_SENT", "email": email}


def _signup_notes(payload: SignUpRequest) -> str:
    parts = [f"Requested role: {SIGNUP_ROLE_LABELS[payload.requestedRole]}."]
    if payload.profileUrl:
        parts.append(f"Profile: {payload.profileUrl}")
    if payload.note and payload.note.strip():
        parts.append(payload.note.strip())
    return "\n".join(parts)


async def _send_signup_link(email: str, user_id: uuid.UUID) -> None:
    async with session_scope() as session:
        account = await session.get(User, user_id)
        if account is None or account.deletedAt is not None or account.emailVerifiedAt is not None:
            return
        try:
            issued, _raw = await credential_links.issue_link(
                session, user=account, purpose="INVITE", issued_by_id=None
            )
        except credential_links.IssueThrottled:
            return
        await session.commit()
        await mailer.send(mailer.signup_link_mail(email, issued.link, credential_links.INVITE_MINUTES))
