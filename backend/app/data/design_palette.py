from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from functools import cache
from types import MappingProxyType
from typing import Any

from .contributor_kit import design_tokens

__all__ = [
    "THEMES",
    "THEME_RULES",
    "design_palettes",
    "four_themes_css",
    "token_tables",
    "tokens_css",
    "type_css",
    "ui_face",
]

THEMES = ("light", "dark", "hcLight", "hcDark")
DARK_THEMES = frozenset({"dark", "hcDark"})
THEME_RULES = (
    (None, ":root", "light"),
    ("(prefers-color-scheme: dark)", ':root:not([data-theme="light"])', "dark"),
    (None, ':root[data-theme="dark"]', "dark"),
    ("(prefers-contrast: more)", ':root:not([data-high-contrast="false"])', "hcLight"),
    (
        "(prefers-contrast: more) and (prefers-color-scheme: dark)",
        ':root:not([data-high-contrast="false"]):not([data-theme="light"])',
        "hcDark",
    ),
    ("(prefers-contrast: more)", ':root[data-theme="dark"]:not([data-high-contrast="false"])', "hcDark"),
    (None, ':root[data-high-contrast="true"]', "hcLight"),
    ("(prefers-color-scheme: dark)", ':root[data-high-contrast="true"]:not([data-theme="light"])', "hcDark"),
    (None, ':root[data-theme="dark"][data-high-contrast="true"]', "hcDark"),
)
TYPE_FAMILIES = ("headline", "reading", "ui", "code")


def _tokens() -> dict[str, Any]:
    return json.loads(design_tokens())


@cache
def design_palettes() -> Mapping[str, Mapping[str, str]]:
    tokens = _tokens()
    return MappingProxyType({theme: MappingProxyType(dict(_palette(tokens, theme))) for theme in THEMES})


def _palette(tokens: Mapping[str, Any], theme: str) -> Iterator[tuple[str, str]]:
    for name, token in tokens["color"].items():
        yield name, token[theme]["hex"]
    dataviz = tokens["dataviz"]
    for group in ("chart", "map"):
        for name, token in dataviz[group].items():
            if isinstance(token, dict) and isinstance(token.get(theme), dict) and "hex" in token[theme]:
                yield name, token[theme]["hex"]
    for ramp, token in dataviz["ramps"].items():
        for step, value in enumerate(token[theme]["steps"], start=1):
            yield f"{ramp}-{step}", value
    categorical = dataviz["categorical"]
    for family, value in categorical[theme]["colors"].items():
        yield f"fam-{family}", value
    yield "fam-other", categorical["other"][theme]
    for name, token in tokens["specimen"].items():
        if isinstance(token, dict) and "hex" in token:
            yield name, token["hex"]


def ui_face() -> str:
    return str(_tokens()["type"]["families"]["ui"]["stack"])


def four_themes_css(declarations: Mapping[str, str]) -> str:
    rules = []
    for media, selector, theme in THEME_RULES:
        scheme = "dark" if theme in DARK_THEMES else "light"
        rule = f"{selector}{{color-scheme:{scheme};{declarations[theme]}}}"
        rules.append(f"@media {media}{{{rule}}}" if media else rule)
    return "".join(rules)


def type_css(tokens: Mapping[str, Any]) -> str:
    families = "".join(
        f"--font-{name}:{tokens['type']['families'][name]['stack']};" for name in TYPE_FAMILIES
    )
    sizes = "".join(f"{token['cssVar']}:{token['value']};" for token in tokens["type"]["scale"].values())
    return f"--text-zoom:1;{families}{sizes}"


def tokens_css() -> str:
    tokens = _tokens()
    palettes = design_palettes()
    colours = {
        theme: "".join(f"--{name}:{value};" for name, value in palettes[theme].items()) for theme in THEMES
    }
    return f":root{{{type_css(tokens)}}}" + four_themes_css(colours)


def token_tables(names: tuple[str, ...]) -> str:
    palettes = design_palettes()
    lines = ["| Role | Light | Dark | High contrast light | High contrast dark |", "|---|---|---|---|---|"]
    lines += [
        f"| `--{name}` | " + " | ".join(palettes[theme][name] for theme in THEMES) + " |" for name in names
    ]
    return "\n".join(lines)
