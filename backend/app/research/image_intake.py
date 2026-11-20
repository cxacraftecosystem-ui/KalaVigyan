from __future__ import annotations

from dataclasses import dataclass

from app.core.errors import InvalidInput

from .image_intake_avif import MetadataUnplaced, avif_without_metadata
from .image_intake_pixels import converted, sized
from .image_intake_svg import clean_svg
from .image_intake_types import (
    ACCEPTED_TYPES,
    AVIF,
    CONVERTED_TYPES,
    IMAGE_BYTES_MAX,
    JPEG,
    JPEG_START,
    PNG,
    PNG_SIGNATURE,
    RIFF,
    SVG,
    WEBP,
    WEBP_FORM,
    received_type,
)

__all__ = [
    "ACCEPTED_TYPES",
    "AI_SOURCE_MARK",
    "AVIF",
    "CONVERTED_TYPES",
    "IMAGE_BYTES_MAX",
    "IMAGE_SIDE_MAX",
    "IMAGE_SIDE_MIN",
    "PNG_SIGNATURE",
    "SVG",
    "InspectedImage",
    "inspected_image",
    "png_size",
    "received_type",
]

IMAGE_SIDE_MIN = 320
IMAGE_SIDE_MAX = 8192
AI_SOURCE_MARK = b"trainedAlgorithmicMedia"
PNG_HEADER = b"IHDR"

PNG_KEPT = frozenset(
    {
        b"IHDR",
        b"PLTE",
        b"IDAT",
        b"IEND",
        b"tRNS",
        b"gAMA",
        b"cHRM",
        b"sRGB",
        b"iCCP",
        b"sBIT",
        b"pHYs",
        b"bKGD",
    }
)
PNG_END = b"IEND"

JPEG_SCAN = 0xDA
JPEG_EXIF_APP = 0xE1
JPEG_KEPT = frozenset({0xC4, 0xCC, 0xDB, 0xDD, 0xE0, 0xE2, 0xEE})
JPEG_FRAMES = frozenset({0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF})
EXIF_HEADER = b"Exif\x00\x00"
ORIENTATION_TAG = 0x0112
SHORT_TYPE = 3

WEBP_EXTENDED = b"VP8X"
WEBP_LOSSY = b"VP8 "
WEBP_LOSSLESS = b"VP8L"
WEBP_DROPPED = frozenset({b"EXIF", b"XMP ", b"C2PA"})
WEBP_METADATA_FLAGS = 0x08 | 0x04
WEBP_LOSSLESS_SIGNATURE = 0x2F
WEBP_SIDE_BITS = 0x3FFF


@dataclass(frozen=True)
class InspectedImage:
    data: bytes
    mime: str
    width: int
    height: int
    ai_marked: bool
    received: str

    @property
    def vector(self) -> bool:
        return self.mime == SVG


def inspected_image(data: bytes) -> InspectedImage:
    if len(data) > IMAGE_BYTES_MAX:
        raise InvalidInput(f"A contributed image is at most {IMAGE_BYTES_MAX // (1024 * 1024)} MB")
    received = received_type(data)
    marked = AI_SOURCE_MARK in data
    if received == SVG:
        drawing = clean_svg(data)
        return InspectedImage(drawing.data, SVG, drawing.width, drawing.height, marked, received)
    clean, mime, (width, height) = _cleaned(data, received)
    if min(width, height) < IMAGE_SIDE_MIN or max(width, height) > IMAGE_SIDE_MAX:
        raise InvalidInput(
            f"A contributed image is {IMAGE_SIDE_MIN} to {IMAGE_SIDE_MAX} pixels a side, not {width} by {height}"
        )
    if len(clean) > IMAGE_BYTES_MAX:
        raise InvalidInput(
            f"Converted, this picture is over {IMAGE_BYTES_MAX // (1024 * 1024)} MB; send a smaller one"
        )
    return InspectedImage(clean, mime, width, height, marked, received)


def _cleaned(data: bytes, received: str) -> tuple[bytes, str, tuple[int, int]]:
    if received == PNG:
        clean = _png_without_metadata(data)
        return clean, PNG, png_size(clean)
    if received == JPEG:
        clean, size = _jpeg_without_metadata(data)
        return clean, JPEG, size
    if received == WEBP:
        clean, size = _webp_without_metadata(data)
        return clean, WEBP, size
    if received == AVIF:
        kept = _avif_kept(data)
        if kept is not None:
            return kept
    made = converted(data, CONVERTED_TYPES.get(received, WEBP))
    return made.data, made.mime, (made.width, made.height)


def _avif_kept(data: bytes) -> tuple[bytes, str, tuple[int, int]] | None:
    try:
        clean = avif_without_metadata(data)
        return clean, AVIF, sized(clean)
    except MetadataUnplaced, InvalidInput:
        return None


def _png_without_metadata(data: bytes) -> bytes:
    kept = [PNG_SIGNATURE]
    position = len(PNG_SIGNATURE)
    while position + 12 <= len(data):
        length = int.from_bytes(data[position : position + 4])
        kind = data[position + 4 : position + 8]
        end = position + 12 + length
        if end > len(data):
            break
        if kind in PNG_KEPT:
            kept.append(data[position:end])
        if kind == PNG_END:
            return b"".join(kept)
        position = end
    raise InvalidInput("The PNG is cut short")


def _jpeg_without_metadata(data: bytes) -> tuple[bytes, tuple[int, int]]:
    kept = [JPEG_START]
    size: tuple[int, int] | None = None
    position = len(JPEG_START)
    while position + 4 <= len(data) and data[position] == 0xFF:
        marker = data[position + 1]
        if marker == 0xFF:
            position += 1
            continue
        if marker == JPEG_SCAN:
            kept.append(data[position:])
            if size is None:
                break
            return b"".join(kept), size
        end = position + 2 + int.from_bytes(data[position + 2 : position + 4])
        segment = data[position:end]
        if marker in JPEG_FRAMES and len(segment) >= 9:
            size = (int.from_bytes(segment[7:9]), int.from_bytes(segment[5:7]))
        if marker in JPEG_KEPT or marker in JPEG_FRAMES:
            kept.append(segment)
        elif marker == JPEG_EXIF_APP:
            kept.extend(_orientation_only(segment))
        position = end
    raise InvalidInput("The JPEG's segments are broken or it has no frame")


def _orientation_only(segment: bytes) -> list[bytes]:
    body = segment[4:]
    if not body.startswith(EXIF_HEADER):
        return []
    tiff = body[len(EXIF_HEADER) :]
    order = "little" if tiff[:2] == b"II" else "big"
    if len(tiff) < 8:
        return []
    first = int.from_bytes(tiff[4:8], order)
    count = int.from_bytes(tiff[first : first + 2], order) if first + 2 <= len(tiff) else 0
    for index in range(count):
        entry = tiff[first + 2 + 12 * index : first + 14 + 12 * index]
        if len(entry) == 12 and int.from_bytes(entry[:2], order) == ORIENTATION_TAG:
            return [_orientation_segment(int.from_bytes(entry[8:10], order))]
    return []


def _orientation_segment(orientation: int) -> bytes:
    entry = ORIENTATION_TAG.to_bytes(2, "big") + SHORT_TYPE.to_bytes(2, "big") + (1).to_bytes(4, "big")
    entry += orientation.to_bytes(2, "big") + bytes(2)
    tiff = b"MM\x00\x2a" + (8).to_bytes(4, "big") + (1).to_bytes(2, "big") + entry + bytes(4)
    body = EXIF_HEADER + tiff
    return bytes([0xFF, JPEG_EXIF_APP]) + (len(body) + 2).to_bytes(2, "big") + body


def _webp_without_metadata(data: bytes) -> tuple[bytes, tuple[int, int]]:
    chunks: list[bytes] = []
    size: tuple[int, int] | None = None
    position = 12
    while position + 8 <= len(data):
        kind = data[position : position + 4]
        length = int.from_bytes(data[position + 4 : position + 8], "little")
        end = position + 8 + length + (length & 1)
        if end > len(data):
            raise InvalidInput("The WebP is cut short")
        payload = data[position + 8 : position + 8 + length]
        size = size or _webp_size(kind, payload)
        if kind == WEBP_EXTENDED and length >= 1:
            chunks.append(data[position : position + 8] + bytes([payload[0] & ~WEBP_METADATA_FLAGS & 0xFF]))
            chunks.append(data[position + 9 : end])
        elif kind not in WEBP_DROPPED:
            chunks.append(data[position:end])
        position = end
    if size is None:
        raise InvalidInput("The WebP has no image")
    body = WEBP_FORM + b"".join(chunks)
    return RIFF + len(body).to_bytes(4, "little") + body, size


def _webp_size(kind: bytes, payload: bytes) -> tuple[int, int] | None:
    if kind == WEBP_EXTENDED and len(payload) >= 10:
        return int.from_bytes(payload[4:7], "little") + 1, int.from_bytes(payload[7:10], "little") + 1
    if kind == WEBP_LOSSY and len(payload) >= 10:
        return (
            int.from_bytes(payload[6:8], "little") & WEBP_SIDE_BITS,
            int.from_bytes(payload[8:10], "little") & WEBP_SIDE_BITS,
        )
    if kind == WEBP_LOSSLESS and len(payload) >= 5 and payload[0] == WEBP_LOSSLESS_SIGNATURE:
        bits = int.from_bytes(payload[1:5], "little")
        return (bits & WEBP_SIDE_BITS) + 1, ((bits >> 14) & WEBP_SIDE_BITS) + 1
    return None


def png_size(data: bytes) -> tuple[int, int]:
    if len(data) < 24 or not data.startswith(PNG_SIGNATURE) or data[12:16] != PNG_HEADER:
        raise InvalidInput("The image is not a PNG")
    width = int.from_bytes(data[16:20])
    height = int.from_bytes(data[20:24])
    if width < 1 or height < 1:
        raise InvalidInput("The PNG has no size")
    return width, height
