from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.research.monograph_document import MonographDocument

from .monograph_document import CRAFT_SUBJECT, document_hash, latest_document_row
from .monograph_generated import generated_document
from .page_text_index import PageKey, stored_tag

__all__ = ["CATEGORY", "EnglishPage", "english_page"]

CATEGORY = "category"


@dataclass(frozen=True)
class EnglishPage:
    document: MonographDocument
    tag: str


async def english_page(session: AsyncSession, page: PageKey) -> EnglishPage | None:
    kind, slug = page
    if kind != CATEGORY:
        row = await latest_document_row(session, CRAFT_SUBJECT, slug)
        if row is not None:
            document = MonographDocument.model_validate({**row.document, "language": row.language})
            return EnglishPage(document, stored_tag(row.version, row.contentHash))
    generated = await generated_document(session, kind, slug)
    if generated is None:
        return None
    return EnglishPage(generated, stored_tag(generated.version, document_hash(generated)))
