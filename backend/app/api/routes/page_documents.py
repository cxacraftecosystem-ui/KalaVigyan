from dataclasses import dataclass
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.public_deps import cached_read, public_reader
from app.core.db import get_session
from app.core.deps import get_current_user
from app.core.errors import InvalidInput, Refused
from app.core.roles import ADMIN, has_rank
from app.models import User
from app.research.crafts import SLUG_MAX_CHARS
from app.research.monograph_document import SUBJECT_KINDS
from app.research.page_layout import LayoutWrite
from app.services.monograph_generated import generated_document
from app.services.open_work_subjects import subject_by_key
from app.services.page_layouts import page_layout, write_layout

router = APIRouter(tags=["page documents"])

ADMIN_ONLY_DETAIL = "Changing a page's layout is for admins."
NO_DOCUMENT_DETAIL = "There is no monograph for that {kind} yet."
NO_LAYOUT_DETAIL = "That page has no layout yet."
CATEGORY, FAMILY = "category", "family"
CONTENT_LANGUAGE = "Content-Language"

SubjectKind = Literal[*SUBJECT_KINDS]
Slug = Annotated[str, Path(min_length=1, max_length=SLUG_MAX_CHARS, pattern=r"^[A-Za-z0-9-]+$")]


@dataclass(frozen=True)
class PageRef:
    kind: str
    slug: str


async def layout_admin(user: User = Depends(get_current_user)) -> User:
    if not has_rank(user, ADMIN):
        raise HTTPException(status.HTTP_403_FORBIDDEN, ADMIN_ONLY_DETAIL)
    return user


def page_ref(kind: SubjectKind, slug: Slug) -> PageRef:
    return PageRef(kind, slug)


@router.get("/categories/{slug}/monograph")
async def get_category_monograph(
    request: Request,
    response: Response,
    slug: Slug,
    reader: User | None = Depends(public_reader),
    session: AsyncSession = Depends(get_session),
) -> Any:
    return _served(request, response, reader, await _document(session, CATEGORY, slug))


@router.get("/families/{slug}/monograph")
async def get_family_monograph(
    request: Request,
    response: Response,
    slug: Slug,
    reader: User | None = Depends(public_reader),
    session: AsyncSession = Depends(get_session),
) -> Any:
    return _served(request, response, reader, await _document(session, FAMILY, slug))


@router.get("/pages/{kind}/{slug}/layout")
async def get_page_layout(
    request: Request,
    response: Response,
    page: PageRef = Depends(page_ref),
    reader: User | None = Depends(public_reader),
    session: AsyncSession = Depends(get_session),
) -> Any:
    try:
        layout = await page_layout(session, page.kind, page.slug)
    except InvalidInput as unknown:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(unknown)) from unknown
    if layout is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NO_LAYOUT_DETAIL)
    return cached_read(request, response, reader, layout.model_dump(mode="json", by_alias=True))


@router.put("/pages/{kind}/{slug}/layout")
async def put_page_layout(
    written: LayoutWrite,
    user: User = Depends(layout_admin),
    page: PageRef = Depends(page_ref),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    try:
        layout = await write_layout(session, page.kind, page.slug, written, actor=user)
    except InvalidInput as unknown:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(unknown)) from unknown
    except Refused as stale:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, stale.message) from stale
    await session.commit()
    return layout.model_dump(mode="json", by_alias=True)


def _served(request: Request, response: Response, reader: User | None, body: dict[str, Any]) -> Any:
    response.headers[CONTENT_LANGUAGE] = body["language"]
    return cached_read(request, response, reader, body)


async def _document(session: AsyncSession, kind: str, slug: str) -> dict[str, Any]:
    try:
        await subject_by_key(session, kind, slug)
    except InvalidInput as unknown:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(unknown)) from unknown
    document = await generated_document(session, kind, slug)
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NO_DOCUMENT_DETAIL.format(kind=kind))
    return document.model_dump(mode="json", by_alias=True)
