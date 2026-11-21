from dataclasses import dataclass
from typing import Annotated, Any, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.document_reads import (
    WHOLE_DOCUMENT,
    AskedPart,
    AskedTag,
    PartAsk,
    ServedDocument,
    document_response,
    generated_in_language,
    queue_rebuild,
)
from app.api.public_deps import cached_read, public_reader
from app.core.db import get_session
from app.core.deps import get_current_user
from app.core.errors import InvalidInput, Refused
from app.core.roles import ADMIN, has_rank
from app.models import User
from app.research.crafts import SLUG_MAX_CHARS
from app.research.monograph_document import LANGUAGE_MAX_CHARS, SUBJECT_KINDS, served_language
from app.research.page_layout import LayoutWrite
from app.services.page_layouts import page_layout, write_layout
from app.services.stored_documents import generated_read

router = APIRouter(tags=["page documents"])

ADMIN_ONLY_DETAIL = "Changing a page's layout is for admins."
NO_DOCUMENT_DETAIL = "There is no monograph for that {kind} yet."
NO_LAYOUT_DETAIL = "That page has no layout yet."
CATEGORY, FAMILY = "category", "family"

SubjectKind = Literal[*SUBJECT_KINDS]
Slug = Annotated[str, Path(min_length=1, max_length=SLUG_MAX_CHARS, pattern=r"^[A-Za-z0-9-]+$")]
AskedLanguage = Annotated[str | None, Query(alias="lang", max_length=LANGUAGE_MAX_CHARS)]


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


@dataclass(frozen=True)
class AskedDocument:
    slug: str
    language: str
    part: PartAsk = WHOLE_DOCUMENT


def asked_document(
    slug: Slug, lang: AskedLanguage = None, part: AskedPart = None, tag: AskedTag = None
) -> AskedDocument:
    return AskedDocument(slug, served_language(lang), PartAsk(part, tag))


@router.get("/categories/{slug}/monograph")
async def get_category_monograph(
    request: Request,
    background: BackgroundTasks,
    asked: AskedDocument = Depends(asked_document),
    reader: User | None = Depends(public_reader),
    session: AsyncSession = Depends(get_session),
) -> Response:
    served = await _document(session, CATEGORY, asked)
    queue_rebuild(background, served)
    return document_response(request, reader, served, asked.part)


@router.get("/families/{slug}/monograph")
async def get_family_monograph(
    request: Request,
    background: BackgroundTasks,
    asked: AskedDocument = Depends(asked_document),
    reader: User | None = Depends(public_reader),
    session: AsyncSession = Depends(get_session),
) -> Response:
    served = await _document(session, FAMILY, asked)
    queue_rebuild(background, served)
    return document_response(request, reader, served, asked.part)


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


async def _document(session: AsyncSession, kind: str, asked: AskedDocument) -> ServedDocument:
    try:
        read = await generated_read(session, kind, asked.slug)
    except InvalidInput as unknown:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(unknown)) from unknown
    served = await generated_in_language(session, read, language=asked.language)
    if served is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NO_DOCUMENT_DETAIL.format(kind=kind))
    return served
