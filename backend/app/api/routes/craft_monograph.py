from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.document_reads import (
    WHOLE_DOCUMENT,
    AskedPart,
    AskedTag,
    PartAsk,
    ServedDocument,
    document_response,
    generated_in_language,
    in_language,
    queue_rebuild,
)
from app.api.public_deps import public_reader
from app.core.db import get_session
from app.models import Craft, User
from app.research.document_parts import compact_json
from app.research.monograph_document import ENGLISH, LANGUAGE_MAX_CHARS, served_language
from app.research.why_here import CraftGround
from app.services import knowledge_view
from app.services.answering import NOT_FOUND_DETAIL
from app.services.monograph_document import CRAFT_SUBJECT, document_row
from app.services.monograph_generated_why_here import ground_hash, with_why_here
from app.services.open_work_subjects import is_family
from app.services.page_text_index import stored_tag
from app.services.page_translation_serving import ServedPage
from app.services.place_ground import subject_ground
from app.services.stored_documents import GeneratedRead, generated_read

router = APIRouter(prefix="/crafts", tags=["crafts"])

FAMILY_SUBJECT = "family"
NO_DOCUMENT_DETAIL = "This craft's page is not a monograph document yet."
NO_VERSION_DETAIL = "This craft's monograph has no such version."

AskedLanguage = Annotated[str | None, Query(alias="lang", max_length=LANGUAGE_MAX_CHARS)]
AskedVersion = Annotated[int | None, Query(ge=1)]


@dataclass(frozen=True)
class DocumentAsk:
    language: str
    version: int | None = None
    part: PartAsk = WHOLE_DOCUMENT


def document_ask(
    lang: AskedLanguage = None, version: AskedVersion = None, part: AskedPart = None, tag: AskedTag = None
) -> DocumentAsk:
    return DocumentAsk(language=served_language(lang), version=version, part=PartAsk(part, tag))


@dataclass(frozen=True)
class ReaderAsk:
    request: Request
    reader: User | None
    asked: DocumentAsk


def reader_ask(
    request: Request,
    asked: DocumentAsk = Depends(document_ask),
    reader: User | None = Depends(public_reader),
) -> ReaderAsk:
    return ReaderAsk(request, reader, asked)


@router.get("/{slug}/monograph")
async def get_craft_monograph(
    slug: str,
    background: BackgroundTasks,
    read: ReaderAsk = Depends(reader_ask),
    session: AsyncSession = Depends(get_session),
) -> Response:
    craft = await knowledge_view.resolve_craft(session, slug)
    if craft is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND_DETAIL)
    served = await served_document(session, craft, read.asked)
    if served is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, NO_VERSION_DETAIL if read.asked.version else NO_DOCUMENT_DETAIL
        )
    queue_rebuild(background, served)
    return document_response(read.request, read.reader, served, read.asked.part)


async def served_document(session: AsyncSession, craft: Craft, asked: DocumentAsk) -> ServedDocument | None:
    page = (subject_kind(craft), craft.slug)
    row = await document_row(session, CRAFT_SUBJECT, craft.slug, language=ENGLISH, version=asked.version)
    if row is not None:
        ground = await stored_ground(session, craft)
        english = ServedPage(
            etag=document_etag(row.version, ground_hash(row.contentHash, ground)),
            language=row.language,
            body={**row.document, "language": row.language},
        )
        tag = stored_tag(row.version, row.contentHash)
        shown = await in_language(session, page, english, tag=tag, language=asked.language)
        body = with_why_here(shown.body, ground)
        return ServedDocument(shown.etag, shown.language, compact_json(body), row.version)
    read = await generated_fallback(session, craft)
    if read.copy is None or (asked.version is not None and read.copy.version != asked.version):
        return None
    return await generated_in_language(session, read, language=asked.language)


async def stored_ground(session: AsyncSession, craft: Craft) -> CraftGround | None:
    return await subject_ground(session, craft.id) if subject_kind(craft) == CRAFT_SUBJECT else None


async def generated_fallback(session: AsyncSession, craft: Craft) -> GeneratedRead:
    return await generated_read(session, subject_kind(craft), craft.slug)


def subject_kind(craft: Craft) -> str:
    return FAMILY_SUBJECT if is_family(bool(craft.isCatchAll), craft.stateOfPractice or ()) else CRAFT_SUBJECT


def document_etag(version: int, content_hash: str) -> str:
    return f"v{version}-{content_hash}"
