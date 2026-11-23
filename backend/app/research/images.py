from __future__ import annotations

import ipaddress
import uuid
from typing import Protocol, Self, runtime_checkable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import AwareDatetime, Field, model_validator

from .base import ContractModel, HttpsUrl
from .evidence import ADAPTER_NAME_PATTERN, SEARCH_QUERY_MAX_CHARS
from .licences import open_licence
from .media_refs import MediaRef
from .public_suffixes import registrable_name

__all__ = [
    "IMAGE_DESCRIPTION_MAX_CHARS",
    "MEDIA_TEXT_MAX_CHARS",
    "ImageCandidate",
    "ImageQuery",
    "ImageSource",
    "clipped",
    "media_ref_of",
    "openly_licensed",
    "same_site",
    "shown_inline",
    "site_of",
    "without_tracking",
]

MEDIA_TEXT_MAX_CHARS = 300
IMAGE_DESCRIPTION_MAX_CHARS = 2000
TRACKING_PREFIX = "utm_"
ELLIPSIS = "…"


class ImageQuery(ContractModel):
    text: str = Field(min_length=2, max_length=SEARCH_QUERY_MAX_CHARS)
    language: str = Field(default="en", min_length=2, max_length=16)


class ImageCandidate(ContractModel):
    provider: str = Field(pattern=ADAPTER_NAME_PATTERN)
    page_url: HttpsUrl
    image_url: HttpsUrl
    original_url: HttpsUrl
    width: int | None = Field(default=None, ge=1)
    height: int | None = Field(default=None, ge=1)
    title: str = Field(min_length=1, max_length=MEDIA_TEXT_MAX_CHARS)
    description: str | None = Field(default=None, max_length=IMAGE_DESCRIPTION_MAX_CHARS)
    author: str | None = Field(default=None, max_length=MEDIA_TEXT_MAX_CHARS)
    site: str = Field(min_length=1, max_length=MEDIA_TEXT_MAX_CHARS)
    credit: str | None = Field(default=None, max_length=MEDIA_TEXT_MAX_CHARS)
    licence: str | None = Field(default=None, max_length=200)
    licence_url: HttpsUrl | None = None
    retrieved_at: AwareDatetime

    @model_validator(mode="after")
    def _size_is_whole(self) -> Self:
        if (self.width is None) != (self.height is None):
            raise ValueError(f"image {self.image_url} gives both its width and height, or neither")
        return self

    @property
    def alt(self) -> str:
        return clipped(self.description or self.title)

    @property
    def described(self) -> str:
        return f"{self.title}\n{self.description or ''}"

    @property
    def original_key(self) -> str:
        parts = urlsplit(self.original_url)
        return f"{parts.netloc.lower()}{parts.path}"


@runtime_checkable
class ImageSource(Protocol):
    name: str

    async def images(self, query: ImageQuery, k: int) -> list[ImageCandidate]: ...


def openly_licensed(candidate: ImageCandidate) -> bool:
    return open_licence(candidate.licence) or open_licence(candidate.licence_url)


def shown_inline(candidate: ImageCandidate) -> bool:
    return openly_licensed(candidate) and bool(candidate.author)


def media_ref_of(candidate: ImageCandidate, *, media_id: uuid.UUID, source_id: str | None) -> MediaRef:
    return MediaRef(
        id=media_id,
        display="INLINE" if shown_inline(candidate) else "LINK_CARD",
        provider=candidate.provider,
        page_url=candidate.page_url,
        image_url=candidate.image_url,
        width=candidate.width,
        height=candidate.height,
        title=candidate.title,
        alt=candidate.alt,
        author=candidate.author,
        site=candidate.site,
        credit=candidate.credit,
        licence=candidate.licence,
        licence_url=candidate.licence_url,
        source_id=source_id,
        retrieved_at=candidate.retrieved_at,
    )


def site_of(host: str) -> str | None:
    name = host.lower().rstrip(".").strip("[]")
    if not name or _is_address(name):
        return None
    return registrable_name(name)


def same_site(first_url: str, second_url: str) -> bool:
    first, second = urlsplit(first_url).hostname, urlsplit(second_url).hostname
    if not first or not second:
        return False
    site = site_of(first)
    return site is not None and site == site_of(second)


def without_tracking(url: str) -> str:
    parts = urlsplit(url)
    pairs = parse_qsl(parts.query, keep_blank_values=True)
    kept = [(name, value) for name, value in pairs if not name.startswith(TRACKING_PREFIX)]
    if len(kept) == len(pairs):
        return url
    return urlunsplit(parts._replace(query=urlencode(kept, safe="!,/:")))


def _is_address(name: str) -> bool:
    try:
        ipaddress.ip_address(name)
    except ValueError:
        return False
    return True


def clipped(text: str, limit: int = MEDIA_TEXT_MAX_CHARS) -> str:
    single = " ".join(text.split())
    if len(single) <= limit:
        return single
    cut = single[: limit - 1].rsplit(" ", 1)[0].rstrip(" ,;:")
    return f"{cut}{ELLIPSIS}"
