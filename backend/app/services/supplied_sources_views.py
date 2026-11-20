from __future__ import annotations

from app.models import SuppliedSource
from app.research.supplied_sources import (
    READY,
    CiteAs,
    Confirmation,
    SourceAccess,
    SourceIdentity,
    SuppliedPassage,
    SuppliedSourceReply,
    SuppliedSourceView,
    SuppliedUpload,
)

from .supplied_sources_pdf import FILE_BYTES_MAX, FILE_TYPES

__all__ = ["slot_path", "supplied_reply", "supplied_view"]

SLOT_PATH = "/api/knowledge/supplied-sources/slots/{token}"
HELD = (
    "Held privately for reviewers as {characters} characters (SHA-256 {digest}); only short quotes and their "
    "citation are ever shown."
)
WAITING = "The source is recorded; its words arrive through the upload slot within 30 minutes."
CITE = (
    "Cite it in a fact's or structure item's sources as url {url} with title {title}, quoting its words "
    "verbatim with their locators; the QUOTES gate reads this text instead of fetching the address."
)
UPLOAD = "PUT the file's bytes to upload_url (Content-Type {types}), then cite it as url {url}."


def slot_path(token: str) -> str:
    return SLOT_PATH.format(token=token)


def supplied_reply(row: SuppliedSource, upload_url: str | None = None) -> SuppliedSourceReply:
    ready = row.state == READY
    return SuppliedSourceReply(
        supplied_source_id=row.id,
        state=row.state,
        cite_as=CiteAs(url=row.citeUrl, title=row.title, licence=row.licence),
        grade=row.grade,
        grade_reason=row.gradeReason,
        confirmed=Confirmation.model_validate(row.confirmation) if row.confirmation else None,
        characters=row.characters,
        passages=len(row.passages or []),
        text_sha256=row.textSha256,
        upload=_upload(row, upload_url),
        message=_message(row) if ready else WAITING,
        next_step=_next_step(row) if ready else UPLOAD.format(types=_type(row), url=row.citeUrl),
    )


def supplied_view(row: SuppliedSource) -> SuppliedSourceView:
    return SuppliedSourceView(
        id=row.id,
        state=row.state,
        cite_url=row.citeUrl,
        identity=SourceIdentity.model_validate(row.identity),
        access=SourceAccess(how=row.accessKind, accessed_on=row.accessedOn, note=row.accessNote),
        licence=row.licence,
        grade=row.grade,
        grade_reason=row.gradeReason,
        confirmed=Confirmation.model_validate(row.confirmation) if row.confirmation else None,
        characters=row.characters,
        text_sha256=row.textSha256,
        passages=[SuppliedPassage.model_validate(passage) for passage in row.passages or []],
        text=None if row.passages else row.text,
        created_at=row.createdAt,
    )


def _upload(row: SuppliedSource, upload_url: str | None) -> SuppliedUpload | None:
    if upload_url is None or row.slotExpiresAt is None or row.upload is None:
        return None
    return SuppliedUpload(
        upload_url=upload_url,
        upload_types=[_type(row)],
        upload_max_bytes=FILE_BYTES_MAX,
        expires_at=row.slotExpiresAt,
    )


def _message(row: SuppliedSource) -> str:
    return HELD.format(characters=row.characters, digest=(row.textSha256 or "")[:12])


def _next_step(row: SuppliedSource) -> str:
    return CITE.format(url=row.citeUrl, title=row.title)


def _type(row: SuppliedSource) -> str:
    return FILE_TYPES.get(row.upload or "", "")
