from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator

from fastapi import HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import release_connection
from app.core.errors import ExternalFailure, NotConfigured
from app.research.citation_export import CitationExport
from app.research.citation_formats import citation_file
from app.research.explainer_versions import ExplainerVersionDocument
from app.research.export_links import ExportLink
from app.research.lessons import LessonPack
from app.services.apa_references import apa_references
from app.services.citation_dates import accessed_dates
from app.services.export_files import (
    ExportTools,
    explainer_citations,
    explainer_cited,
    explainer_pdf_link,
    lesson_file_link,
    opened_export_tools,
)
from app.services.export_store import EXPORT_BUILDS_AT_ONCE
from app.services.naming import content_disposition, explainer_file_name
from app.services.object_store import media_bucket

__all__ = [
    "EXPORT_UNAVAILABLE_DETAIL",
    "citation_export",
    "citation_file_response",
    "explainer_pdf",
    "export_tools",
    "lesson_file",
]

EXPORT_UNAVAILABLE_DETAIL = "This file can't be made right now. Try again later."
CITATIONS_WHAT = "Citations"

logger = logging.getLogger(__name__)

_export_builds = asyncio.Semaphore(EXPORT_BUILDS_AT_ONCE)


async def export_tools() -> AsyncIterator[ExportTools]:
    objects = media_bucket()
    if objects is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, EXPORT_UNAVAILABLE_DETAIL)
    async with opened_export_tools(objects, _export_builds) as tools:
        yield tools


async def citation_export(session: AsyncSession, document: ExplainerVersionDocument) -> CitationExport:
    accessed = await accessed_dates(session, explainer_cited(document))
    await release_connection(session)
    return await asyncio.to_thread(explainer_citations, document, accessed, apa_references)


def citation_file_response(
    document: ExplainerVersionDocument, export: CitationExport, fmt: str, headers: dict[str, str]
) -> Response:
    written = citation_file(export, fmt)
    crafts = document.explainer.understood.crafts
    name = explainer_file_name(
        made_at=document.mark.created_at,
        craft=crafts[0].name if crafts else None,
        question=document.mark.question,
        version=document.mark.version,
        what=CITATIONS_WHAT,
        ext=written.extension,
    )
    return Response(
        written.text.encode("utf-8"),
        media_type=f"{written.media_type}; charset=utf-8",
        headers={**headers, "Content-Disposition": content_disposition(name, inline=False)},
    )


async def explainer_pdf(
    session: AsyncSession, tools: ExportTools, owner_id: uuid.UUID, document: ExplainerVersionDocument
) -> ExportLink:
    accessed = await accessed_dates(session, explainer_cited(document))
    await release_connection(session)
    try:
        return await explainer_pdf_link(tools, owner_id, document, accessed)
    except (ExternalFailure, NotConfigured) as error:
        logger.warning(
            "explainer %s v%s could not be filed as a PDF: %s",
            document.mark.explainer_id,
            document.mark.version,
            error,
        )
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, EXPORT_UNAVAILABLE_DETAIL) from None


async def lesson_file(
    session: AsyncSession, tools: ExportTools, owner_id: uuid.UUID, pack: LessonPack, fmt: str
) -> ExportLink:
    accessed = await accessed_dates(session, pack.sources)
    await release_connection(session)
    try:
        return await lesson_file_link(tools, owner_id, pack, accessed, fmt)
    except (ExternalFailure, NotConfigured) as error:
        logger.warning("lesson %s could not be filed as %s: %s", pack.id, fmt, error)
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, EXPORT_UNAVAILABLE_DETAIL) from None
