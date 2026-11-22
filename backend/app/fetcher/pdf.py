from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import Any

from pypdf import PageObject, PdfReader, apply_configuration
from pypdf.errors import LimitReachedError
from pypdf.generic import DictionaryObject, StreamObject

from app.research.fetcher import PDF_MAX_DECOMPRESSED_BYTES, PDF_MAX_PAGES, FetchRefused, PageMetadata
from app.sources.records import clean_text, partial_date_of

__all__ = ["pdf_text"]

FORM_SUBTYPE = "/Form"
TYPE1_SUBTYPE = "/Type1"
TYPE1_FONT_FILES = ("/FontFile", "/FontFile3")
STREAM_LIMITS = (
    "zlib_maximum_output_length",
    "lzw_maximum_output_length",
    "run_length_maximum_output_length",
    "array_based_stream_maximum_output_length",
)


def pdf_text(
    url: str,
    body: bytes,
    *,
    max_pages: int = PDF_MAX_PAGES,
    max_decompressed: int = PDF_MAX_DECOMPRESSED_BYTES,
) -> tuple[str, bool, PageMetadata]:
    try:
        with apply_configuration(**dict.fromkeys(STREAM_LIMITS, max_decompressed)):
            reader = _opened(url, body)
            page_count = len(reader.pages)
            texts = _page_texts(reader, min(page_count, max_pages), _DecodeBudget(url, max_decompressed))
            metadata = _metadata(reader)
    except FetchRefused:
        raise
    except LimitReachedError:
        raise FetchRefused(url, "PDF_LIMIT", "a stream decompresses past the parser's limit") from None
    except Exception as error:
        raise FetchRefused(url, "PARSE_FAILED", f"PDF could not be read ({type(error).__name__})") from None
    text = "\n\n".join(t for t in texts if t.strip())
    if not text.strip():
        raise FetchRefused(url, "PARSE_FAILED", "the PDF has no text layer")
    return text, page_count > max_pages, metadata


@dataclass
class _DecodeBudget:
    url: str
    limit: int
    spent: int = 0
    counted: set[int] = field(default_factory=set)

    def read_page(self, page: PageObject, number: int) -> None:
        contents = page.get_contents()
        self._spend(len(contents.get_data()) if contents is not None else 0, number)
        self._read_resources(page.get("/Resources"), number)

    def _read_resources(self, value: Any, number: int) -> None:
        resources = _resolved(value)
        if not isinstance(resources, DictionaryObject):
            return
        for font in _entries(resources.get("/Font")):
            for stream in _font_text_streams(font):
                self._spend_once(stream, number)
        for xobject in _entries(resources.get("/XObject")):
            if xobject.get("/Subtype") == FORM_SUBTYPE and id(xobject) not in self.counted:
                self._spend_once(xobject, number)
                self._read_resources(xobject.get("/Resources"), number)

    def _spend_once(self, stream: StreamObject, number: int) -> None:
        if id(stream) not in self.counted:
            self.counted.add(id(stream))
            self._spend(len(stream.get_data()), number)

    def _spend(self, size: int, number: int) -> None:
        self.spent += size
        if self.spent > self.limit:
            raise FetchRefused(self.url, "PDF_LIMIT", f"content past {self.limit} bytes by page {number}")


def _page_texts(reader: PdfReader, pages: int, budget: _DecodeBudget) -> list[str]:
    texts: list[str] = []
    for index in range(pages):
        page = reader.pages[index]
        budget.read_page(page, index + 1)
        texts.append(page.extract_text() or "")
    return texts


def _font_text_streams(font: DictionaryObject) -> list[StreamObject]:
    to_unicode = _resolved(font.get("/ToUnicode"))
    if isinstance(to_unicode, StreamObject):
        return [to_unicode]
    descriptor = _resolved(font.get("/FontDescriptor"))
    if font.get("/Subtype") != TYPE1_SUBTYPE or not isinstance(descriptor, DictionaryObject):
        return []
    files = (_resolved(descriptor.get(key)) for key in TYPE1_FONT_FILES)
    return [file for file in files if isinstance(file, StreamObject)]


def _entries(value: Any) -> list[DictionaryObject]:
    named = _resolved(value)
    if not isinstance(named, DictionaryObject):
        return []
    resolved = (_resolved(entry) for entry in named.values())
    return [entry for entry in resolved if isinstance(entry, DictionaryObject)]


def _resolved(value: Any) -> Any:
    return value.get_object() if hasattr(value, "get_object") else value


def _opened(url: str, body: bytes) -> PdfReader:
    reader = PdfReader(io.BytesIO(body), strict=False)
    if reader.is_encrypted and not reader.decrypt(""):
        raise FetchRefused(url, "PARSE_FAILED", "the PDF is encrypted")
    return reader


def _metadata(reader: PdfReader) -> PageMetadata:
    info: Any = reader.metadata or {}
    title = clean_text(getattr(info, "title", None))
    author = clean_text(getattr(info, "author", None))
    created = getattr(info, "creation_date_raw", None)
    return PageMetadata(
        title=title[:1000] if title else None,
        authors=[author[:300]] if author else [],
        published=_pdf_date(created),
    )


def _pdf_date(raw: Any) -> str | None:
    if not isinstance(raw, str):
        return None
    digits = raw.removeprefix("D:")[:8]
    if len(digits) == 8 and digits.isdigit():
        return partial_date_of(f"{digits[:4]}-{digits[4:6]}-{digits[6:]}")
    if len(digits) >= 4 and digits[:4].isdigit():
        return partial_date_of(digits[:4])
    return None
