import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.auth import (
    SESSION_TOKEN_HEADER,
    assert_access_admits,
    open_session,
    reload_user,
    session_token,
)
from app.core.db import get_session
from app.core.deps import get_current_user_any_step, is_break_glass_master
from app.core.rate_limit import code_attempt, refund_code
from app.core.throttle_refusal import refuse_when_throttled, too_many_requests
from app.models import User
from app.schemas.auth import TwoFactorCodeRequest, TwoFactorVerifyRequest
from app.services import audit, two_factor

router = APIRouter(prefix="/auth/two-factor", tags=["auth"])
logger = logging.getLogger(__name__)

CODE_THROTTLED_DETAIL = "Too many codes were tried. Wait a few minutes, then try again."

_STATUS = {
    "invalid": status.HTTP_400_BAD_REQUEST,
    "conflict": status.HTTP_409_CONFLICT,
    "dead": status.HTTP_401_UNAUTHORIZED,
    "locked": status.HTTP_429_TOO_MANY_REQUESTS,
}


def _refuse(error: two_factor.TwoFactorError) -> HTTPException:
    return HTTPException(status_code=_STATUS[error.kind], detail=error.detail)


async def _spend_budget(user_id: str) -> None:
    refuse_when_throttled(await code_attempt(user_id), CODE_THROTTLED_DETAIL)


@router.get("")
async def two_factor_status(
    user: User = Depends(get_current_user_any_step), session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    if not user.twoFactorEnabled and user.twoFactorPendingSecret and not two_factor.pending_is_live(user):
        await two_factor.clear_pending(session, user.id)
        await session.commit()
        user = await reload_user(session, user.id)
    return two_factor.status_of(user)


@router.post("/setup/cancel", status_code=status.HTTP_204_NO_CONTENT)
async def two_factor_setup_cancel(
    user: User = Depends(get_current_user_any_step), session: AsyncSession = Depends(get_session)
) -> Response:
    await two_factor.clear_pending(session, user.id)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/setup")
async def two_factor_setup(
    user: User = Depends(get_current_user_any_step), session: AsyncSession = Depends(get_session)
) -> dict[str, str]:
    try:
        return await two_factor.begin_setup(session, user)
    except two_factor.TwoFactorError as error:
        raise _refuse(error) from error


@router.post("/enable")
async def two_factor_enable(
    payload: TwoFactorCodeRequest,
    response: Response,
    user: User = Depends(get_current_user_any_step),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    await _spend_budget(str(user.id))
    try:
        codes = await two_factor.enable(session, user, payload.code)
    except two_factor.TwoFactorError as error:
        raise _refuse(error) from error
    await refund_code(str(user.id))
    fresh = await reload_user(session, user.id)
    await audit.record(
        session, action="auth.two_factor_enabled", actor=fresh, target_type="User", target_id=fresh.id
    )
    await session.commit()
    token = session_token(fresh)
    response.headers[SESSION_TOKEN_HEADER] = token
    return {"recovery_codes": codes, "accessToken": token}


@router.post("/disable", status_code=status.HTTP_200_OK)
async def two_factor_disable(
    payload: TwoFactorCodeRequest,
    response: Response,
    user: User = Depends(get_current_user_any_step),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    await _spend_budget(str(user.id))
    try:
        await two_factor.disable(session, user, payload.code)
    except two_factor.TwoFactorError as error:
        raise _refuse(error) from error
    await refund_code(str(user.id))
    fresh = await reload_user(session, user.id)
    await audit.record(
        session, action="auth.two_factor_disabled", actor=fresh, target_type="User", target_id=fresh.id
    )
    await session.commit()
    token = session_token(fresh)
    response.headers[SESSION_TOKEN_HEADER] = token
    return {"ok": True, "accessToken": token}


@router.post("/recovery-codes")
async def two_factor_recovery_codes(
    payload: TwoFactorCodeRequest,
    user: User = Depends(get_current_user_any_step),
    session: AsyncSession = Depends(get_session),
) -> dict[str, list[str]]:
    await _spend_budget(str(user.id))
    try:
        codes = await two_factor.regenerate_recovery_codes(session, user, payload.code)
    except two_factor.TwoFactorError as error:
        raise _refuse(error) from error
    await refund_code(str(user.id))
    return {"recovery_codes": codes}


@router.post("/verify")
async def two_factor_verify(
    payload: TwoFactorVerifyRequest, session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    try:
        challenge = two_factor.read_challenge(payload.challenge_token)
    except two_factor.TwoFactorError as error:
        raise _refuse(error) from error
    dead = HTTPException(status.HTTP_401_UNAUTHORIZED, two_factor.CHALLENGE_DEAD_DETAIL)
    await _spend_budget(str(challenge.user_id))
    if not await two_factor.spend_challenge_attempt(session, challenge):
        raise dead
    user = await session.get(User, challenge.user_id)
    if user is None or not user.twoFactorEnabled or user.deletedAt is not None:
        raise dead
    try:
        accepted = await two_factor.check_second_factor(session, user, payload.code)
    except two_factor.SecondFactorLocked as locked:
        raise too_many_requests(two_factor.TOO_MANY_ATTEMPTS_DETAIL) from locked
    if not accepted:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, two_factor.WRONG_CODE_DETAIL)
    await refund_code(str(user.id))
    if not await two_factor.close_challenge(session, challenge):
        raise dead
    await session.commit()
    user = await reload_user(session, user.id)
    access = await assert_access_admits(session, user.email, is_master=is_break_glass_master(user))
    return await open_session(session, user, access)
