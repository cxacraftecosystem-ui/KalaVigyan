from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.public_deps import public_reader, read_headers, unchanged_read
from app.core.db import get_session
from app.models import Craft, User
from app.research.monograph_document import LANGUAGE_MAX_CHARS, MonographDocument, served_language
from app.research.why_here import CraftGround
from app.services import knowledge_view
from app.services.answering import NOT_FOUND_DETAIL
from app.services.monograph_document import CRAFT_SUBJECT, document_body, document_hash, document_row
from app.services.monograph_generated import generated_document
from app.services.monograph_generated_why_here import ground_hash, with_why_here
from app.services.open_work_subjects import is_family
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
class ServedDocument:
    etag: str
    language: str
    body: dict[str, Any]


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


async def served_document(session: AsyncSession, craft: Craft, asked: DocumentAsk) -> ServedDocument | None:
    row = await document_row(
        session, CRAFT_SUBJECT, craft.slug, language=asked.language, version=asked.version
    )
    if row is not None:
        ground = await stored_ground(session, craft)
        body = dict(with_why_here({**row.document, "language": row.language}, ground))
        return ServedDocument(
            etag=document_etag(row.version, ground_hash(row.contentHash, ground)),
            language=row.language,
            body=body,
        )
    generated = await generated_fallback(session, craft)
    if generated is None or (asked.version is not None and generated.version != asked.version):
        return None
    return ServedDocument(
        etag=document_etag(generated.version, document_hash(generated)),
        language=generated.language,
        body=document_body(generated),
    )


async def stored_ground(session: AsyncSession, craft: Craft) -> CraftGround | None:
    return await subject_ground(session, craft.id) if subject_kind(craft) == CRAFT_SUBJECT else None


async def generated_fallback(session: AsyncSession, craft: Craft) -> MonographDocument | None:
    return await generated_document(session, subject_kind(craft), craft.slug)


def subject_kind(craft: Craft) -> str:
    return FAMILY_SUBJECT if is_family(bool(craft.isCatchAll), craft.stateOfPractice or ()) else CRAFT_SUBJECT


def document_etag(version: int, content_hash: str) -> str:
    return f"v{version}-{content_hash}"
