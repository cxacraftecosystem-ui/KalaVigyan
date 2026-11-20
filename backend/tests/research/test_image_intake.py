import zlib

import pytest

from app.core.errors import InvalidInput
from app.research.image_intake import IMAGE_BYTES_MAX, inspected_image

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
AI_SOURCE = b"http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia"
GPS_NOTE = b"GPS 23.25N 69.67E"


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    return len(payload).to_bytes(4) + kind + payload + zlib.crc32(kind + payload).to_bytes(4)


def _png(width: int, height: int, *extra: bytes) -> bytes:
    header = width.to_bytes(4) + height.to_bytes(4) + bytes([8, 2, 0, 0, 0])
    return (
        PNG_SIGNATURE
        + _png_chunk(b"IHDR", header)
        + b"".join(extra)
        + _png_chunk(b"IDAT", b"\x78\x9c\x03\x00")
        + _png_chunk(b"IEND", b"")
    )


def _jpeg_segment(marker: int, body: bytes) -> bytes:
    return bytes([0xFF, marker]) + (len(body) + 2).to_bytes(2) + body


def _little_exif(orientation: int) -> bytes:
    entries = [
        (0x0112).to_bytes(2, "little")
        + (3).to_bytes(2, "little")
        + (1).to_bytes(4, "little")
        + orientation.to_bytes(2, "little")
        + bytes(2),
        (0x8825).to_bytes(2, "little")
        + (4).to_bytes(2, "little")
        + (1).to_bytes(4, "little")
        + (38).to_bytes(4, "little"),
    ]
    tiff = b"II*\x00" + (8).to_bytes(4, "little") + (2).to_bytes(2, "little") + b"".join(entries) + bytes(4)
    return b"Exif\x00\x00" + tiff + GPS_NOTE


def _jpeg(width: int, height: int, *extra: bytes) -> bytes:
    frame = bytes([8]) + height.to_bytes(2) + width.to_bytes(2) + bytes([1, 1, 0x11, 0])
    return (
        b"\xff\xd8"
        + _jpeg_segment(0xE0, b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00")
        + b"".join(extra)
        + _jpeg_segment(0xDB, bytes(65))
        + _jpeg_segment(0xC0, frame)
        + _jpeg_segment(0xDA, bytes([1, 1, 0, 0, 0x3F, 0]))
        + b"\x12\x34\x56"
        + b"\xff\xd9"
    )


def _webp_chunk(kind: bytes, payload: bytes) -> bytes:
    padded = payload + (b"\x00" if len(payload) % 2 else b"")
    return kind + len(payload).to_bytes(4, "little") + padded


def _webp(width: int, height: int, *extra: bytes) -> bytes:
    flags = bytes([0x08 | 0x04 | 0x10])
    canvas = (width - 1).to_bytes(3, "little") + (height - 1).to_bytes(3, "little")
    bits = (width - 1) | ((height - 1) << 14)
    lossless = bytes([0x2F]) + bits.to_bytes(4, "little") + b"\x00\x00"
    body = (
        b"WEBP"
        + _webp_chunk(b"VP8X", flags + bytes(3) + canvas)
        + b"".join(extra)
        + _webp_chunk(b"VP8L", lossless)
    )
    return b"RIFF" + len(body).to_bytes(4, "little") + body


def test_a_png_keeps_its_picture_and_loses_its_text_and_is_marked_ai_made_by_its_own_metadata() -> None:
    made = _png(800, 600, _png_chunk(b"tEXt", b"Comment\x00" + GPS_NOTE), _png_chunk(b"iTXt", AI_SOURCE))
    image = inspected_image(made)
    assert (image.mime, image.width, image.height, image.ai_marked) == ("image/png", 800, 600, True)
    assert image.data == _png(800, 600)
    assert GPS_NOTE not in image.data and AI_SOURCE not in image.data


def test_a_png_without_the_mark_is_not_called_ai_made() -> None:
    assert inspected_image(_png(640, 480)).ai_marked is False


def test_a_jpeg_keeps_only_its_orientation_and_drops_location_and_content_credentials() -> None:
    credentials = _jpeg_segment(0xEB, b"JP\x00\x00jumbc2pa" + AI_SOURCE)
    made = _jpeg(1024, 768, _jpeg_segment(0xE1, _little_exif(6)), credentials, _jpeg_segment(0xFE, GPS_NOTE))
    image = inspected_image(made)
    assert (image.mime, image.width, image.height, image.ai_marked) == ("image/jpeg", 1024, 768, True)
    assert GPS_NOTE not in image.data and AI_SOURCE not in image.data and b"c2pa" not in image.data
    orientation = b"Exif\x00\x00MM\x00\x2a" + (8).to_bytes(4) + (1).to_bytes(2) + b"\x01\x12\x00\x03"
    assert orientation + (1).to_bytes(4) + (6).to_bytes(2) in image.data
    assert image.data.endswith(b"\x12\x34\x56\xff\xd9")


def test_a_jpeg_without_exif_gains_no_orientation() -> None:
    image = inspected_image(_jpeg(400, 400))
    assert b"Exif" not in image.data and image.ai_marked is False


def test_a_webp_loses_its_exif_and_xmp_and_their_flags_and_keeps_a_true_riff_size() -> None:
    made = _webp(1200, 900, _webp_chunk(b"EXIF", GPS_NOTE), _webp_chunk(b"XMP ", AI_SOURCE))
    image = inspected_image(made)
    assert (image.mime, image.width, image.height, image.ai_marked) == ("image/webp", 1200, 900, True)
    assert GPS_NOTE not in image.data and AI_SOURCE not in image.data
    assert image.data[20] == 0x10
    assert int.from_bytes(image.data[4:8], "little") == len(image.data) - 8


@pytest.mark.parametrize(
    "made",
    [
        b"GIF89a" + bytes(40),
        _png(100, 100),
        _png(9000, 400),
        _png(800, 600)[:-12],
        _jpeg(800, 600).replace(b"\xff\xc0", b"\xff\xe5"),
        b"RIFF" + bytes(4) + b"WEBP",
    ],
    ids=[
        "broken-gif",
        "too-small",
        "too-wide",
        "png-without-end",
        "jpeg-without-frame",
        "webp-without-image",
    ],
)
def test_what_is_not_a_whole_picture_of_a_fair_size_is_refused(made: bytes) -> None:
    with pytest.raises(InvalidInput):
        inspected_image(made)


def test_a_file_over_the_size_limit_is_refused_before_it_is_read() -> None:
    with pytest.raises(InvalidInput):
        inspected_image(_png(800, 600) + bytes(IMAGE_BYTES_MAX))
