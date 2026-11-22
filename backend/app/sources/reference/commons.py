from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from app.core.errors import InvalidInput
from app.research.evidence import EvidenceItem, SearchQuery, SourceDocument
from app.research.images import (
    IMAGE_DESCRIPTION_MAX_CHARS,
    ImageCandidate,
    ImageQuery,
    clipped,
    without_tracking,
)

from ..adapter import HttpSourceAdapter, build_document, checked_k, usable_records
from ..records import UnusableRecord, https_or_none, markup_text, title_of
from .commons_dates import original_date
from .mediawiki import (
    WIKIMEDIA_PUBLISHER,
    WIKIMEDIA_RATE,
    action_api,
    language_and_native,
    page_revision,
    pages_in_order,
    primary_language,
    with_language,
)

__all__ = ["COMMONS_RATE", "COMMONS_SITE", "IMAGE_THUMB_WIDTH", "WikimediaCommonsAdapter", "file_metadata"]

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
COMMONS_RATE = WIKIMEDIA_RATE
COMMONS_SITE = "Wikimedia Commons"
FILE_NAMESPACE = 6
IMAGE_THUMB_WIDTH = 960
IMAGE_MIME_PREFIX = "image/"
EXTMETADATA = (
    "ObjectName",
    "ImageDescription",
    "DateTimeOriginal",
    "Artist",
    "Credit",
    "LicenseShortName",
    "LicenseUrl",
    "AttributionRequired",
)
FILE_PROPS = {
    "prop": "imageinfo|info|revisions",
    "inprop": "url",
    "rvprop": "ids|timestamp",
    "iiprop": "url|mime|extmetadata",
    "iiextmetadatafilter": "|".join(EXTMETADATA),
}
IMAGE_PROPS = {
    "prop": "imageinfo|info",
    "inprop": "url",
    "iiprop": "url|size|mime|extmetadata",
    "iiurlwidth": str(IMAGE_THUMB_WIDTH),
    "iiextmetadatafilter": FILE_PROPS["iiextmetadatafilter"],
}
DOCUMENT_LINES = (
    ("description", ""),
    ("date", "Date: "),
    ("author", "Author: "),
    ("credit", "Credit: "),
    ("licence", "Licence: "),
)
PAGE_ID = re.compile(r"^[1-9]\d*$")
MEDIA_KIND = "MEDIA"
DOCUMENT_KIND = "OTHER"
DOCUMENT_MIMES = frozenset({"application/pdf", "image/vnd.djvu"})


class WikimediaCommonsAdapter(HttpSourceAdapter):
    name = "wikimedia_commons"

    async def _search_records(self, query: SearchQuery, k: int) -> list[Any]:
        language = primary_language(query.language)
        params = FILE_PROPS | {
            "action": "query",
            "generator": "search",
            "gsrsearch": query.text,
            "gsrnamespace": str(FILE_NAMESPACE),
            "gsrlimit": str(k),
            "iiextmetadatalanguage": language,
        }
        return [(page, language) for page in pages_in_order(await action_api(self.http, COMMONS_API, params))]

    def _item(self, record: Any, retrieved_at: datetime) -> EvidenceItem:
        page, language = record
        meta = file_metadata(page)
        if meta["licence"] is None:
            raise UnusableRecord("no licence")
        url = https_or_none(page.get("canonicalurl") or page.get("fullurl"))
        if url is None:
            raise UnusableRecord("no https description page")
        revision = page_revision(page)
        file_title = title_of(page.get("title"))
        return EvidenceItem(
            id=f"{self.name}:{with_language(str(page['pageid']), language)}",
            adapter=self.name,
            tier=self.tier,
            source_type=_file_kind(page),
            url=url,
            title=meta["title"] or file_title.removeprefix("File:"),
            authors=[meta["author"]] if meta["author"] else [],
            published=meta["published"],
            retrieved_at=retrieved_at,
            licence=meta["licence"],
            attribution=_attribution(meta),
            publisher=WIKIMEDIA_PUBLISHER,
            trust="C",
            external_ids={
                "commons_file": file_title,
                "commons_media": f"M{page['pageid']}",
                "revision": revision.id,
            },
        )

    async def _fetch_document(self, native: str, retrieved_at: datetime) -> SourceDocument:
        language, page_id = language_and_native(native)
        if not PAGE_ID.match(page_id):
            raise InvalidInput(f"{native!r} is not a Wikimedia Commons page id")
        params = FILE_PROPS | {"action": "query", "pageids": page_id, "iiextmetadatalanguage": language}
        pages = pages_in_order(await action_api(self.http, COMMONS_API, params))
        if not pages or pages[0].get("missing") or pages[0].get("ns") != FILE_NAMESPACE:
            raise self._not_found(native, "no file")
        item = self._item((pages[0], language), retrieved_at)
        return build_document(item, _document_text(item.title, file_metadata(pages[0])), "EXCERPT")

    async def images(self, query: ImageQuery, k: int) -> list[ImageCandidate]:
        params = IMAGE_PROPS | {
            "action": "query",
            "generator": "search",
            "gsrsearch": query.text,
            "gsrnamespace": str(FILE_NAMESPACE),
            "gsrlimit": str(checked_k(k)),
            "iiextmetadatalanguage": primary_language(query.language),
        }
        pages = pages_in_order(await action_api(self.http, COMMONS_API, params))
        retrieved_at = self.clock()
        return usable_records(self.name, pages, lambda page: self._image(page, retrieved_at))

    def _image(self, page: dict[str, Any], retrieved_at: datetime) -> ImageCandidate:
        meta = file_metadata(page)
        info = (page.get("imageinfo") or [{}])[0]
        if not str(info.get("mime") or "").startswith(IMAGE_MIME_PREFIX):
            raise UnusableRecord("not an image")
        page_url = https_or_none(page.get("canonicalurl") or page.get("fullurl"))
        original = https_or_none(info.get("url"))
        shown = https_or_none(info.get("thumburl")) or original
        if page_url is None or original is None or shown is None:
            raise UnusableRecord("no https description page or image")
        title = meta["title"] or title_of(page.get("title")).removeprefix("File:")
        return ImageCandidate(
            provider=self.name,
            page_url=page_url,
            image_url=without_tracking(shown),
            original_url=without_tracking(original),
            width=info.get("width"),
            height=info.get("height"),
            title=clipped(title),
            description=_described(meta["description"]),
            author=clipped(meta["author"]) if meta["author"] else None,
            site=COMMONS_SITE,
            licence=meta["licence"],
            licence_url=meta["licence_url"],
            retrieved_at=retrieved_at,
        )


def file_metadata(page: dict[str, Any]) -> dict[str, str | None]:
    if not page.get("pageid") or page.get("ns") != FILE_NAMESPACE:
        raise UnusableRecord("not a file page")
    info = (page.get("imageinfo") or [{}])[0]
    meta = info.get("extmetadata") or {}
    date = (meta.get("DateTimeOriginal") or {}).get("value")
    return {
        "title": _field(meta, "ObjectName"),
        "description": _field(meta, "ImageDescription"),
        "date": markup_text(date),
        "published": original_date(date),
        "author": _field(meta, "Artist"),
        "credit": _field(meta, "Credit"),
        "licence": _field(meta, "LicenseShortName"),
        "licence_url": https_or_none(_field(meta, "LicenseUrl")),
    }


def _field(meta: dict[str, Any], name: str) -> str | None:
    return markup_text((meta.get(name) or {}).get("value"))


def _file_kind(page: dict[str, Any]) -> str:
    mime = (page.get("imageinfo") or [{}])[0].get("mime")
    return DOCUMENT_KIND if mime in DOCUMENT_MIMES else MEDIA_KIND


def _attribution(meta: dict[str, str | None]) -> str:
    licence = meta["licence"] or ""
    if meta["licence_url"]:
        licence = f"{licence} ({meta['licence_url']})"
    parts = [meta["author"], licence, "via Wikimedia Commons"]
    return ", ".join(part for part in parts if part)


def _described(description: str | None) -> str | None:
    return clipped(description, IMAGE_DESCRIPTION_MAX_CHARS) if description else None


def _document_text(title: str, meta: dict[str, str | None]) -> str:
    lines = [title]
    lines.extend(f"{label}{meta[key]}" for key, label in DOCUMENT_LINES if meta[key])
    return "\n".join(lines)
