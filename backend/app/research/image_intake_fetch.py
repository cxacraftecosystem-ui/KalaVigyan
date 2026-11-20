from __future__ import annotations

import base64
import binascii
import re
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from pydantic import Field

from app.core.errors import InvalidInput

from .base import ContractModel, HttpsUrl
from .image_intake_types import IMAGE_BYTES_MAX

__all__ = [
    "FINAL_URL_HEADER",
    "IMAGE_BASE64_BYTES_MAX",
    "PICTURE_FETCH_ACCEPT",
    "PICTURE_FETCH_PATH",
    "PICTURE_FETCH_TIMEOUT_SECONDS",
    "FetchedPicture",
    "PictureFetchRequest",
    "PictureFetcher",
    "base64_chars_max",
    "decoded_base64",
]

PICTURE_FETCH_PATH = "/fetch-picture"
PICTURE_FETCH_TIMEOUT_SECONDS = 15.0
PICTURE_FETCH_ACCEPT = "image/avif,image/webp,image/png,image/jpeg,image/*;q=0.8,*/*;q=0.1"
FINAL_URL_HEADER = "X-Final-Url"
IMAGE_BASE64_BYTES_MAX = 6 * 1024 * 1024
DATA_URI = re.compile(r"^data:[a-z0-9.+/-]+;base64,", re.IGNORECASE)
SPACES = re.compile(r"\s+")


def base64_chars_max(decoded_max: int) -> int:
    return 4 * -(-decoded_max // 3)


class PictureFetchRequest(ContractModel):
    url: HttpsUrl
    max_bytes: int = Field(default=IMAGE_BYTES_MAX, gt=0, le=IMAGE_BYTES_MAX)


@dataclass(frozen=True)
class FetchedPicture:
    url: str
    final_url: str
    content_type: str
    data: bytes


@runtime_checkable
class PictureFetcher(Protocol):
    async def fetch_picture(self, url: str) -> FetchedPicture: ...


def decoded_base64(text: str, *, limit: int = IMAGE_BASE64_BYTES_MAX) -> bytes:
    body = SPACES.sub("", DATA_URI.sub("", text.strip(), count=1))
    if len(body) > base64_chars_max(limit):
        raise InvalidInput(
            f"A picture sent in the call is at most {limit // (1024 * 1024)} MB; give its link instead"
        )
    try:
        return base64.b64decode(body, validate=True)
    except binascii.Error, ValueError:
        raise InvalidInput("image_base64 is not valid base64") from None
