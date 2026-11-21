from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Annotated

from fastapi import BackgroundTasks, HTTPException, Query, Request, Response, status

from app.api.public_deps import read_headers, unchanged_read
from app.models import User
from app.research.document_parts import compact_json, document_parts, part_body
from app.services.stored_document_rebuilds import rebuild_wanted
from app.services.stored_documents import GeneratedRead

__all__ = [
    "CONTENT_LANGUAGE",
    "JSON_TYPE",
    "NO_PART_DETAIL",
    "PARTS_MAX",
    "AskedPart",
    "ServedDocument",
    "document_response",
    "generated_served",
    "queue_rebuild",
]

JSON_TYPE = "application/json"
CONTENT_LANGUAGE = "Content-Language"
NO_PART_DETAIL = "This monograph has no such part."
PARTS_MAX = 64

AskedPart = Annotated[int | None, Query(ge=0, le=PARTS_MAX)]


@dataclass(frozen=True)
class ServedDocument:
    etag: str
    language: str
    text: str
    version: int
    rebuild: tuple[str, str] | None = None


def generated_served(read: GeneratedRead) -> ServedDocument | None:
    copy = read.copy
    if copy is None:
        return None
    rebuild = (read.subject.kind, read.subject.slug) if read.rebuild else None
    return ServedDocument(copy.etag, copy.language, copy.text, copy.version, rebuild)


def queue_rebuild(background: BackgroundTasks, served: ServedDocument) -> None:
    if served.rebuild is not None:
        background.add_task(rebuild_wanted, *served.rebuild)


def document_response(
    request: Request, reader: User | None, served: ServedDocument, part: int | None
) -> Response:
    etag, content = served.etag, served.text
    if part is not None:
        parts = document_parts(json.loads(served.text))
        if part >= len(parts):
            raise HTTPException(status.HTTP_404_NOT_FOUND, NO_PART_DETAIL)
        etag = f"{served.etag}-p{part}"
        content = compact_json(part_body(parts[part], served.version))
    unchanged = unchanged_read(request, reader, etag)
    if unchanged is not None:
        unchanged.headers[CONTENT_LANGUAGE] = served.language
        return unchanged
    headers = {**read_headers(reader, etag), CONTENT_LANGUAGE: served.language}
    return Response(content, media_type=JSON_TYPE, headers=headers)
