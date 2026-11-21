from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from pydantic import ConfigDict, Field

from app.core.errors import InvalidInput

from .base import ContractModel

__all__ = [
    "CITE_MARK",
    "FIXED_MARKS",
    "HASH_PATTERN",
    "NAME_UNITS",
    "PASSAGE_TEXTS_MAX",
    "PASSAGE_TEXT_MAX_CHARS",
    "UNIT_KEY_MAX_CHARS",
    "PassageLeaf",
    "TaskPassage",
    "has_letters",
    "is_translatable",
    "passage_leaves",
    "passage_text",
    "task_passage",
    "unit_hash",
    "with_texts",
]

CITE_MARK = "cite"
FIXED_MARKS = frozenset({"i", "sub", "sup"})
CITATION_ATTRS = frozenset({"g", "key"})
NAME_UNITS = frozenset({"masthead-title"})
PASSAGE_TEXTS_MAX = 60
PASSAGE_TEXT_MAX_CHARS = 2000
UNIT_KEY_MAX_CHARS = 200
HASH_PATTERN = r"^[0-9a-f]{64}$"
CHILDREN = "c"
MARK = "m"
FEWER = "The translation gives fewer texts than the passage holds; give one text for each, in order."
MORE = "The translation gives more texts than the passage holds; give one text for each, in order."


@dataclass(frozen=True)
class PassageLeaf:
    text: str
    fixed: bool
    cited: bool


class TaskPassage(ContractModel):
    model_config = ConfigDict(str_strip_whitespace=False)

    key: str = Field(min_length=1, max_length=UNIT_KEY_MAX_CHARS)
    source_hash: str = Field(pattern=HASH_PATTERN)
    english: str
    texts: list[str]
    fixed: list[int] = Field(default_factory=list)
    cited: list[int] = Field(default_factory=list)


def passage_leaves(nodes: Sequence[Any]) -> list[PassageLeaf]:
    return list(_leaves(nodes, fixed=False, cited=False))


def _leaves(nodes: Sequence[Any], *, fixed: bool, cited: bool) -> Iterator[PassageLeaf]:
    for node in nodes:
        if isinstance(node, str):
            yield PassageLeaf(node, fixed, cited)
            continue
        mark = node.get(MARK)
        yield from _leaves(
            node.get(CHILDREN, []), fixed=fixed or mark in FIXED_MARKS, cited=cited or mark == CITE_MARK
        )


def passage_text(leaves: Sequence[PassageLeaf]) -> str:
    return "".join(leaf.text for leaf in leaves)


def has_letters(text: str) -> bool:
    return any(char.isalpha() for char in text)


def is_translatable(key: str, nodes: Sequence[Any]) -> bool:
    if key in NAME_UNITS:
        return False
    return any(not leaf.fixed and has_letters(leaf.text) for leaf in passage_leaves(nodes))


def unit_hash(nodes: Sequence[Any], claim_ids: Sequence[str]) -> str:
    body = {"claims": sorted(claim_ids), "nodes": _hashed(nodes)}
    text = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _hashed(nodes: Sequence[Any]) -> list[Any]:
    return [node if isinstance(node, str) else _hashed_mark(node) for node in nodes]


def _hashed_mark(node: Mapping[str, Any]) -> dict[str, Any]:
    cited = node.get(MARK) == CITE_MARK
    return {
        name: _hashed(value) if name == CHILDREN else value
        for name, value in node.items()
        if not (cited and name in CITATION_ATTRS)
    }


def with_texts(nodes: Sequence[Any], texts: Sequence[str]) -> list[Any]:
    given = iter(texts)
    replaced = _replaced(nodes, given)
    if next(given, None) is not None:
        raise InvalidInput(MORE)
    return replaced


def _replaced(nodes: Sequence[Any], given: Iterator[str]) -> list[Any]:
    out: list[Any] = []
    for node in nodes:
        if isinstance(node, str):
            text = next(given, None)
            if text is None:
                raise InvalidInput(FEWER)
            out.append(text)
        elif CHILDREN in node:
            out.append({**node, CHILDREN: _replaced(node[CHILDREN], given)})
        else:
            out.append(dict(node))
    return out


def task_passage(key: str, nodes: Sequence[Any], claim_ids: Sequence[str]) -> TaskPassage:
    leaves = passage_leaves(nodes)
    return TaskPassage(
        key=key,
        source_hash=unit_hash(nodes, claim_ids),
        english=passage_text(leaves),
        texts=[leaf.text for leaf in leaves],
        fixed=[at for at, leaf in enumerate(leaves) if leaf.fixed],
        cited=[at for at, leaf in enumerate(leaves) if leaf.cited],
    )
