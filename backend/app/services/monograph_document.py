from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput
from app.data.monograph_files import CONTENT_FILE, MONOGRAPHS_DIR
from app.models import MonographDocument as DocumentRow
from app.research.monograph_document import ENGLISH, MonographDocument, fragment_file_name, spec_file_name
from app.research.monograph_page import (
    KIT_FILES,
    MonographContent,
    PageParts,
    authored_main,
    keyed_kit,
)

__all__ = [
    "CONTENT_FILE",
    "CRAFT_SUBJECT",
    "FRAGMENTS_FOLDER",
    "KIT_DIR",
    "MONOGRAPHS_DIR",
    "NATIVE_FILE",
    "SPECS_FOLDER",
    "TEMPLATE_FILE",
    "authored_document",
    "component_specs",
    "craft_page_url",
    "document_body",
    "document_hash",
    "document_json",
    "document_row",
    "has_authored_content",
    "kit_sources",
    "latest_document_row",
    "monograph_content",
    "monograph_kit",
    "monograph_shell",
    "native_views",
    "page_parts",
    "store_document",
    "stored_document",
]

KIT_DIR = MONOGRAPHS_DIR / "kit"
TEMPLATE_FILE = "template.html"
FRAGMENTS_FOLDER = "fragments"
SPECS_FOLDER = "specs"
NATIVE_FILE = "native.json"
CRAFT_SUBJECT = "craft"
CRAFT_PATH = "/crafts/"
FIRST_VERSION = 1
UNHASHED_FIELDS = frozenset({"version", "language"})
GOLDEN_INDENT = 1


def has_authored_content(slug: str) -> bool:
    return (MONOGRAPHS_DIR / slug / CONTENT_FILE).is_file()


def monograph_content(slug: str) -> MonographContent:
    return MonographContent.model_validate_json(_text(MONOGRAPHS_DIR / slug / CONTENT_FILE))


def monograph_shell(slug: str) -> str:
    return _text(MONOGRAPHS_DIR / slug / TEMPLATE_FILE)


def kit_sources() -> dict[str, str]:
    return {name: _text(KIT_DIR / name) for name in KIT_FILES}


def monograph_kit() -> dict[str, str]:
    return keyed_kit(kit_sources())


def page_parts(content: MonographContent) -> PageParts:
    return PageParts(fragments=_fragments(content), kit=monograph_kit())


def component_specs(content: MonographContent) -> dict[str, dict[str, Any]]:
    folder = MONOGRAPHS_DIR / content.craft_slug / SPECS_FOLDER
    found = {c.label: folder / spec_file_name(c.label) for c in content.components}
    return {label: _spec(path) for label, path in found.items() if path.is_file()}


def native_views(slug: str) -> frozenset[str]:
    path = MONOGRAPHS_DIR / slug / NATIVE_FILE
    if not path.is_file():
        return frozenset()
    labels = json.loads(_text(path))
    if not isinstance(labels, list) or not all(isinstance(label, str) for label in labels):
        raise InvalidInput(f"{NATIVE_FILE} of {slug} is not a list of component labels")
    return frozenset(labels)


def craft_page_url(site: str, slug: str) -> str:
    return f"{site.rstrip('/')}{CRAFT_PATH}{slug}"


def authored_document(content: MonographContent, *, title: str, page_url: str) -> MonographDocument:
    native = native_views(content.craft_slug)
    specs = {label: spec for label, spec in component_specs(content).items() if label in native}
    fragments = _fragments(content)
    inlined = {label: fragment for label, fragment in fragments.items() if label not in specs}
    return MonographDocument(
        subject_kind=CRAFT_SUBJECT,
        subject_slug=content.craft_slug,
        title=title,
        version=FIRST_VERSION,
        content=content,
        specs=specs,
        shell=authored_main(monograph_shell(content.craft_slug), content, inlined, kept=frozenset(specs)),
        page_url=page_url,
    )


def document_body(document: MonographDocument) -> dict[str, Any]:
    return document.model_dump(mode="json", by_alias=True)


def document_hash(document: MonographDocument) -> str:
    body = document.model_dump(mode="json", by_alias=True, exclude=set(UNHASHED_FIELDS))
    text = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def document_json(document: MonographDocument) -> str:
    return json.dumps(document_body(document), ensure_ascii=False, indent=GOLDEN_INDENT) + "\n"


async def document_row(
    session: AsyncSession,
    subject_kind: str,
    slug: str,
    *,
    language: str = ENGLISH,
    version: int | None = None,
) -> DocumentRow | None:
    query = select(DocumentRow).where(
        DocumentRow.subjectKind == subject_kind,
        DocumentRow.subjectSlug == slug,
        DocumentRow.language == language,
    )
    if version is not None:
        return await session.scalar(query.where(DocumentRow.version == version))
    return await session.scalar(query.order_by(DocumentRow.version.desc()).limit(1))


async def latest_document_row(
    session: AsyncSession, subject_kind: str, slug: str, language: str = ENGLISH
) -> DocumentRow | None:
    return await document_row(session, subject_kind, slug, language=language)


async def stored_document(
    session: AsyncSession, subject_kind: str, slug: str, language: str = ENGLISH
) -> MonographDocument | None:
    row = await latest_document_row(session, subject_kind, slug, language)
    return None if row is None else MonographDocument.model_validate(row.document)


async def store_document(session: AsyncSession, document: MonographDocument) -> int | None:
    latest = await latest_document_row(
        session, document.subject_kind, document.subject_slug, document.language
    )
    digest = document_hash(document)
    if latest is not None and latest.contentHash == digest:
        return None
    version = FIRST_VERSION if latest is None else latest.version + 1
    stamped = document.model_copy(update={"version": version})
    session.add(
        DocumentRow(
            subjectKind=document.subject_kind,
            subjectSlug=document.subject_slug,
            language=document.language,
            version=version,
            document=document_body(stamped),
            contentHash=digest,
        )
    )
    await session.flush()
    return version


def _fragments(content: MonographContent) -> dict[str, str]:
    folder = MONOGRAPHS_DIR / content.craft_slug / FRAGMENTS_FOLDER
    return {c.label: _text(folder / fragment_file_name(c.label)) for c in content.components}


def _spec(path: Path) -> dict[str, Any]:
    value = json.loads(_text(path))
    if not isinstance(value, dict):
        raise InvalidInput(f"The component spec {path.name} is not a JSON object")
    return value


def _text(path: Path) -> str:
    if not path.is_file():
        raise InvalidInput(f"The monograph file {path.name} is missing from {path.parent.name}")
    return path.read_bytes().decode("utf-8")
