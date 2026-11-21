from typing import Any

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.public_deps import cached_read, public_reader
from app.core.config import get_settings
from app.core.db import get_session
from app.models import User
from app.services.open_data_listing import open_data_listing

router = APIRouter(prefix="/open-data", tags=["open-data"])


@router.get("")
async def get_open_data(
    request: Request,
    response: Response,
    reader: User | None = Depends(public_reader),
    session: AsyncSession = Depends(get_session),
) -> Any:
    listing = await open_data_listing(session, site=get_settings().public_web_url)
    return cached_read(request, response, reader, listing.model_dump(mode="json", by_alias=True))
