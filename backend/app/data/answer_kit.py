from __future__ import annotations

import base64
import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from functools import lru_cache
from typing import Any

from .contributor_kit import design_tokens
from .craft_master_loader import DATA_DIR
from .design_palette import THEMES, four_themes_css, type_css

__all__ = [
    "ANSWER_KIT_PATH",
    "ANSWER_VIEW_PATH",
    "KIT_COLOURS",
    "KIT_FONTS",
    "SCRIPT_HASH_SLOT",
    "THEME_SLOT",
    "TOKENS_SLOT",
    "answer_kit",
    "answer_view",
    "script_hash",
    "theme_css",
]

ANSWER_KIT_PATH = DATA_DIR / "design" / "answer-kit.md"
ANSWER_VIEW_PATH = DATA_DIR / "design" / "answer-view.html"
TOKENS_SLOT = "{{tokens}}"
THEME_SLOT = "__KV_THEME__"
SCRIPT_HASH_SLOT = "__KV_SCRIPT_HASH__"
KIT_COLOURS = (
    "ground",
    "raised",
    "sunk",
    "rule",
    "rule-strong",
    "ink-1",
    "ink-2",
    "ink-3",
    "indigo",
    "indigo-hover",
    "indigo-wash",
    "on-indigo",
    "madder",
    "turmeric-wash",
)
KIT_FONTS = ("headline", "reading", "ui")
SCRIPT = re.compile(r"<script>(?P<body>.*?)</script>", re.DOTALL)


@lru_cache(maxsize=1)
def answer_kit() -> str:
    spec = ANSWER_KIT_PATH.read_bytes().decode("utf-8")
    return spec.replace(TOKENS_SLOT, _token_tables(_tokens()))


@lru_cache(maxsize=1)
def answer_view() -> str:
    page = ANSWER_VIEW_PATH.read_bytes().decode("utf-8")
    return page.replace(THEME_SLOT, theme_css(_tokens())).replace(SCRIPT_HASH_SLOT, script_hash(page))


def script_hash(page: str) -> str:
    found = SCRIPT.findall(page)
    if len(found) != 1:
        raise ValueError(f"the answer view holds {len(found)} scripts, not one")
    digest = hashlib.sha256(found[0].encode("utf-8")).digest()
    return f"sha256-{base64.b64encode(digest).decode('ascii')}"


def theme_css(tokens: Mapping[str, Any]) -> str:
    colours = {theme: _colours(tokens, theme) for theme in THEMES}
    return f":root{{{type_css(tokens)}}}" + four_themes_css(colours)


def _tokens() -> dict[str, Any]:
    return json.loads(design_tokens())


def _colours(tokens: Mapping[str, Any], theme: str) -> str:
    return "".join(
        f"{tokens['color'][name]['alias']}:{tokens['color'][name][theme]['hex']};" for name in KIT_COLOURS
    )


def _token_tables(tokens: Mapping[str, Any]) -> str:
    colours = _table(
        ("Token", "Use", "Light", "Dark"),
        (
            (
                f"`{tokens['color'][name]['alias']}`",
                tokens["color"][name]["role"],
                tokens["color"][name]["light"]["hex"],
                tokens["color"][name]["dark"]["hex"],
            )
            for name in KIT_COLOURS
        ),
    )
    fonts = _table(
        ("Face", "Stack"),
        ((name, tokens["type"]["families"][name]["stack"].replace("|", "/")) for name in KIT_FONTS),
    )
    return f"{colours}\n\n{fonts}"


def _table(head: tuple[str, ...], rows: Iterable[tuple[str, ...]]) -> str:
    lines = [f"| {' | '.join(head)} |", f"|{'---|' * len(head)}"]
    lines += [f"| {' | '.join(str(cell).replace('|', '/') for cell in row)} |" for row in rows]
    return "\n".join(lines)
