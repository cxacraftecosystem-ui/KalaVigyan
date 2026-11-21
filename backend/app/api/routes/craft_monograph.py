from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.public_deps import public_reader, read_headers, unchanged_read
from app.core.db import get_session, release_connection
from app.models import Craft, User
from app.research.monograph_document import ENGLISH, LANGUAGE_MAX_CHARS, MonographDocument, served_language
from app.research.why_here import CraftGround
from app.services import knowledge_view
from app.services.answering import NOT_FOUND_DETAIL
from app.services.monograph_document import CRAFT_SUBJECT, document_body, document_hash, document_row
from app.services.monograph_generated import generated_document
from app.services.monograph_generated_why_here import ground_hash, with_why_here
from app.services.open_work_subjects import is_family
from app.services.page_text_index import stored_tag
from app.services.page_translation_serving import ServedPage, ShownPage, page_in_language
from app.services.place_ground import subject_ground

router = APIRouter(prefix="/crafts", tags=["crafts"])

JSON_TYPE = "application/json"
FAMILY_SUBJECT = "family"
CONTENT_LANGUAGE = "Content-Language"
NO_DOCUMENT_DETAIL = "This craft's page is not a monograph document yet."
NO_VERSION_DETAIL = "This craft's monograph has no such version."

AskedLanguage = Annotated[str | None, Query(alias="lang", max_length=LANGUAGE_MAX_CHARS)]
AskedVersion = Annotated[int | None, Query(ge=1)]


@dataclass(frozen=True)
class DocumentAsk:
    language: str
    version: int | None = None


def document_ask(lang: AskedLanguage = None, version: AskedVersion = None) -> DocumentAsk:
    return DocumentAsk(language=served_language(lang), version=version)


@router.get("/{slug}/monograph")
async def get_craft_monograph(
    slug: str,
    request: Request,
    asked: DocumentAsk = Depends(document_ask),
    reader: User | None = Depends(public_reader),
    session: AsyncSession = Depends(get_session),
) -> Response:
    craft = await knowledge_view.resolve_craft(session, slug)
    if craft is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND_DETAIL)
    served = await served_document(session, craft, asked)
    if served is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, NO_VERSION_DETAIL if asked.version else NO_DOCUMENT_DETAIL
        )
    unchanged = unchanged_read(request, reader, served.etag)
    if unchanged is not None:
        unchanged.headers[CONTENT_LANGUAGE] = served.language
        return unchanged
    content = json.dumps(served.body, ensure_ascii=False, separators=(",", ":"))
    headers = {**read_headers(reader, served.etag), CONTENT_LANGUAGE: served.language}
    return Response(content, media_type=JSON_TYPE, headers=headers)


async def served_document(session: AsyncSession, craft: Craft, asked: DocumentAsk) -> ServedPage | None:
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
        shown = await _in_language(session, page, english, tag=tag, language=asked.language)
        return ServedPage(shown.etag, shown.language, dict(with_why_here(shown.body, ground)))
    generated = await generated_fallback(session, craft)
    if generated is None or (asked.version is not None and generated.version != asked.version):
        return None
    digest = document_hash(generated)
    english = ServedPage(
        etag=document_etag(generated.version, digest),
        language=generated.language,
        body=document_body(generated),
    )
    tag = stored_tag(generated.version, digest)
    return await _in_language(session, page, english, tag=tag, language=asked.language)


async def _in_language(
    session: AsyncSession, page: tuple[str, str], english: ServedPage, *, tag: str, language: str
) -> ServedPage:
    shown: ShownPage = await page_in_language(session, page, english, tag=tag, language=language)
    if shown.wrote:
        await release_connection(session)
    return shown.page


async def stored_ground(session: AsyncSession, craft: Craft) -> CraftGround | None:
    return await subject_ground(session, craft.id) if subject_kind(craft) == CRAFT_SUBJECT else None


async def generated_fallback(session: AsyncSession, craft: Craft) -> MonographDocument | None:
    return await generated_document(session, subject_kind(craft), craft.slug)


def subject_kind(craft: Craft) -> str:
    return FAMILY_SUBJECT if is_family(bool(craft.isCatchAll), craft.stateOfPractice or ()) else CRAFT_SUBJECT


def document_etag(version: int, content_hash: str) -> str:
    return f"v{version}-{content_hash}"
