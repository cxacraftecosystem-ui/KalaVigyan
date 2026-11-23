from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from .kin_crafts import KIN_KIND
from .monograph_document import MonographDocument
from .spec_strings import spec_strings

__all__ = ["COUNTED_APART", "SourceSplit", "counted_apart", "source_split"]

CITE_MARK = "cite"
COUNTED_APART = (
    "the masthead counts {own} for this page's own sentences and, apart, {kin} for the kin crafts' "
    "sentences alone; check that no family fact is filed as the craft's own"
)


@dataclass(frozen=True)
class SourceSplit:
    own: tuple[str, ...]
    kin: tuple[str, ...]


def source_split(document: MonographDocument) -> SourceSplit:
    content = document.content
    kin_labels = {component.label for component in content.components if component.kind == KIN_KIND}
    held = {entry.ref for entry in content.layout if entry.kind == "unit" and entry.within in kin_labels}
    held |= {value for label in kin_labels for value in spec_strings(document.specs.get(label, {}))}
    in_kin: set[str] = set()
    elsewhere: set[str] = set()
    for key, unit in content.units.items():
        (in_kin if key in held else elsewhere).update(_cited(unit.nodes))
    for label, spec in document.specs.items():
        if label not in kin_labels:
            elsewhere.update(spec_strings(spec))
    ordered = sorted(content.sources, key=lambda key: content.sources[key].number)
    kin = tuple(key for key in ordered if key in in_kin and key not in elsewhere)
    return SourceSplit(own=tuple(key for key in ordered if key not in kin), kin=kin)


def counted_apart(document: MonographDocument) -> str:
    split = source_split(document)
    return COUNTED_APART.format(own=_sources(len(split.own)), kin=_sources(len(split.kin)))


def _sources(count: int) -> str:
    if count == 0:
        return "no source"
    return "1 source" if count == 1 else f"{count} sources"


def _cited(nodes: Sequence[Any]) -> set[str]:
    found: set[str] = set()
    for node in nodes:
        if isinstance(node, dict):
            if node.get("m") == CITE_MARK:
                found.update(str(key) for key in node.get("g", []))
            found |= _cited(node.get("c", []))
    return found
