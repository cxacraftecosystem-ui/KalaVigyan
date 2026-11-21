from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.public_deps import cached_read, public_reader
from app.core.db import get_session
from app.models import User
from app.services import knowledge_view
from app.services.answering import NOT_FOUND_DETAIL
from app.services.place_ground import craft_ground_of, map_ground_at

router = APIRouter(tags=["ground"])

NO_PLACE_DETAIL = "This craft has no recorded place on the map to measure the ground at."
NOT_A_PLACE_DETAIL = "There is no craft place at that point on the map."
WEST, SOUTH, EAST, NORTH = 64.7, 5.3, 98.5, 37.9


@router.get("/crafts/{slug}/ground")
async def get_craft_ground(
    slug: str,
    request: Request,
    response: Response,
    reader: User | None = Depends(public_reader),
    session: AsyncSession = Depends(get_session),
) -> Any:
    craft = await knowledge_view.resolve_craft(session, slug)
    if craft is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND_DETAIL)
    ground = await craft_ground_of(session, craft)
    if ground is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NO_PLACE_DETAIL)
    return cached_read(request, response, reader, ground.model_dump(mode="json", by_alias=True))


@router.get("/map/ground")
async def get_map_ground(
    request: Request,
    response: Response,
    longitude: float = Query(ge=WEST, le=EAST),
    latitude: float = Query(ge=SOUTH, le=NORTH),
    reader: User | None = Depends(public_reader),
    session: AsyncSession = Depends(get_session),
) -> Any:
    ground = await map_ground_at(session, (longitude, latitude))
    if ground is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_A_PLACE_DETAIL)
    return cached_read(request, response, reader, ground.model_dump(mode="json", by_alias=True))
