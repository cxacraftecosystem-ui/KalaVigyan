from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import get_current_user, require_master_admin
from app.core.errors import InvalidInput
from app.core.http_cache import PRIVATE_NO_CACHE
from app.core.roles import ADMIN, has_rank
from app.models import User
from app.research.field_voices import ARTISAN_IMAGE_VISIBILITIES
from app.services import audit
from app.services.field_voices_held import held_image_list, held_photo_crafts, set_artisan_image_visibility
from app.services.page_revalidation import craft_owners, refresh_pages

router = APIRouter(prefix="/field-voices/held-images", tags=["field-voices"])

ADMINS_ONLY = "Held field images are for admins."
UNKNOWN_CURSOR = "Unknown cursor."

Visibility = Literal[*ARTISAN_IMAGE_VISIBILITIES]


class VisibilityUpdate(BaseModel):
    visibility: Visibility


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if not has_rank(user, ADMIN):
        raise HTTPException(status.HTTP_403_FORBIDDEN, ADMINS_ONLY)
    return user


@router.get("")
async def get_held_images(
    response: Response,
    cursor: str | None = None,
    *,
    _: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> Any:
    try:
        listed = await held_image_list(session, cursor=cursor)
    except InvalidInput:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, UNKNOWN_CURSOR) from None
    response.headers["Cache-Control"] = PRIVATE_NO_CACHE
    return listed.model_dump(mode="json", by_alias=True)


@router.put("/visibility")
async def put_held_image_visibility(
    body: VisibilityUpdate,
    response: Response,
    actor: User = Depends(require_master_admin),
    session: AsyncSession = Depends(get_session),
) -> Any:
    visibility = await set_artisan_image_visibility(session, body.visibility, actor_id=actor.id)
    await audit.record(
        session,
        action="field_voices.artisan_images",
        actor=actor,
        target_type="AppSetting",
        target_id="field_voices.artisan_images",
        detail={"visibility": visibility},
    )
    await session.commit()
    await refresh_pages(await craft_owners(session, await held_photo_crafts(session)))
    response.headers["Cache-Control"] = PRIVATE_NO_CACHE
    return {"visibility": visibility}
