import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session, session_scope
from app.core.deps import (
    get_current_user,
    get_current_user_any_step,
    is_break_glass_master,
    is_configured_master_admin,
    require,
)
from app.core.rate_limit import (
    client_ip,
    forgot_password_attempt,
    ip_hash,
    refund_account,
    refund_ip,
    sign_in_attempt_by_account,
    sign_in_attempt_by_ip,
)
from app.core.roles import (
    ADMIN,
    MASTER_ADMIN,
    STUDENT,
    Capability,
    has_rank,
    is_known_role,
    may_manage_target,
    role_value,
)
from app.core.security import create_access_token, hash_password, verify_password, verify_password_or_decoy
from app.core.throttle_refusal import refuse_when_throttled, too_many_requests
from app.models import AccessRoster, ConsentRecord, PasswordResetRequest, RoleRequest, User
from app.schemas.auth import (
    ConsentRequest,
    ForgotPasswordRequest,
    GoogleLinkRequest,
    IssuePasswordLinkRequest,
    LoginRequest,
    OidcCodeFields,
    OidcNonceRequest,
    PasswordLinkCheckRequest,
    SetPasswordRequest,
    SignUpRequest,
)
from app.services import (
    access_roster,
    audit,
    auth_nonces,
    credential_links,
    google_auth,
    mailer,
    oidc_sign_in,
    reader_profiles,
    turnstile,
    two_factor,
)
from app.services.users import serialize_user

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)

ACCESS_STATUS_HEADER = "X-Access-Status"
SESSION_TOKEN_HEADER = "X-Session-Token"
SIGN_IN_HINT_HEADER = "X-Sign-In-Hint"
TWO_FACTOR_REQUIRED_HEADER = "X-Two-Factor-Required"

ACCESS_PENDING_DETAIL = "Your access request is waiting for an administrator to approve it."
ACCESS_REJECTED_DETAIL = (
    "Your access request was not approved. Contact the administrator if this is a mistake."
)
ACCESS_SUSPENDED_DETAIL = "Your access has been suspended. Contact the administrator."
ACCESS_NOT_RECORDED_DETAIL = "Access requests are closed for now. Contact the administrator directly."
INVALID_CREDENTIALS_DETAIL = "Invalid email or password"
THROTTLED_DETAIL = "Too many sign-in attempts. Wait a few minutes and try again."
RESETS_SPENT_DETAIL = "Too many reset requests. Try again later."
LINKS_SPENT_DETAIL = "Several links were issued this hour. Wait, or use one of them."
LINKS_SPENT_WAIT_SECONDS = 3600
PASSWORD_NOT_SET_HINT = "PASSWORD_NOT_SET"
PASSWORD_NOT_SET_DETAIL = (
    "This account has no password yet. Sign in with {label}, or ask for a set-password link."
)
EMAIL_UNVERIFIED_HINT = "EMAIL_UNVERIFIED"
EMAIL_UNVERIFIED_DETAIL = (
    "Confirm your email address first: open the link we sent, or ask for a new one with Forgot password."
)
PROVIDER_UNAVAILABLE_DETAIL = (
    "{label} sign-in isn't available right now. Sign in with your email and password."
)
PROVIDER_FAILED_DETAIL = "{label} sign-in didn't work. Try again."
PROVIDER_UNVERIFIED_DETAIL = "This {label} account's email address isn't verified."
GOOGLE_PROVIDER = "GOOGLE"
GOOGLE_UNAVAILABLE_DETAIL = PROVIDER_UNAVAILABLE_DETAIL.format(label="Google")
GOOGLE_FAILED_DETAIL = PROVIDER_FAILED_DETAIL.format(label="Google")
GOOGLE_UNVERIFIED_DETAIL = PROVIDER_UNVERIFIED_DETAIL.format(label="Google")
SAME_PASSWORD_DETAIL = "Choose a password different from the one you have now."
FORGOT_PASSWORD_MESSAGE = "If that address has a password here, a reset link is on its way."

SET_PASSWORD_REFUSALS = {
    credential_links.MISSING: "This link is incomplete. Open the whole link.",
    credential_links.MALFORMED: "This is not a link this site issued.",
    credential_links.EXPIRED: "This link has expired. Ask for a new one.",
    credential_links.REVOKED: "This link was withdrawn. Ask for a new one.",
    credential_links.SPENT: "This link has already been used. Sign in with the password you set.",
    credential_links.UNKNOWN_ACCOUNT: "This link no longer points at an account.",
}


def _access_headers(access_status: str) -> dict[str, str]:
    return {ACCESS_STATUS_HEADER: access_status}


def role_for_email(email: str) -> str:
    settings = get_settings()
    if email.strip().lower() == settings.master_admin_email.strip().lower():
        return MASTER_ADMIN
    role = settings.default_signup_role
    return role if is_known_role(role) and not has_rank(role, ADMIN) else STUDENT


async def assert_access_admits(session: AsyncSession, email: str, *, is_master: bool) -> Any:
    if is_master:
        return None
    row = await access_roster.access_row(session, email)
    if access_roster.admits(row):
        return row
    outcome = await access_roster.record_refused_attempt(session, email, row)
    if outcome == access_roster.REJECTED:
        raise HTTPException(status.HTTP_403_FORBIDDEN, ACCESS_REJECTED_DETAIL, _access_headers(outcome))
    if outcome == access_roster.SUSPENDED:
        raise HTTPException(status.HTTP_403_FORBIDDEN, ACCESS_SUSPENDED_DETAIL, _access_headers(outcome))
    if outcome == access_roster.NOT_RECORDED:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, ACCESS_NOT_RECORDED_DETAIL, _access_headers(outcome)
        )
    raise HTTPException(
        status.HTTP_403_FORBIDDEN, ACCESS_PENDING_DETAIL, _access_headers(access_roster.PENDING)
    )


def session_token(user: User) -> str:
    return create_access_token(
        str(user.id),
        token_version=user.tokenVersion,
        extra_claims={"email": user.email, "role": role_value(user)},
    )


async def reload_user(session: AsyncSession, user_id: uuid.UUID) -> User:
    user = (
        await session.execute(
            select(User).where(User.id == user_id).execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "This account no longer exists. Sign in again.")
    return user


async def open_session(session: AsyncSession, user: User, access: Any) -> dict[str, Any]:
    now = datetime.now(UTC)
    await access_roster.mark_access_seen(session, access)
    user.lastLoginAt = now
    if user.firstLoginAt is None:
        user.firstLoginAt = now
    await session.commit()
    user = await reload_user(session, user.id)
    return {
        "accessToken": session_token(user),
        "tokenType": "bearer",
        "user": serialize_user(user, access_status=access_roster.status_of(access) or "ACTIVE"),
    }


async def _find_user(session: AsyncSession, email: str) -> User | None:
    return (
        await session.execute(select(User).where(func.lower(User.email) == email.strip().lower()))
    ).scalar_one_or_none()


def _sign_in_label(user: User) -> str:
    provider = str(user.authProvider or "")
    return oidc_sign_in.label_of(provider) if provider in oidc_sign_in.PROVIDERS else "Google"


async def _adopt_admitted_role(session: AsyncSession, account: User, row: Any) -> None:
    admitted = access_roster.role_of(row) if access_roster.admits(row) else None
    if not admitted or role_value(account) in (admitted, MASTER_ADMIN):
        return
    await reader_profiles.apply_role_change(session, account, admitted)
    account.role = admitted
    account.tokenVersion += 1


@dataclass(frozen=True)
class VerifiedMailbox:
    email: str
    display_name: str | None
    avatar_url: str | None
    provider: str


def _account_name(mailbox: VerifiedMailbox, role: str, access: Any) -> str:
    if access is not None and access.fullName:
        return str(access.fullName)[:200]
    if role == MASTER_ADMIN:
        return get_settings().master_admin_name[:200]
    return str(mailbox.display_name or mailbox.email.split("@")[0])[:200]


async def _clear_unverified_credentials(session: AsyncSession, account: User) -> User:
    if account.emailVerifiedAt is not None or account.passwordIssuerKnown:
        return account
    had_password = account.passwordHash is not None
    had_two_factor = account.twoFactorEnabled or account.twoFactorPendingSecret is not None
    if not (had_password or had_two_factor):
        return account
    account.passwordHash = None
    account.passwordSetAt = None
    account.mustChangePassword = False
    await two_factor.reset_by_administrator(session, account)
    await credential_links.revoke_outstanding(session, account.id)
    await audit.record(
        session,
        action="auth.unverified_credentials_cleared",
        actor=None,
        target_type="User",
        target_id=account.id,
        detail={"password": had_password, "twoFactor": had_two_factor},
    )
    await session.flush()
    return await reload_user(session, account.id)


async def _update_verified_account(
    session: AsyncSession, existing: User, mailbox: VerifiedMailbox, *, name: str, role: str, access: Any
) -> User:
    if existing.deletedAt is not None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, ACCESS_SUSPENDED_DETAIL, _access_headers(access_roster.SUSPENDED)
        )
    existing = await _clear_unverified_credentials(session, existing)
    if existing.emailVerifiedAt is None:
        await _adopt_admitted_role(session, existing, access)
    if existing.passwordHash is None:
        existing.name = name
        if str(existing.authProvider) in ("LOCAL", mailbox.provider):
            existing.authProvider = mailbox.provider
    if mailbox.provider == GOOGLE_PROVIDER:
        existing.avatarUrl = mailbox.avatar_url
    existing.emailVerifiedAt = existing.emailVerifiedAt or datetime.now(UTC)
    if role == MASTER_ADMIN and existing.passwordHash is None and role_value(existing) != MASTER_ADMIN:
        await reader_profiles.apply_role_change(session, existing, MASTER_ADMIN)
        existing.role = MASTER_ADMIN
        existing.tokenVersion += 1
    await session.flush()
    return existing


async def sign_in_verified_mailbox(session: AsyncSession, mailbox: VerifiedMailbox) -> tuple[User, Any]:
    role = role_for_email(mailbox.email)
    access = await assert_access_admits(session, mailbox.email, is_master=role == MASTER_ADMIN)
    name = _account_name(mailbox, role, access)
    existing = await _find_user(session, mailbox.email)
    if existing is not None:
        updated = await _update_verified_account(
            session, existing, mailbox, name=name, role=role, access=access
        )
        return updated, access
    admitted_role = access_roster.role_of(access) if access is not None else None
    created = User(
        email=mailbox.email,
        name=name,
        avatarUrl=mailbox.avatar_url,
        authProvider=mailbox.provider,
        role=MASTER_ADMIN if role == MASTER_ADMIN else (admitted_role or role),
        emailVerifiedAt=datetime.now(UTC),
    )
    session.add(created)
    await session.flush()
    return created, access


async def login_with_google(session: AsyncSession, token: str) -> tuple[User, Any]:
    if not google_auth.google_enabled():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, GOOGLE_UNAVAILABLE_DETAIL)
    try:
        claims = await google_auth.verify_with_nonce(session, token)
    except google_auth.GoogleSignInRefused as exc:
        await session.commit()
        detail = GOOGLE_UNVERIFIED_DETAIL if exc.reason == "email_unverified" else GOOGLE_FAILED_DETAIL
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail) from exc
    await session.commit()
    mailbox = VerifiedMailbox(
        email=str(claims["email"]).strip().lower(),
        display_name=claims.get("name"),
        avatar_url=claims.get("picture"),
        provider=GOOGLE_PROVIDER,
    )
    return await sign_in_verified_mailbox(session, mailbox)


def _refuse_when_ip_throttled(request: Request) -> None:
    refuse_when_throttled(sign_in_attempt_by_ip(request), THROTTLED_DETAIL)


def code_grant(payload: OidcCodeFields) -> oidc_sign_in.CodeGrant:
    return oidc_sign_in.CodeGrant(
        provider=payload.oidcProvider or "",
        code=payload.oidcCode or "",
        code_verifier=payload.oidcCodeVerifier or "",
        redirect_uri=payload.oidcRedirectUri or "",
        raw_nonce=payload.oidcNonce or "",
    )


async def _prove_with_provider(
    session: AsyncSession, payload: LoginRequest, label: str
) -> oidc_sign_in.ProvedIdentity:
    name = payload.oidcProvider or ""
    try:
        return await oidc_sign_in.prove_once(session, code_grant(payload), purpose=oidc_sign_in.NONCE_PURPOSE)
    except oidc_sign_in.EmailNotVerified as exc:
        logger.info("oidc sign-in refused", extra={"provider": name, "reason": exc.reason})
        detail = PROVIDER_UNVERIFIED_DETAIL.format(label=label)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail) from exc
    except oidc_sign_in.SignInRefused as exc:
        logger.info("oidc sign-in refused", extra={"provider": name, "reason": exc.reason})
        detail = PROVIDER_FAILED_DETAIL.format(label=label)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail) from exc


async def login_with_oidc(session: AsyncSession, payload: LoginRequest, request: Request) -> tuple[User, Any]:
    name = payload.oidcProvider or ""
    label = oidc_sign_in.label_of(name)
    if oidc_sign_in.provider(name) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, PROVIDER_UNAVAILABLE_DETAIL.format(label=label))
    _refuse_when_ip_throttled(request)
    proved = await _prove_with_provider(session, payload, label)
    refund_ip(request)
    mailbox = VerifiedMailbox(
        email=proved.email, display_name=proved.name, avatar_url=None, provider=proved.provider
    )
    return await sign_in_verified_mailbox(session, mailbox)


async def login_with_password(
    session: AsyncSession, payload: LoginRequest, request: Request
) -> tuple[User, Any]:
    email = (payload.email or "").strip().lower()
    user = await _find_user(session, email)
    if user is not None and user.passwordHash is None and user.deletedAt is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            PASSWORD_NOT_SET_DETAIL.format(label=_sign_in_label(user)),
            {SIGN_IN_HINT_HEADER: PASSWORD_NOT_SET_HINT},
        )
    account_key = str(user.id) if user is not None else f"addr:{email}"
    allowed, retry = sign_in_attempt_by_ip(request)
    if allowed:
        allowed, retry = sign_in_attempt_by_account(account_key)
    refuse_when_throttled((allowed, retry), THROTTLED_DETAIL)
    matched = await asyncio.to_thread(
        verify_password_or_decoy, payload.password or "", user.passwordHash if user else None
    )
    if not matched or user is None or user.deletedAt is not None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, INVALID_CREDENTIALS_DETAIL)
    if (
        user.emailVerifiedAt is None
        and not user.passwordIssuerKnown
        and user.firstLoginAt is None
        and not is_break_glass_master(user)
    ):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            EMAIL_UNVERIFIED_DETAIL,
            {SIGN_IN_HINT_HEADER: EMAIL_UNVERIFIED_HINT},
        )
    refund_account(account_key)
    refund_ip(request)
    access = await assert_access_admits(session, user.email, is_master=is_break_glass_master(user))
    return user, access


@router.post("/google/nonce")
async def google_nonce(request: Request, session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    if not google_auth.google_enabled():
        raise HTTPException(status.HTTP_404_NOT_FOUND, GOOGLE_UNAVAILABLE_DETAIL)
    _refuse_when_ip_throttled(request)
    refund_ip(request)
    nonce, expires = await auth_nonces.issue_nonce(
        session, purpose="GOOGLE_SIGN_IN", ip_hash=ip_hash(client_ip(request))
    )
    return {"nonce": nonce, "expiresAt": expires.isoformat(), "clientId": get_settings().google_client_id}


@router.post("/oidc/nonce")
async def oidc_nonce(
    payload: OidcNonceRequest, request: Request, session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    client_id = oidc_sign_in.client_id_if_enabled(payload.provider)
    if client_id is None:
        label = oidc_sign_in.label_of(payload.provider)
        raise HTTPException(status.HTTP_404_NOT_FOUND, PROVIDER_UNAVAILABLE_DETAIL.format(label=label))
    _refuse_when_ip_throttled(request)
    refund_ip(request)
    nonce, expires = await auth_nonces.issue_nonce(
        session, purpose=oidc_sign_in.NONCE_PURPOSE, ip_hash=ip_hash(client_ip(request))
    )
    return {"nonce": nonce, "expiresAt": expires.isoformat(), "clientId": client_id}


@router.get("/config")
async def auth_config() -> dict[str, Any]:
    microsoft_client_id = oidc_sign_in.client_id_if_enabled(oidc_sign_in.MICROSOFT)
    yahoo_client_id = oidc_sign_in.client_id_if_enabled(oidc_sign_in.YAHOO)
    return {
        "googleEnabled": google_auth.google_enabled(),
        "googleClientId": get_settings().google_client_id if google_auth.google_enabled() else None,
        "microsoftEnabled": microsoft_client_id is not None,
        "microsoftClientId": microsoft_client_id,
        "yahooEnabled": yahoo_client_id is not None,
        "yahooClientId": yahoo_client_id,
        "turnstileRequired": turnstile.turnstile_enabled(),
        "turnstileSiteKey": turnstile.site_key(),
        "mailAvailable": mailer.mail_configured(),
        "signUpOpen": mailer.mail_configured() and not turnstile.required_but_missing(),
    }


@router.post("/login")
async def login(
    payload: LoginRequest, request: Request, session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    if payload.googleIdToken:
        user, access = await login_with_google(session, payload.googleIdToken)
    elif payload.has_oidc_code:
        user, access = await login_with_oidc(session, payload, request)
    else:
        user, access = await login_with_password(session, payload, request)
    await session.commit()
    if user.twoFactorEnabled:
        if two_factor.fully_locked(user):
            raise too_many_requests(two_factor.TOO_MANY_ATTEMPTS_DETAIL)
        return {
            "two_factor_required": True,
            "challenge_token": await two_factor.issue_challenge(session, user),
        }
    return await open_session(session, user, access)


SIGNUP_CLOSED_DETAIL = "Request access with Google instead."
SIGNUP_ROLE_LABELS = {
    "STUDENT": "Student",
    "ARTISAN": "Artisan",
    "RESEARCHER": "Researcher",
    "PROFESSOR": "Professor",
}


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


@router.post("/signup", status_code=status.HTTP_202_ACCEPTED)
async def signup(
    payload: SignUpRequest,
    request: Request,
    background: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    refuse_when_throttled(sign_in_attempt_by_ip(request), THROTTLED_DETAIL)
    if turnstile.required_but_missing() or not mailer.mail_configured():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, SIGNUP_CLOSED_DETAIL)
    if not await turnstile.verify(payload.turnstileToken, client_ip(request)):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The human check did not pass. Try again.")
    if not payload.ageAttested:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "Confirm you are old enough to use KalaVigyan."
        )
    email = str(payload.email).strip().lower()
    if email == get_settings().master_admin_email.strip().lower():
        return _signup_answer(email)
    existing = await _find_user(session, email)
    if existing is not None:
        if existing.deletedAt is None and existing.emailVerifiedAt is None and existing.passwordHash is None:
            background.add_task(_send_signup_link, email, existing.id)
        return _signup_answer(email)
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
    await session.commit()
    background.add_task(_send_signup_link, email, user.id)
    return _signup_answer(email)


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


@router.post("/logout")
async def logout() -> dict[str, bool]:
    return {"ok": True}


@router.get("/me")
async def me(
    user: User = Depends(get_current_user_any_step), session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    row = await access_roster.access_row(session, user.email)
    access = "ACTIVE" if is_break_glass_master(user) else (access_roster.status_of(row) or "ACTIVE")
    body = serialize_user(user, access_status=access)
    body["profileRequired"] = await reader_profiles.profile_required(session, user)
    body["guardianConsentRequired"] = await reader_profiles.guardian_consent_required(session, user)
    return body


@router.post("/consent")
async def record_consent(
    payload: ConsentRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    now = datetime.now(UTC)
    session.add(
        ConsentRecord(userId=user.id, kind=payload.kind, noticeVersion=payload.noticeVersion, acceptedAt=now)
    )
    await session.commit()
    return {"kind": payload.kind, "noticeVersion": payload.noticeVersion, "acceptedAt": now.isoformat()}


@router.post("/google/link-nonce")
async def google_link_nonce(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    if not google_auth.google_enabled():
        raise HTTPException(status.HTTP_404_NOT_FOUND, GOOGLE_UNAVAILABLE_DETAIL)
    nonce, expires = await auth_nonces.issue_nonce(session, purpose="GOOGLE_LINK", user_id=user.id)
    return {"nonce": nonce, "expiresAt": expires.isoformat(), "clientId": get_settings().google_client_id}


@router.post("/google/link")
async def google_link(
    payload: GoogleLinkRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    fresh = False
    if payload.twoFactorCode and user.twoFactorEnabled:
        fresh = await two_factor.step_up(session, user, payload.twoFactorCode)
    elif payload.password and user.passwordHash:
        fresh = await asyncio.to_thread(verify_password, payload.password, user.passwordHash)
    if not fresh:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Confirm it's you with your password or a code first.",
            {TWO_FACTOR_REQUIRED_HEADER: "1"} if user.twoFactorEnabled else None,
        )
    try:
        claims = await google_auth.verify_with_nonce(
            session, payload.googleIdToken, purpose="GOOGLE_LINK", user_id=user.id
        )
    except google_auth.GoogleSignInRefused as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, GOOGLE_FAILED_DETAIL) from exc
    if str(claims["email"]).strip().lower() != user.email.strip().lower():
        raise HTTPException(status.HTTP_409_CONFLICT, "That Google account uses a different email address.")
    user.avatarUrl = claims.get("picture") or user.avatarUrl
    user.emailVerifiedAt = user.emailVerifiedAt or datetime.now(UTC)
    await audit.record(
        session, action="auth.google_linked", actor=user, target_type="User", target_id=user.id
    )
    await session.commit()
    return serialize_user(await reload_user(session, user.id))


@router.post("/password-links", status_code=status.HTTP_201_CREATED)
async def issue_password_link(
    payload: IssuePasswordLinkRequest,
    actor: User = Depends(require(Capability.MANAGE_ACCESS)),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    try:
        target_id = uuid.UUID(payload.userId)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found") from exc
    target = await session.get(User, target_id)
    if target is None or target.deletedAt is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if target.id == actor.id or not may_manage_target(actor, target) or is_configured_master_admin(target):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can't issue a password link for this account.")
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
    delivered = "COPY_LINK"
    if payload.delivery == "EMAIL":
        minutes = credential_links.minutes_for(purpose)
        mail = (mailer.invite_link_mail if purpose == "INVITE" else mailer.reset_link_mail)(
            target.email, issued.link, minutes
        )
        if await mailer.send(mail):
            delivered = "EMAIL"
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
    from app.models import PasswordResetToken

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


async def _link_check(session: AsyncSession, raw: str | None) -> dict[str, Any]:
    verdict = await credential_links.describe_token(session, raw)
    return {"valid": verdict.ok, "reason": verdict.reason, "purpose": verdict.purpose}


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
        await _adopt_admitted_role(session, account, await access_roster.access_row(session, account.email))
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


async def _request_password_reset(email: str, ip: str | None, user_agent: str | None) -> None:
    async with session_scope() as session:
        account = await _find_user(session, email)
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


@router.post("/forgot-password")
async def forgot_password(
    payload: ForgotPasswordRequest, request: Request, response: Response, background: BackgroundTasks
) -> dict[str, str]:
    refuse_when_throttled(forgot_password_attempt(request), RESETS_SPENT_DETAIL)
    background.add_task(
        _request_password_reset,
        str(payload.email).strip().lower(),
        ip_hash(client_ip(request)),
        request.headers.get("user-agent"),
    )
    response.headers["Cache-Control"] = "no-store"
    return {"message": FORGOT_PASSWORD_MESSAGE}
