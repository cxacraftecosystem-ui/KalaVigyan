from __future__ import annotations

from types import MappingProxyType

from app.core.errors import InvalidInput

from .image_intake_avif import AVIF, AVIF_BRANDS, HEIF_BRANDS, file_brands
from .image_intake_svg import SVG, looks_like_svg

__all__ = [
    "ACCEPTED_TYPES",
    "AVIF",
    "BMP",
    "CONVERTED_TYPES",
    "GIF",
    "HEIC",
    "HEIF",
    "IMAGE_BYTES_MAX",
    "JPEG",
    "JPEG_START",
    "KEPT_TYPES",
    "NOT_A_PICTURE",
    "PNG",
    "PNG_SIGNATURE",
    "RIFF",
    "SVG",
    "TIFF",
    "WEBP",
    "WEBP_FORM",
    "received_type",
]

IMAGE_BYTES_MAX = 10 * 1024 * 1024
PNG = "image/png"
JPEG = "image/jpeg"
WEBP = "image/webp"
GIF = "image/gif"
HEIC = "image/heic"
HEIF = "image/heif"
TIFF = "image/tiff"
BMP = "image/bmp"
KEPT_TYPES = (PNG, JPEG, WEBP, AVIF)
CONVERTED_TYPES = MappingProxyType({GIF: PNG, HEIC: WEBP, HEIF: WEBP, TIFF: WEBP, BMP: WEBP})
ACCEPTED_TYPES = (*KEPT_TYPES, *CONVERTED_TYPES, SVG)
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
JPEG_START = b"\xff\xd8"
RIFF = b"RIFF"
WEBP_FORM = b"WEBP"
HEIC_BRANDS = frozenset({b"heic", b"heix", b"heim", b"heis"})
GIF_SIGNATURES = (b"GIF87a", b"GIF89a")
TIFF_SIGNATURES = (b"II*\x00", b"MM\x00*")
BMP_SIGNATURE = b"BM"
NOT_A_PICTURE = "A contributed picture is a PNG, JPEG, WebP, AVIF, GIF, HEIC, HEIF, TIFF, BMP or SVG file"


def received_type(data: bytes) -> str:
    if data.startswith(PNG_SIGNATURE):
        return PNG
    if data.startswith(JPEG_START):
        return JPEG
    if data[:4] == RIFF and data[8:12] == WEBP_FORM:
        return WEBP
    brands = file_brands(data)
    if brands & AVIF_BRANDS:
        return AVIF
    if brands & HEIF_BRANDS:
        return HEIC if brands & HEIC_BRANDS else HEIF
    if data.startswith(GIF_SIGNATURES):
        return GIF
    if data.startswith(TIFF_SIGNATURES):
        return TIFF
    if data.startswith(BMP_SIGNATURE):
        return BMP
    if looks_like_svg(data):
        return SVG
    raise InvalidInput(NOT_A_PICTURE)
