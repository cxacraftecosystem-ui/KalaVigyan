from __future__ import annotations

import io
import math
import struct
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from functools import cache
from types import ModuleType
from typing import TYPE_CHECKING

from app.core.errors import InvalidInput

from .image_intake_types import PNG, WEBP

if TYPE_CHECKING:
    from PIL.Image import Image as Picture

__all__ = [
    "DECODED_BYTES_MAX",
    "FINGERPRINT_BITS",
    "IMAGE_PIXELS_MAX",
    "PREVIEW_MIME",
    "PREVIEW_SIDE",
    "Converted",
    "Pixels",
    "converted",
    "fingerprint_distance",
    "pixels_of",
    "sized",
]

IMAGE_PIXELS_MAX = 40_000_000
DECODED_BYTES_MAX = 128 * 1024 * 1024
FINGERPRINT_BITS = 64
HASH_SIDE = 32
HASH_LOW = 8
PREVIEW_SIDE = 768
PREVIEW_MIME = "image/jpeg"
PREVIEW_QUALITY = 80
WEBP_QUALITY = 90
WEBP_METHOD = 4
SAVED_AS = {WEBP: "WEBP", PNG: "PNG"}
OPENED_FORMATS = ("PNG", "JPEG", "WEBP", "AVIF", "GIF", "HEIF", "TIFF", "BMP")
BAND_BYTES = {"I": 4, "F": 4, "I;16": 2, "I;16B": 2, "I;16L": 2, "I;16N": 2}
DIRECT_MODES = frozenset({"L", "LA", "RGB", "RGBA"})
CLEAR_MODES = frozenset({"LA", "RGBA", "PA"})
WHITE = (255, 255, 255)
UNREADABLE = "The picture could not be read: its data is broken or it is not the format it claims"
DECODE_FAILURES: tuple[type[Exception], ...] = (
    OSError,
    ValueError,
    SyntaxError,
    EOFError,
    IndexError,
    TypeError,
    RuntimeError,
    struct.error,
)
COSINES = tuple(
    tuple(math.cos(math.pi * (2 * n + 1) * k / (2 * HASH_SIDE)) for n in range(HASH_SIDE))
    for k in range(HASH_LOW)
)


@dataclass(frozen=True)
class Pixels:
    fingerprint: int
    preview: bytes


@dataclass(frozen=True)
class Converted:
    data: bytes
    mime: str
    width: int
    height: int


def sized(data: bytes) -> tuple[int, int]:
    with _opened(data) as image:
        return image.size


def converted(data: bytes, mime: str) -> Converted:
    with _opened(data) as image:
        _loaded(image)
        profile = image.info.get("icc_profile")
        _operations().exif_transpose(image, in_place=True)
        flat = _flat(image)
        flat.info = {}
        out = io.BytesIO()
        options = {"icc_profile": profile} if profile else {}
        if mime == WEBP:
            options |= {"quality": WEBP_QUALITY, "method": WEBP_METHOD}
        flat.save(out, SAVED_AS[mime], **options)
        return Converted(out.getvalue(), mime, flat.width, flat.height)


def pixels_of(data: bytes) -> Pixels:
    with _opened(data) as image:
        if image.format == "JPEG":
            image.draft("RGB", (PREVIEW_SIDE, PREVIEW_SIDE))
        _loaded(image)
        _operations().exif_transpose(image, in_place=True)
        source = _on_white(image if image.mode in DIRECT_MODES else _flat(image))
        return Pixels(fingerprint=_fingerprint(source), preview=_preview(source))


def fingerprint_distance(first: int, second: int) -> int:
    return (first ^ second).bit_count()


@cache
def _pillow() -> ModuleType:
    from PIL import Image
    from pillow_heif import register_heif_opener

    Image.MAX_IMAGE_PIXELS = IMAGE_PIXELS_MAX
    register_heif_opener(thumbnails=False)
    return Image


def _operations() -> ModuleType:
    _pillow()
    from PIL import ImageOps

    return ImageOps


def _failures() -> tuple[type[Exception], ...]:
    return (*DECODE_FAILURES, _pillow().DecompressionBombError)


@contextmanager
def _opened(data: bytes) -> Iterator[Picture]:
    try:
        image = _pillow().open(io.BytesIO(data), formats=OPENED_FORMATS)
    except _failures():
        raise InvalidInput(UNREADABLE) from None
    with image:
        _refuse_large(image)
        yield image


def _refuse_large(image: Picture) -> None:
    pixels = image.width * image.height
    if pixels > IMAGE_PIXELS_MAX:
        raise InvalidInput(
            f"A contributed picture is at most {IMAGE_PIXELS_MAX // 1_000_000} million pixels, not {pixels:,}"
        )
    decoded = pixels * len(image.getbands()) * BAND_BYTES.get(image.mode, 1)
    if decoded > DECODED_BYTES_MAX:
        raise InvalidInput(
            f"Decoding this picture would take more than {DECODED_BYTES_MAX // (1024 * 1024)} MB of memory"
        )


def _loaded(image: Picture) -> None:
    try:
        image.load()
    except _failures():
        raise InvalidInput(UNREADABLE) from None


def _flat(image: Picture) -> Picture:
    clear = image.mode in CLEAR_MODES or "transparency" in image.info
    try:
        return image.convert("RGBA" if clear else "RGB")
    except ValueError, OSError:
        raise InvalidInput(f"A picture in the colour mode {image.mode} cannot be shown") from None


def _on_white(image: Picture) -> Picture:
    scale = min(1.0, PREVIEW_SIDE / max(image.width, image.height))
    size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
    pillow = _pillow()
    small = image.resize(size, pillow.Resampling.LANCZOS, reducing_gap=3.0)
    if small.mode not in CLEAR_MODES:
        return small.convert("RGB")
    ground = pillow.new("RGB", small.size, WHITE)
    ground.paste(small.convert("RGBA"), mask=small.getchannel("A"))
    return ground


def _preview(image: Picture) -> bytes:
    out = io.BytesIO()
    image.save(out, "JPEG", quality=PREVIEW_QUALITY)
    return out.getvalue()


def _fingerprint(image: Picture) -> int:
    grey = image.convert("L").resize((HASH_SIDE, HASH_SIDE), _pillow().Resampling.LANCZOS)
    values = list(grey.tobytes())
    rows = [values[at : at + HASH_SIDE] for at in range(0, HASH_SIDE * HASH_SIDE, HASH_SIDE)]
    across = [[sum(c * v for c, v in zip(cosine, row, strict=True)) for cosine in COSINES] for row in rows]
    low = [
        sum(COSINES[k][n] * across[n][j] for n in range(HASH_SIDE))
        for k in range(HASH_LOW)
        for j in range(HASH_LOW)
    ]
    ordered = sorted(low)
    middle = (ordered[len(low) // 2 - 1] + ordered[len(low) // 2]) / 2
    bits = 0
    for value in low:
        bits = (bits << 1) | (value > middle)
    return bits
