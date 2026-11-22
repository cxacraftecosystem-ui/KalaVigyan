from __future__ import annotations

from dataclasses import replace
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.export_deps import (
    citation_export,
    citation_file_response,
    explainer_pdf,
    export_tools,
    lesson_file,
)
from app.api.public_deps import READER_VARY, cached_read, public_reader, reader_cache
from app.core.db import get_session
from app.core.http_cache import PRIVATE_NO_CACHE
from app.models import User
from app.research.citation_export import CITATION_FORMATS
from app.research.explainer_versions import ExplainerVersionDocument
from app.research.lessons import LESSON_FORMATS, LessonPack
from app.research.share_links import SHARE_TOKEN_PATTERN
from app.services.export_files import ExportTools
from app.services.share_links import shared_answer, shared_lesson
from app.services.shared_files import SHARED_EXPORT_OWNER, SignedKeys, record_shared_files

router = APIRouter(prefix="/shared", tags=["shared"])

NO_SHARE_DETAIL = "Nothing is shared at that address. Its owner may have stopped sharing it."

ShareToken = Annotated[str, Path(pattern=SHARE_TOKEN_PATTERN)]
CitationFormat = Literal[*CITATION_FORMATS]
LessonFormat = Literal[*LESSON_FORMATS]


@router.get("/answers/{token}")
async def get_shared_answer(
    token: ShareToken,
    request: Request,
    response: Response,
    reader: User | None = Depends(public_reader),
    session: AsyncSession = Depends(get_session),
) -> Any:
    document = await _shared_answer(session, token)
    return cached_read(request, response, reader, document.model_dump(mode="json", by_alias=True))


@router.get("/answers/{token}/citations")
async def get_shared_citations(
    token: ShareToken,
    request: Request,
    response: Response,
    reader: User | None = Depends(public_reader),
    session: AsyncSession = Depends(get_session),
) -> Any:
    export = await citation_export(session, await _shared_answer(session, token))
    return cached_read(request, response, reader, export.model_dump(mode="json", by_alias=True))


@router.get("/answers/{token}/citations/{fmt}")
async def get_shared_citation_file(
    token: ShareToken,
    fmt: CitationFormat,
    reader: User | None = Depends(public_reader),
    session: AsyncSession = Depends(get_session),
) -> Response:
    document = await _shared_answer(session, token)
    export = await citation_export(session, document)
    headers = {"Cache-Control": reader_cache(reader), "Vary": READER_VARY}
    return citation_file_response(document, export, fmt, headers)


@router.get("/answers/{token}/pdf")
async def get_shared_pdf(
    token: ShareToken,
    response: Response,
    *,
    reader: User | None = Depends(public_reader),
    session: AsyncSession = Depends(get_session),
    tools: ExportTools = Depends(export_tools),
) -> dict[str, Any]:
    document = await _shared_answer(session, token)
    signed = SignedKeys(tools.objects)
    link = await explainer_pdf(session, replace(tools, objects=signed), SHARED_EXPORT_OWNER, document)
    await record_shared_files(session, token, signed.keys, objects=tools.objects)
    response.headers["Cache-Control"] = PRIVATE_NO_CACHE
    return link.model_dump(mode="json", by_alias=True)


@router.get("/lessons/{token}")
async def get_shared_lesson(
    token: ShareToken,
    request: Request,
    response: Response,
    reader: User | None = Depends(public_reader),
    session: AsyncSession = Depends(get_session),
) -> Any:
    pack = await _shared_lesson(session, token)
    return cached_read(request, response, reader, pack.model_dump(mode="json", by_alias=True))


@router.get("/lessons/{token}/files/{fmt}")
async def get_shared_lesson_file(
    token: ShareToken,
    fmt: LessonFormat,
    response: Response,
    *,
    reader: User | None = Depends(public_reader),
    session: AsyncSession = Depends(get_session),
    tools: ExportTools = Depends(export_tools),
) -> dict[str, Any]:
    pack = await _shared_lesson(session, token)
    signed = SignedKeys(tools.objects)
    link = await lesson_file(session, replace(tools, objects=signed), SHARED_EXPORT_OWNER, pack, fmt)
    await record_shared_files(session, token, signed.keys, objects=tools.objects)
    response.headers["Cache-Control"] = PRIVATE_NO_CACHE
    return link.model_dump(mode="json", by_alias=True)


async def _shared_answer(session: AsyncSession, token: str) -> ExplainerVersionDocument:
    document = await shared_answer(session, token)
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NO_SHARE_DETAIL)
    return document


async def _shared_lesson(session: AsyncSession, token: str) -> LessonPack:
    pack = await shared_lesson(session, token)
    if pack is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NO_SHARE_DETAIL)
    return pack
