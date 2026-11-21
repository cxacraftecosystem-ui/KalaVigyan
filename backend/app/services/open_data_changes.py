from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field

from .open_data_rows import OpenDataTables, row_key
from .open_data_tables import TABLES

__all__ = [
    "DIGEST_CHARS",
    "EXAMPLES_MAX",
    "ReleaseChanges",
    "TableChanges",
    "release_changes",
    "row_digest",
    "row_digests",
]

DIGEST_CHARS = 16
EXAMPLES_MAX = 25

Digests = Mapping[str, Mapping[str, str]]


@dataclass(frozen=True)
class TableChanges:
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    changed: list[str] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        return {"added": len(self.added), "removed": len(self.removed), "changed": len(self.changed)}

    def any(self) -> bool:
        return bool(self.added or self.removed or self.changed)


@dataclass(frozen=True)
class ReleaseChanges:
    previous: str | None
    tables: Mapping[str, TableChanges]

    def counts(self) -> dict[str, dict[str, int]]:
        return {name: changes.counts() for name, changes in self.tables.items()}


def row_digest(row: Mapping[str, object]) -> str:
    text = json.dumps(row, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:DIGEST_CHARS]


def row_digests(tables: OpenDataTables) -> dict[str, dict[str, str]]:
    return {
        table.name: {row_key(table, row): row_digest(row) for row in tables.of(table)} for table in TABLES
    }


def release_changes(
    current: Digests, previous: Digests | None, previous_version: str | None
) -> ReleaseChanges:
    if previous is None:
        return ReleaseChanges(previous=None, tables={table.name: TableChanges() for table in TABLES})
    return ReleaseChanges(
        previous=previous_version,
        tables={
            table.name: _diff(current.get(table.name, {}), previous.get(table.name, {})) for table in TABLES
        },
    )


def _diff(now: Mapping[str, str], before: Mapping[str, str]) -> TableChanges:
    return TableChanges(
        added=sorted(set(now) - set(before)),
        removed=sorted(set(before) - set(now)),
        changed=sorted(key for key in set(now) & set(before) if now[key] != before[key]),
    )
