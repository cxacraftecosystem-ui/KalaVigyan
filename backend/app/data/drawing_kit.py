from __future__ import annotations

import json
from collections.abc import Callable
from functools import cache
from typing import Any

from .contributor_kit import design_tokens
from .craft_master_loader import DATA_DIR
from .design_palette import token_tables, tokens_css

__all__ = [
    "DESIGN_KIT",
    "DRAWING_GUIDE_PATH",
    "DRAWING_GUIDE_URI",
    "GUIDE_ROLES",
    "TOKENS_CSS_URI",
    "design_css",
    "drawing_guide",
]

DRAWING_GUIDE_PATH = DATA_DIR / "design" / "drawing-guide.md"
DRAWING_GUIDE_URI = "kalavigyan://design/drawing.md"
TOKENS_CSS_URI = "kalavigyan://design/tokens.css"
ROLES_SLOT = "{{roles}}"
TYPE_SLOT = "{{type}}"
GUIDE_ROLES = (
    "ground",
    "raised",
    "sunk",
    "rule",
    "rule-strong",
    "ink-1",
    "ink-2",
    "ink-3",
    "chart-axis-text",
    "chart-axis-line",
    "chart-grid",
    "chart-series",
    "chart-emph",
    "chart-reference",
    "chart-annotation",
    "chart-differ",
    "series-rain",
    "series-heat",
    "series-count",
    "map-land",
    "map-water",
    "map-coast",
    "map-river",
    "map-salt",
    "map-label",
    "terracotta",
    "madder",
    "indigo",
)
TYPE_ROLES = ("caption", "label", "ui", "h4", "figcaption", "body-sm", "body", "lede", "h3", "h2", "h1")
MARKDOWN = "text/markdown"
CSS = "text/css"


@cache
def drawing_guide() -> str:
    guide = DRAWING_GUIDE_PATH.read_bytes().decode("utf-8")
    return guide.replace(ROLES_SLOT, token_tables(GUIDE_ROLES)).replace(TYPE_SLOT, _type_table())


@cache
def design_css() -> str:
    return tokens_css()


def _type_table() -> str:
    tokens: dict[str, Any] = json.loads(design_tokens())
    families = tokens["type"]["families"]
    lines = ["| Token | Face | 360 px | 1440 px | Weight | Line height |", "|---|---|---|---|---|---|"]
    for name in TYPE_ROLES:
        size = tokens["type"]["scale"][name]
        face = families[size["family"]]["stack"].split(",")[0].strip('"')
        lines.append(
            f"| `{size['cssVar']}` | {face} | {size['phone']} | {size['desktop']} | {size['weight']} | "
            f"{size['lineHeight']} |"
        )
    return "\n".join(lines)


DESIGN_KIT: tuple[tuple[str, str, str, str, str, Callable[[], str]], ...] = (
    (
        TOKENS_CSS_URI,
        "kalavigyan-design-css",
        "The KalaVigyan design tokens as CSS",
        "Every colour role, ramp, map and specimen colour as a CSS custom property in the light, dark and "
        "high-contrast themes, with the type faces and sizes, for an agent that draws KalaVigyan's "
        "knowledge in its own chat: paste it into a page and name roles as var(--ink-1).",
        CSS,
        design_css,
    ),
    (
        DRAWING_GUIDE_URI,
        "kalavigyan-drawing",
        "Drawing for KalaVigyan",
        "A short guide for an agent that draws a chart, diagram or page of KalaVigyan's knowledge itself, "
        "or delivers a drawing: the roles and their colours in four themes, the type scale and faces, "
        "the 12 px floor, captions and credits, and what indigo, madder and data colours may mean.",
        MARKDOWN,
        drawing_guide,
    ),
)
