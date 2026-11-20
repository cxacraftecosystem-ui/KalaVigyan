from __future__ import annotations

from io import BytesIO
from pathlib import Path

__all__ = ["fitted_size", "web_mark"]


def fitted_size(size: tuple[int, int], width: int) -> tuple[int, int]:
    source_width, source_height = size
    if source_width <= width:
        return size
    return width, max(1, round(source_height * width / source_width))


def web_mark(source: Path, width: int, quality: int) -> tuple[bytes, tuple[int, int]]:
    from PIL import Image

    with Image.open(source) as opened:
        image = opened.convert("RGBA")
    box = image.getchannel("A").getbbox()
    if box:
        image = image.crop(box)
    size = fitted_size(image.size, width)
    resized = image.resize(size, Image.Resampling.LANCZOS)
    out = BytesIO()
    resized.save(out, "WEBP", lossless=True, quality=quality, method=6)
    return out.getvalue(), size
