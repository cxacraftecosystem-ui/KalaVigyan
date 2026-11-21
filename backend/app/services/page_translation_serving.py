from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput
from app.research.monograph_document import ENGLISH
from app.research.monograph_page import MonographContent
from app.research.page_translation_variant import ServedTranslations, variant_content

from .monograph_document import authored_document, has_authored_content
from .page_text_index import PageKey, indexed_tag, write_page_texts
from .page_translation_store import served_translations

__all__ = ["DIGEST_SHOWN", "ServedPage", "ShownPage", "page_in_language", "variant_body"]

logger = logging.getLogger(__name__)

DIGEST_SHOWN = 16
FIRST_VERSION = 1


@dataclass(frozen=True)
class ServedPage:
    etag: str
    language: str
    body: Mapping[str, Any]


@dataclass(frozen=True)
class ShownPage:
    page: ServedPage
    wrote: bool


async def page_in_language(
    session: AsyncSession, page: PageKey, english: ServedPage, *, tag: str, language: str
) -> ShownPage:
    content: MonographContent | None = None
    wrote = await indexed_tag(session, page) != tag
    if wrote:
        content = MonographContent.model_validate(english.body["content"])
        await write_page_texts(session, page, tag, content)
    if language == ENGLISH:
        return ShownPage(english, wrote)
    served = await served_translations(session, page, language)
    if served.empty:
        return ShownPage(english, wrote)
    content = content or MonographContent.model_validate(english.body["content"])
    body = variant_body(english.body, content, served, language)
    if body is None:
        return ShownPage(english, wrote)
    etag = f"{english.etag}-{language}-{served.digest[:DIGEST_SHOWN]}"
    return ShownPage(ServedPage(etag=etag, language=language, body=body), wrote)


def variant_body(
    english: Mapping[str, Any], content: MonographContent, served: ServedTranslations, language: str
) -> dict[str, Any] | None:
    version = int(english.get("version") or FIRST_VERSION)
    variant = variant_content(content, served, language=language, source_version=version)
    if variant.translation.translated == 0:
        return None
    body = {
        **english,
        "language": language,
        "content": variant.content.model_dump(mode="json", by_alias=True),
        "translation": variant.translation.model_dump(mode="json", by_alias=True),
    }
    if not isinstance(english.get("shell"), str):
        return body
    shell = _authored_shell(english, variant.content)
    return None if shell is None else {**body, "shell": shell}


def _authored_shell(english: Mapping[str, Any], content: MonographContent) -> str | None:
    if not has_authored_content(content.craft_slug):
        return None
    try:
        drawn = authored_document(content, title=str(english["title"]), page_url=str(english["pageUrl"]))
    except InvalidInput as mismatch:
        logger.warning(
            "the %s page is served in English, its shell unmatched: %s", content.craft_slug, mismatch
        )
        return None
    return drawn.shell
