from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

__all__ = [
    "CARRIED_FIELDS",
    "DOCUMENT_PART_SCHEMA_VERSION",
    "PART_BYTES_MAX",
    "DocumentPart",
    "compact_json",
    "document_parts",
    "part_body",
]

DOCUMENT_PART_SCHEMA_VERSION = 1
PART_BYTES_MAX = 1_000_000
WRAPPER_BYTES = 64
SHELL, SPECS, FRAGMENTS = "shell", "specs", "fragments"
CARRIED_FIELDS = (SHELL, SPECS, FRAGMENTS)


@dataclass(frozen=True)
class _Item:
    field: str
    label: str | None
    value: Any
    size: int


@dataclass(frozen=True)
class DocumentPart:
    part: int
    parts: int
    body: dict[str, Any]


def compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def document_parts(body: Mapping[str, Any], *, most: int = PART_BYTES_MAX) -> list[DocumentPart]:
    if most <= WRAPPER_BYTES:
        raise ValueError(f"a document part holds more than its {WRAPPER_BYTES} bytes of wrapping, not {most}")
    if _size(body) <= most:
        return [DocumentPart(part=0, parts=1, body=dict(body))]
    core = {key: value for key, value in body.items() if not _carried(key, value)}
    packed = _packed(_items(body), most)
    total = 1 + len(packed)
    later = [DocumentPart(part=at, parts=total, body=_gathered(items)) for at, items in enumerate(packed, 1)]
    return [DocumentPart(part=0, parts=total, body=core), *later]


def part_body(part: DocumentPart, version: int) -> dict[str, Any]:
    return {
        "schemaVersion": DOCUMENT_PART_SCHEMA_VERSION,
        "version": version,
        "part": part.part,
        "parts": part.parts,
        "body": part.body,
    }


def _carried(key: str, value: Any) -> bool:
    return key in (SPECS, FRAGMENTS) or (key == SHELL and isinstance(value, str))


def _items(body: Mapping[str, Any]) -> list[_Item]:
    items: list[_Item] = []
    shell = body.get(SHELL)
    if isinstance(shell, str):
        items.append(_Item(SHELL, None, shell, _size(shell)))
    for field in (SPECS, FRAGMENTS):
        held: Mapping[str, Any] = body.get(field) or {}
        items.extend(_Item(field, label, value, _size({label: value})) for label, value in held.items())
    return items


def _packed(items: Sequence[_Item], most: int) -> list[list[_Item]]:
    packed: list[list[_Item]] = []
    room = 0
    for item in items:
        if not packed or item.size > room:
            packed.append([])
            room = most - WRAPPER_BYTES
        packed[-1].append(item)
        room -= item.size
    return packed


def _gathered(items: Sequence[_Item]) -> dict[str, Any]:
    gathered: dict[str, Any] = {SPECS: {}, FRAGMENTS: {}}
    for item in items:
        if item.label is None:
            gathered[item.field] = item.value
        else:
            gathered[item.field][item.label] = item.value
    return gathered


def _size(value: Any) -> int:
    return len(compact_json(value).encode("utf-8"))
