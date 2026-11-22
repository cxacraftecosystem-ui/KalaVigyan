import io
import zlib

import pytest
from PIL import Image
from pillow_heif import register_heif_opener

from app.core.errors import InvalidInput
from app.research.image_intake import inspected_image
from app.research.image_intake_pixels import fingerprint_distance, pixels_of
from app.research.image_intake_svg import clean_svg
from app.research.image_screens import NEAR_BITS, NEAR_IDENTICAL_BITS

from ..pictures import AI_SOURCE, picture

MAKER = "TestPhoneMaker"
ORIENTATION = 0x0112
MAKE = 0x010F
SVG_IN = (
    b'<?xml version="1.0"?>'
    b'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
    b'xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" viewBox="0 0 640 480" onload="alert(1)" '
    b'inkscape:export-filename="C:/Users/meera/vat.png">'
    b"<metadata><rdf>Meera Rao</rdf></metadata><script>alert(1)</script>"
    b'<defs><linearGradient id="g"><stop offset="0" stop-color="var(--ink-1)"/></linearGradient></defs>'
    b'<rect width="640" height="480" fill="url(#g)" onclick="steal()"/>'
    b'<use href="#g"/><use xlink:href="https://evil.example/x.svg#a"/>'
    b'<image href="https://evil.example/p.png"/><foreignObject><p>x</p></foreignObject>'
    b'<circle r="5" style="fill:url(https://evil.example/f)"/>'
    b"<style>@import url(https://evil.example/a.css); rect { fill: url(#g) }</style>"
    b"</svg>"
)

register_heif_opener()


def _saved(made: Image.Image, kind: str, **options: object) -> bytes:
    out = io.BytesIO()
    made.save(out, kind, **options)
    return out.getvalue()


def _exif(**tags: object) -> Image.Exif:
    exif = Image.Exif()
    for name, value in tags.items():
        exif[{"orientation": ORIENTATION, "make": MAKE}[name]] = value
    return exif


def _png_header(width: int, height: int, colour_type: int) -> bytes:
    def chunk(kind: bytes, payload: bytes) -> bytes:
        return len(payload).to_bytes(4) + kind + payload + zlib.crc32(kind + payload).to_bytes(4)

    header = width.to_bytes(4) + height.to_bytes(4) + bytes([8, colour_type, 0, 0, 0])
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", b"\x78\x9c\x03\x00")
        + chunk(b"IEND", b"")
    )


def test_a_gif_is_kept_as_a_png_of_its_first_frame() -> None:
    first = Image.new("RGB", (400, 400), (200, 30, 30))
    second = Image.new("RGB", (400, 400), (30, 30, 200))
    image = inspected_image(_saved(first, "GIF", save_all=True, append_images=[second]))
    assert (image.received, image.mime, image.width, image.height) == ("image/gif", "image/png", 400, 400)
    kept = Image.open(io.BytesIO(image.data)).convert("RGB")
    assert kept.getpixel((10, 10)) == (200, 30, 30)


def test_a_heic_is_converted_to_webp_without_its_metadata() -> None:
    made = Image.open(io.BytesIO(picture(900, 700, seed=11)))
    image = inspected_image(_saved(made, "HEIF", exif=_exif(make=MAKER).tobytes()))
    assert (image.received, image.mime, image.width, image.height) == ("image/heic", "image/webp", 900, 700)
    assert MAKER.encode() not in image.data and b"Exif" not in image.data


def test_a_tiff_is_turned_upright_by_its_orientation_and_made_webp() -> None:
    made = Image.open(io.BytesIO(picture(800, 600, seed=12)))
    image = inspected_image(_saved(made, "TIFF", exif=_exif(orientation=6, make=MAKER)))
    assert (image.received, image.mime, image.width, image.height) == ("image/tiff", "image/webp", 600, 800)
    assert MAKER.encode() not in image.data


def test_a_bmp_is_made_webp_at_its_own_size() -> None:
    image = inspected_image(picture(500, 400, seed=13, kind="BMP"))
    assert (image.received, image.mime, image.width, image.height) == ("image/bmp", "image/webp", 500, 400)


def test_an_avif_is_kept_as_it_is_with_its_exif_and_xmp_emptied() -> None:
    made = Image.open(io.BytesIO(picture(640, 480, seed=14)))
    data = _saved(made, "AVIF", exif=_exif(make=MAKER).tobytes(), xmp=AI_SOURCE)
    assert MAKER.encode() in data and AI_SOURCE in data
    image = inspected_image(data)
    assert (image.received, image.mime, image.width, image.height, image.ai_marked) == (
        "image/avif",
        "image/avif",
        640,
        480,
        True,
    )
    assert MAKER.encode() not in image.data and AI_SOURCE not in image.data
    assert len(image.data) == len(data)
    assert Image.open(io.BytesIO(image.data)).size == (640, 480)


def test_an_svg_keeps_its_drawing_and_loses_scripts_handlers_foreign_objects_links_and_metadata() -> None:
    image = inspected_image(SVG_IN)
    assert (image.received, image.mime, image.width, image.height, image.vector) == (
        "image/svg+xml",
        "image/svg+xml",
        640,
        480,
        True,
    )
    text = image.data.decode("utf-8")
    for gone in (
        "script",
        "onload",
        "onclick",
        "foreignObject",
        "evil.example",
        "metadata",
        "Meera",
        "inkscape",
    ):
        assert gone not in text, gone
    for kept in ('fill="url(#g)"', 'href="#g"', "linearGradient", "rect { fill: url(#g) }"):
        assert kept in text, kept


@pytest.mark.parametrize(
    "made",
    [
        b'<!DOCTYPE svg [<!ENTITY a "aaaa">]><svg xmlns="http://www.w3.org/2000/svg">&a;</svg>',
        b'<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>',
        b"<svg xmlns='http://www.w3.org/2000/svg'><rect></svg>",
        b'<html xmlns="http://www.w3.org/1999/xhtml"><svg/></html>',
    ],
    ids=["entities", "no-size", "not-well-formed", "not-an-svg"],
)
def test_an_svg_with_entities_no_size_or_broken_xml_is_refused(made: bytes) -> None:
    with pytest.raises(InvalidInput):
        clean_svg(made)


def test_a_picture_over_forty_million_pixels_is_refused_before_it_is_decoded() -> None:
    with pytest.raises(InvalidInput, match="40 million pixels"):
        pixels_of(_png_header(8000, 8000, 2))


def test_a_picture_whose_decoding_would_pass_the_memory_cap_is_refused() -> None:
    with pytest.raises(InvalidInput, match="128 MB"):
        pixels_of(_png_header(6000, 6000, 6))


def test_a_png_that_does_not_decode_is_refused() -> None:
    with pytest.raises(InvalidInput, match="could not be read"):
        pixels_of(_png_header(800, 600, 2))


def test_the_same_picture_smaller_and_recompressed_keeps_its_fingerprint_and_another_does_not() -> None:
    original = picture(1200, 900, seed=21)
    smaller = Image.open(io.BytesIO(original)).resize((600, 450))
    first = pixels_of(original).fingerprint
    assert fingerprint_distance(first, pixels_of(_saved(smaller, "JPEG", quality=70)).fingerprint) <= (
        NEAR_IDENTICAL_BITS
    )
    assert fingerprint_distance(first, pixels_of(picture(1200, 900, seed=22)).fingerprint) > NEAR_BITS


def test_the_fingerprint_distance_counts_the_bits_that_differ() -> None:
    assert fingerprint_distance(0b1011, 0b0001) == 2
    assert fingerprint_distance(0, (1 << 64) - 1) == 64


def test_the_vision_preview_is_a_jpeg_of_at_most_768_pixels_a_side() -> None:
    preview = Image.open(io.BytesIO(pixels_of(picture(1600, 1200, seed=23)).preview))
    assert (preview.format, preview.size) == ("JPEG", (768, 576))
