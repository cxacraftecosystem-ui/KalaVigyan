from __future__ import annotations

import asyncio
import io
import logging
from typing import TYPE_CHECKING

from app.core.errors import InvalidInput
from app.research.fetcher import PDF_MAX_DECOMPRESSED_BYTES

if TYPE_CHECKING:
    from pypdf import PdfReader

__all__ = ["FILE_BYTES_MAX", "FILE_TYPES", "PDF", "PDF_PAGES_MAX", "TEXT", "file_text"]

logger = logging.getLogger(__name__)

FILE_BYTES_MAX = 20 * 1024 * 1024
PDF_PAGES_MAX = 150
PDF, TEXT = "pdf", "text"
FILE_TYPES = {PDF: "application/pdf", TEXT: "text/plain"}
PDF_MAGIC = b"%PDF-"
EXTRACTIONS = asyncio.Semaphore(2)
NOT_A_PDF = "The file is not a PDF; upload the PDF itself, or supply the text with upload text."
NO_TEXT = "The PDF has no text layer to read; supply its passages as text instead."
UNREADABLE = "The PDF could not be read ({kind}); supply its passages as text instead."
ENCRYPTED = "The PDF is encrypted; supply an unlocked copy or its passages as text."
TOO_BIG = "The PDF's pages decompress past {limit} bytes; supply its passages as text instead."
NOT_UTF8 = "The text file is not UTF-8 text."


async def file_text(data: bytes, kind: str) -> str:
    if kind == TEXT:
        return _plain(data)
    if not data.startswith(PDF_MAGIC):
        raise InvalidInput(NOT_A_PDF)
    async with EXTRACTIONS:
        return await asyncio.to_thread(_pdf_text, data)


def _plain(data: bytes) -> str:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise InvalidInput(NOT_UTF8) from None
    return text.replace("\x00", "").strip()


def _pdf_text(data: bytes) -> str:
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(data), strict=False)
        if reader.is_encrypted and not reader.decrypt(""):
            raise InvalidInput(ENCRYPTED)
        texts = _page_texts(reader)
    except InvalidInput:
        raise
    except Exception as error:
        logger.warning("a supplied PDF could not be read: %s", type(error).__name__)
        raise InvalidInput(UNREADABLE.format(kind=type(error).__name__)) from None
    text = "\n\n".join(page for page in texts if page.strip()).replace("\x00", "")
    if not text.strip():
        raise InvalidInput(NO_TEXT)
    return text


def _page_texts(reader: PdfReader) -> list[str]:
    texts: list[str] = []
    decompressed = 0
    for page in reader.pages[:PDF_PAGES_MAX]:
        contents = page.get_contents()
        decompressed += len(contents.get_data()) if contents is not None else 0
        if decompressed > PDF_MAX_DECOMPRESSED_BYTES:
            raise InvalidInput(TOO_BIG.format(limit=PDF_MAX_DECOMPRESSED_BYTES))
        texts.append(page.extract_text() or "")
    return texts
