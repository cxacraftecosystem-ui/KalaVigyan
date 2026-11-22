from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.public_deps import cached_read, public_reader
from app.core.db import get_session
from app.core.deps import get_current_user
from app.core.errors import InvalidInput
from app.core.roles import ADMIN, has_rank
from app.models import User
from app.research.coverage import FieldCoverage
from app.research.crafts import SLUG_MAX_CHARS
from app.services import knowledge_view
from app.services.coverage import category_coverage, craft_coverage, monograph_coverage
from app.services.upkeep_hidden import last_hidden_facts

router = APIRouter(tags=["coverage"])

CRAFT_NOT_FOUND_DETAIL = "No craft has that address."
CATEGORY_NOT_FOUND_DETAIL = "There is no craft category by that name."
HIDDEN_FACTS_DETAIL = "The count of facts readers cannot see is for admins."


@router.get("/crafts/coverage")
async def get_monograph_coverage(
    request: Request,
    response: Response,
    reader: User | None = Depends(public_reader),
    session: AsyncSession = Depends(get_session),
) -> Any:
    coverage = await monograph_coverage(session)
    return cached_read(request, response, reader, coverage.model_dump(mode="json", by_alias=True))


@router.get("/crafts/{slug}/coverage")
async def get_craft_coverage(
    request: Request,
    response: Response,
    slug: str = Path(min_length=1, max_length=SLUG_MAX_CHARS),
    reader: User | None = Depends(public_reader),
    session: AsyncSession = Depends(get_session),
) -> Any:
    craft = await knowledge_view.resolve_craft(session, slug)
    if craft is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, CRAFT_NOT_FOUND_DETAIL)
    try:
        coverage = await craft_coverage(session, craft.slug)
    except InvalidInput as unknown:
        raise HTTPException(status.HTTP_404_NOT_FOUND, CRAFT_NOT_FOUND_DETAIL) from unknown
    return _served(request, response, reader, coverage)


@router.get("/categories/{slug}/coverage")
async def get_category_coverage(
    request: Request,
    response: Response,
    slug: str = Path(min_length=1, max_length=SLUG_MAX_CHARS),
    reader: User | None = Depends(public_reader),
    session: AsyncSession = Depends(get_session),
) -> Any:
    try:
        coverage = await category_coverage(session, slug)
    except InvalidInput as unknown:
        raise HTTPException(status.HTTP_404_NOT_FOUND, CATEGORY_NOT_FOUND_DETAIL) from unknown
    return _served(request, response, reader, coverage)


@router.get("/coverage/hidden-facts")
async def get_hidden_facts(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    if not has_rank(user, ADMIN):
        raise HTTPException(status.HTTP_403_FORBIDDEN, HIDDEN_FACTS_DETAIL)
    return {"report": await last_hidden_facts(session)}


def _served(request: Request, response: Response, reader: User | None, coverage: FieldCoverage) -> Any:
    return cached_read(request, response, reader, coverage.model_dump(mode="json", by_alias=True))
