from __future__ import annotations

import hashlib
from collections.abc import Mapping
from functools import cache
from typing import Any

from app.data.contributor_kit import design_tokens
from app.data.design_palette import THEMES, design_palettes, ui_face
from app.research.component_specs_general import GENERAL_DRAWING
from app.research.drawing_spec_rules import THEMES_KEY
from app.research.drawing_themes import themed_svg
from app.research.image_intake_svg import SVG

__all__ = [
    "THEME_PATTERN",
    "picture_version",
    "themed_markup",
    "themed_picture",
    "themed_spec",
    "token_set_hash",
]

SVG_KEY = "svg"
THEME_PATTERN = "^(" + "|".join(THEMES) + ")$"


def themed_markup(markup: str, theme: str) -> str:
    return themed_svg(markup, design_palettes()[theme], ui_face())


def themed_spec(kind: str, spec: Mapping[str, Any]) -> dict[str, Any]:
    markup = spec.get(SVG_KEY)
    if kind != GENERAL_DRAWING or not isinstance(markup, str):
        return dict(spec)
    return {**spec, THEMES_KEY: {theme: themed_markup(markup, theme) for theme in THEMES}}


@cache
def token_set_hash() -> str:
    return hashlib.sha256(design_tokens().encode("utf-8")).hexdigest()


def picture_version(sha256: str, mime: str, theme: str | None) -> str:
    if mime != SVG or theme not in (None, *THEMES):
        return sha256
    shown = theme or THEMES[0]
    return hashlib.sha256(f"{sha256}:{shown}:{token_set_hash()}".encode()).hexdigest()


def themed_picture(data: bytes, mime: str, theme: str | None) -> bytes:
    if mime != SVG or theme not in (None, *THEMES):
        return data
    return themed_markup(data.decode("utf-8"), theme or THEMES[0]).encode("utf-8")
