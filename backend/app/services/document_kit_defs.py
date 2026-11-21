from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from .document_components_homes import home_scopes
from .monograph_document import (
    KIT_DIR,
    MONOGRAPHS_DIR,
    has_authored_content,
    monograph_content,
    monograph_shell,
    page_parts,
)

__all__ = [
    "DEFS_CLASS",
    "KIT_STYLE_FILE",
    "defined_ids",
    "kit_defs",
    "kit_defs_of",
    "kit_style_references",
    "kit_style_references_of",
    "referenced_ids",
    "spec_ids",
]

DEFS_CLASS = "kv-defs"
DEFS_BLOCK = re.compile(
    r'<svg\b[^>]*\bclass="' + DEFS_CLASS + r'"[^>]*>\s*<defs>(?P<body>.*?)</defs>\s*</svg>', re.S
)
DEFINITION = re.compile(r'<(?P<tag>[A-Za-z]+)\b[^>]*\bid="(?P<id>[^"]+)"[^>]*>.*?</(?P=tag)>', re.S)
INNER_DEFS = re.compile(r"<defs>(?P<body>.*?)</defs>", re.S)
SYMBOL = re.compile(r'<symbol\b[^>]*\bid="(?P<id>[^"]+)"[^>]*>.*?</symbol>', re.S)
REFERENCE = re.compile(r"""(?:url\(#|<use\s[^>]*?href=["']#)(?P<id>[A-Za-z][\w-]*)""")
USE_ATTRIBUTES = ("href", "xlink:href")
ID_ATTRIBUTE = re.compile(r'\bid="(?P<id>[^"]+)"')
SCOPE_CLASS = re.compile(r'class="[^"]*\bbx-(?P<scope>[a-z]+)\b[^"]*"')
KIT_STYLE_FILE = "monograph.css"
STYLE_RULE = re.compile(r"(?P<selector>[^{}]+)\{(?P<body>[^{}]*)\}")
SCOPE_SELECTOR = re.compile(r"\.bx-(?P<scope>[a-z]+)\b")


def kit_defs_of(
    shells: Iterable[str], fragments: Iterable[tuple[str | None, str]] = ()
) -> dict[str, dict[str, str | None]]:
    kept: dict[str, dict[str, str | None]] = {}
    for shell in shells:
        for block in DEFS_BLOCK.finditer(shell):
            _keep(kept, _scope_before(shell, block.start()), block.group("body"))
    for scope, markup in fragments:
        for block in INNER_DEFS.finditer(markup):
            _keep(kept, scope, block.group("body"))
        for symbol in SYMBOL.finditer(markup):
            kept.setdefault(symbol.group("id"), {"scope": scope, "markup": symbol.group(0)})
    return kept


def _scope_before(shell: str, at: int) -> str | None:
    found = SCOPE_CLASS.findall(shell, 0, at)
    return found[-1] if found else None


def _keep(kept: dict[str, dict[str, str | None]], scope: str | None, body: str) -> None:
    for definition in DEFINITION.finditer(body):
        kept.setdefault(definition.group("id"), {"scope": scope, "markup": definition.group(0)})


def kit_defs() -> dict[str, dict[str, str | None]]:
    slugs = sorted(
        path.name for path in MONOGRAPHS_DIR.iterdir() if path.is_dir() and has_authored_content(path.name)
    )
    fragments = [
        (home_scopes(slug).get(label), markup)
        for slug in slugs
        for label, markup in page_parts(monograph_content(slug)).fragments.items()
    ]
    return kit_defs_of((monograph_shell(slug) for slug in slugs), fragments)


def kit_style_references() -> dict[str, list[str]]:
    return kit_style_references_of((KIT_DIR / KIT_STYLE_FILE).read_bytes().decode("utf-8"))


def kit_style_references_of(css: str) -> dict[str, list[str]]:
    found: dict[str, set[str]] = {}
    for rule in STYLE_RULE.finditer(css):
        ids = referenced_ids(rule.group("body"))
        for scope in SCOPE_SELECTOR.findall(rule.group("selector")) if ids else ():
            found.setdefault(scope, set()).update(ids)
    return {scope: sorted(ids) for scope, ids in sorted(found.items())}


def referenced_ids(markup: str) -> set[str]:
    return {found.group("id") for found in REFERENCE.finditer(markup)}


def defined_ids(markup: str) -> set[str]:
    return {found.group("id") for found in ID_ATTRIBUTE.finditer(markup)}


def spec_ids(node: Any) -> tuple[set[str], set[str]]:
    used: set[str] = set()
    defined: set[str] = set()
    _walk(node, used, defined)
    return used, defined


def _walk(node: Any, used: set[str], defined: set[str]) -> None:
    if isinstance(node, list):
        for item in node:
            _walk(item, used, defined)
        return
    if not isinstance(node, dict):
        return
    attrs = node.get("attrs") if isinstance(node.get("attrs"), dict) else {}
    if isinstance(attrs.get("id"), str):
        defined.add(attrs["id"])
    for name in USE_ATTRIBUTES:
        target = attrs.get(name)
        if node.get("tag") == "use" and isinstance(target, str) and target.startswith("#"):
            used.add(target[1:])
    for value in node.values():
        _walk(value, used, defined)
