from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.errors import InvalidInput
from app.research.monograph_document import FILE_SEPARATOR, LABEL_SEPARATOR, spec_file_name
from app.research.monograph_page import SLOT_PATTERN, MonographContent, Quote, TextUnit, render_page

from .monograph_generated_units import SourceBook
from .open_work_pages import CONTENT_FILE, MONOGRAPHS_DIR

__all__ = [
    "FRAGMENTS_FOLDER",
    "SPECS_FOLDER",
    "Drawings",
    "FilledFragment",
    "FilledUnits",
    "fragment_file_name",
    "remapped_nodes",
]

SPECS_FOLDER = "specs"
FRAGMENTS_FOLDER = "fragments"
FRAGMENT_SUFFIX = ".html"
MONOGRAPH_SLUG = re.compile(r"^[A-Za-z0-9-]+$")
UNIT_SLOT = "unit"
CITE_MARK = "cite"
UNIT_NAME = re.compile(r"^u\d+$")


def fragment_file_name(label: str) -> str:
    return label.replace(LABEL_SEPARATOR, FILE_SEPARATOR) + FRAGMENT_SUFFIX


@dataclass(frozen=True)
class FilledFragment:
    markup: str
    citations: dict[str, list[Quote]]
    citation_claims: dict[str, list[str]]


@dataclass(frozen=True)
class FilledUnits:
    units: dict[str, TextUnit]
    citations: dict[str, list[Quote]]
    citation_claims: dict[str, list[str]]


@dataclass
class Drawings:
    root: Path = MONOGRAPHS_DIR
    _contents: dict[str, MonographContent] = field(default_factory=dict, init=False, repr=False)

    def spec(self, monograph: str, label: str) -> dict[str, Any] | None:
        path = self._folder(monograph) / SPECS_FOLDER / spec_file_name(label)
        if not path.is_file():
            return None
        spec = json.loads(path.read_bytes().decode("utf-8"))
        if not isinstance(spec, dict):
            raise InvalidInput(f"The spec of {label} in {monograph} is not an object")
        return spec

    def has_fragment(self, monograph: str, label: str) -> bool:
        return self._fragment_path(monograph, label).is_file()

    def fragment(self, monograph: str, label: str, book: SourceBook) -> FilledFragment:
        raw = self._fragment_path(monograph, label).read_bytes().decode("utf-8")
        content = self._content(monograph)
        keys = [key for kind, key in SLOT_PATTERN.findall(raw) if kind == UNIT_SLOT]
        missing = sorted(key for key in keys if key not in content.units)
        if missing:
            raise InvalidInput(f"The fragment of {label} has slots for units {monograph} lacks: {missing}")
        filled = self._filled(monograph, keys, book)
        filling = content.model_copy(
            update={
                "sources": dict(book.sources),
                "citations": filled.citations,
                "citation_claims": filled.citation_claims,
                "units": filled.units,
            }
        )
        return FilledFragment(render_page(raw, filling), filled.citations, filled.citation_claims)

    def spec_units(self, monograph: str, spec: Mapping[str, Any], book: SourceBook) -> FilledUnits:
        named = {value for value in _strings(spec) if UNIT_NAME.fullmatch(value)}
        if not named:
            return FilledUnits({}, {}, {})
        content = self._content(monograph)
        return self._filled(monograph, sorted(named & set(content.units)), book)

    def _filled(self, monograph: str, keys: Sequence[str], book: SourceBook) -> FilledUnits:
        content = self._content(monograph)
        prefix = f"{monograph.lower()}:"
        rename = _renamer(content, book)
        units = {key: _remapped_unit(content.units[key], rename, prefix) for key in keys}
        cited = sorted({cite for unit in units.values() for cite in _cite_keys(unit.nodes)})
        citations = {key: _quotes(content, key.removeprefix(prefix), rename) for key in cited}
        claims = {key: list(content.citation_claims.get(key.removeprefix(prefix), [])) for key in cited}
        return FilledUnits(units, citations, claims)

    def _fragment_path(self, monograph: str, label: str) -> Path:
        return self._folder(monograph) / FRAGMENTS_FOLDER / fragment_file_name(label)

    def _folder(self, monograph: str) -> Path:
        if not MONOGRAPH_SLUG.fullmatch(monograph):
            raise InvalidInput(f"No monograph folder is named {monograph!r}")
        return self.root / monograph

    def _content(self, monograph: str) -> MonographContent:
        if monograph not in self._contents:
            raw = (self._folder(monograph) / CONTENT_FILE).read_bytes().decode("utf-8")
            self._contents[monograph] = MonographContent.model_validate_json(raw)
        return self._contents[monograph]


def remapped_nodes(nodes: Sequence[Any], rename: Callable[[str], str], prefix: str) -> list[Any]:
    remapped: list[Any] = []
    for node in nodes:
        if not isinstance(node, dict):
            remapped.append(node)
            continue
        changed = dict(node)
        if "c" in node:
            changed["c"] = remapped_nodes(node["c"], rename, prefix)
        if node.get("m") == CITE_MARK:
            changed["g"] = [rename(key) for key in node["g"]]
            changed["key"] = f"{prefix}{node['key']}"
        remapped.append(changed)
    return remapped


def _renamer(content: MonographContent, book: SourceBook) -> Callable[[str], str]:
    def rename(key: str) -> str:
        source = content.sources.get(key)
        if source is None:
            raise InvalidInput(f"{content.craft_slug} cites a source {key} it does not list")
        return book.key(source)

    return rename


def _remapped_unit(unit: TextUnit, rename: Callable[[str], str], prefix: str) -> TextUnit:
    return unit.model_copy(update={"nodes": remapped_nodes(unit.nodes, rename, prefix)})


def _quotes(content: MonographContent, key: str, rename: Callable[[str], str]) -> list[Quote]:
    return [
        quote.model_copy(update={"source": rename(quote.source)}) for quote in content.citations.get(key, [])
    ]


def _cite_keys(nodes: Sequence[Any]) -> list[str]:
    found: list[str] = []
    for node in nodes:
        if isinstance(node, Mapping):
            if node.get("m") == CITE_MARK:
                found.append(str(node["key"]))
            found += _cite_keys(node.get("c", []))
    return found


def _strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        return [found for item in value.values() for found in _strings(item)]
    if isinstance(value, list | tuple):
        return [found for item in value for found in _strings(item)]
    return []
