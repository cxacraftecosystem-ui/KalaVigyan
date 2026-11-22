from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.public_deps import cached_read, public_reader
from app.core.config import get_settings
from app.core.db import get_session
from app.core.deps import get_current_user
from app.core.errors import ExternalFailure, NotConfigured
from app.core.roles import ADMIN, has_rank
from app.core.throttle_refusal import too_many_requests
from app.models import User
from app.services.site_build import (
    BuildTooSoon,
    SiteBuildHook,
    deploy_hook,
    refuse_early_build,
    site_build_state,
    trigger_site_build,
)
from app.services.static_pages import static_pages

router = APIRouter(prefix="/site", tags=["site"])

ADMIN_ONLY_DETAIL = "Starting a site build is for admins."
NOT_CONFIGURED_DETAIL = "The site build is not set up on the server yet. The owner sets its deploy hook."
HOOK_FAILED_DETAIL = "The build service did not take the request. Try again in a few minutes."
ADMIN_ORIGIN = "admin"


async def site_admin(user: User = Depends(get_current_user)) -> User:
    if not has_rank(user, ADMIN):
        raise HTTPException(status.HTTP_403_FORBIDDEN, ADMIN_ONLY_DETAIL)
    return user


async def site_build_hook() -> AsyncIterator[SiteBuildHook | None]:
    async with httpx.AsyncClient(follow_redirects=False) as client:
        yield deploy_hook(get_settings().vercel_deploy_hook_url, client)


@router.get("/pages")
async def get_static_pages(
    request: Request,
    response: Response,
    reader: User | None = Depends(public_reader),
    session: AsyncSession = Depends(get_session),
) -> Any:
    listing = await static_pages(session)
    return cached_read(request, response, reader, listing.as_dict())


@router.get("/build")
async def get_site_build(
    _: User = Depends(site_admin), session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    configured = bool((get_settings().vercel_deploy_hook_url or "").strip())
    return (await site_build_state(session, configured=configured, now=datetime.now(UTC))).as_dict()


@router.post("/build", status_code=status.HTTP_202_ACCEPTED)
async def post_site_build(
    user: User = Depends(site_admin),
    session: AsyncSession = Depends(get_session),
    hook: SiteBuildHook | None = Depends(site_build_hook),
) -> dict[str, Any]:
    try:
        await refuse_early_build(session, now=datetime.now(UTC))
        await trigger_site_build(session, hook, actor=user, origin=ADMIN_ORIGIN)
    except NotConfigured:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, NOT_CONFIGURED_DETAIL) from None
    except BuildTooSoon as early:
        raise too_many_requests(early.message, early.retry_after) from None
    except ExternalFailure:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, HOOK_FAILED_DETAIL) from None
    return (await site_build_state(session, configured=True, now=datetime.now(UTC))).as_dict()
