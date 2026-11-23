import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.public_deps import cached_read, public_reader, read_headers, unchanged_read
from app.core.db import get_session
from app.core.deps import SIGN_IN_DETAIL, require
from app.core.errors import Refused
from app.core.kept_value import KeptValue
from app.core.roles import PROFESSOR, Capability, can, has_rank
from app.geo.region_view import craft_region
from app.models import Craft, User
from app.schemas.craft_page import PageHiding
from app.services import craft_catalogue, knowledge_view
from app.services.answering import NOT_FOUND_DETAIL
from app.services.craft_page_cache import PageCache, ServedPage
from app.services.craft_page_hiding import SIMULATION, set_page_media_hidden, set_page_piece_hidden
from app.services.craft_page_snapshots import OPEN, RESEARCHER, served_page
from app.services.region_records import region_records

router = APIRouter(prefix="/crafts", tags=["crafts"])

INACTIVE_REFUSAL = "The full craft list, with retired crafts, is for professors and above."
NOT_ON_PAGE_DETAIL = "That piece is not on this craft's page."
JSON_TYPE = "application/json"


def catalogue_cache(request: Request) -> KeptValue[dict[str, Any]]:
    kept: KeptValue[dict[str, Any]] = request.app.state.craft_catalogue
    return kept


@router.get("/catalogue")
async def get_craft_catalogue(
    request: Request,
    response: Response,
    includeInactive: bool = False,
    *,
    reader: User | None = Depends(public_reader),
    session: AsyncSession = Depends(get_session),
    kept: KeptValue[dict[str, Any]] = Depends(catalogue_cache),
) -> Any:
    if includeInactive and reader is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, SIGN_IN_DETAIL)
    if includeInactive and not has_rank(reader, PROFESSOR):
        raise HTTPException(status.HTTP_403_FORBIDDEN, INACTIVE_REFUSAL)
    if includeInactive:
        catalogue = await craft_catalogue.load_catalogue(session, include_inactive=True)
    else:
        catalogue = await craft_catalogue.reader_catalogue(session, kept)
    return cached_read(request, response, reader, catalogue, version=catalogue["version"])


@router.get("/{slug}/page")
async def get_craft_page(
    slug: str,
    request: Request,
    *,
    reader: User | None = Depends(public_reader),
    session: AsyncSession = Depends(get_session),
) -> Any:
    craft = await _known_craft(session, slug)
    served = await served_page(session, craft, page_variant(reader), cache=page_cache(request))
    return page_response(request, reader, served)


@router.put("/{slug}/explainers/{piece_id}/hidden")
async def put_explainer_hidden(
    slug: str,
    piece_id: uuid.UUID,
    body: PageHiding,
    *,
    user: User = Depends(require(Capability.HIDE_GENERATED)),
    session: AsyncSession = Depends(get_session),
) -> dict[str, bool]:
    craft = await _known_craft(session, slug)
    marked = await set_page_piece_hidden(
        session, craft, piece_id, hidden=body.hidden, user=user, now=datetime.now(UTC), kind=SIMULATION
    )
    return _hidden(marked)


@router.put("/{slug}/pieces/{piece_id}/hidden")
async def put_piece_hidden(
    slug: str,
    piece_id: uuid.UUID,
    body: PageHiding,
    *,
    user: User = Depends(require(Capability.HIDE_GENERATED)),
    session: AsyncSession = Depends(get_session),
) -> dict[str, bool]:
    craft = await _known_craft(session, slug)
    marked = await set_page_piece_hidden(
        session, craft, piece_id, hidden=body.hidden, user=user, now=datetime.now(UTC)
    )
    return _hidden(marked)


@router.put("/{slug}/media/{asset_id}/hidden")
async def put_media_hidden(
    slug: str,
    asset_id: uuid.UUID,
    body: PageHiding,
    *,
    user: User = Depends(require(Capability.HIDE_GENERATED)),
    session: AsyncSession = Depends(get_session),
) -> dict[str, bool]:
    craft = await _known_craft(session, slug)
    try:
        marked = await set_page_media_hidden(session, craft, asset_id, hidden=body.hidden, user=user)
    except Refused as refused:
        raise HTTPException(status.HTTP_403_FORBIDDEN, refused.message) from refused
    return _hidden(marked)


@router.get("/{slug}/region")
async def get_craft_region(
    slug: str,
    request: Request,
    response: Response,
    reader: User | None = Depends(public_reader),
    session: AsyncSession = Depends(get_session),
) -> Any:
    region = craft_region(await region_records(session, await _known_craft(session, slug)))
    return cached_read(request, response, reader, region.model_dump(mode="json", by_alias=True))


def page_cache(request: Request) -> PageCache | None:
    kept: PageCache | None = getattr(request.app.state, "craft_pages", None)
    return kept


def page_response(request: Request, reader: User | None, served: ServedPage) -> Response:
    unchanged = unchanged_read(request, reader, served.etag)
    if unchanged is not None:
        return unchanged
    return Response(served.content, media_type=JSON_TYPE, headers=read_headers(reader, served.etag))


def page_variant(reader: User | None) -> str:
    if reader is not None and can(reader, Capability.READ_RESEARCHER_QUOTES):
        return RESEARCHER
    return OPEN


def _hidden(marked: bool | None) -> dict[str, bool]:
    if marked is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_ON_PAGE_DETAIL)
    return {"hidden": marked}


async def _known_craft(session: AsyncSession, slug: str) -> Craft:
    craft = await knowledge_view.resolve_craft(session, slug)
    if craft is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND_DETAIL)
    return craft
