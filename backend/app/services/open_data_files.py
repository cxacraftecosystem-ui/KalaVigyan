from __future__ import annotations

import csv
import hashlib
import io
import json
from collections.abc import Mapping
from dataclasses import dataclass

from .open_data_changes import ReleaseChanges
from .open_data_descriptor import PACKAGE_FILE, csv_file, jsonl_file, package_descriptor
from .open_data_readme import MANIFEST_FILE, changes_text, citation_cff, readme_text
from .open_data_release import ReleaseStamp
from .open_data_rows import OpenDataTables
from .open_data_schema import Table
from .open_data_scope import WHOLE, ReleaseScope
from .open_data_tables import TABLES
from .open_data_values import Row

__all__ = [
    "CHANGES_FILE",
    "CITATION_FILE",
    "README_FILE",
    "ReleaseFiles",
    "csv_bytes",
    "jsonl_bytes",
    "manifest_text",
    "release_files",
    "sha256_of",
]

README_FILE = "README.md"
CITATION_FILE = "CITATION.cff"
CHANGES_FILE = "CHANGES.md"
UTF8 = "utf-8"
OTHER_SCOPE = "The release's words name the craft {scope!r}, but its stamp names {stamp!r}."


@dataclass(frozen=True)
class ReleaseFiles:
    files: Mapping[str, bytes]

    def facts(self) -> list[dict[str, object]]:
        return [
            {"path": name, "bytes": len(body), "sha256": sha256_of(body)}
            for name, body in sorted(self.files.items())
        ]

    def total_bytes(self) -> int:
        return sum(len(body) for body in self.files.values())

    def manifest_sha256(self) -> str:
        return sha256_of(self.files[MANIFEST_FILE])


def release_files(
    tables: OpenDataTables,
    stamp: ReleaseStamp,
    changes: ReleaseChanges,
    *,
    site: str,
    scope: ReleaseScope = WHOLE,
) -> ReleaseFiles:
    if scope.craft != stamp.craft:
        raise ValueError(OTHER_SCOPE.format(scope=scope.craft, stamp=stamp.craft))
    files: dict[str, bytes] = {}
    for table in TABLES:
        files[jsonl_file(table)] = jsonl_bytes(table, tables.of(table))
        files[csv_file(table)] = csv_bytes(table, tables.of(table))
    facts = {name: (len(body), sha256_of(body)) for name, body in files.items()}
    descriptor = package_descriptor(stamp, facts, site=site, scope=scope)
    files[PACKAGE_FILE] = (json.dumps(descriptor, ensure_ascii=False, indent=2) + "\n").encode(UTF8)
    files[README_FILE] = readme_text(stamp, tables.counts(), site=site, scope=scope).encode(UTF8)
    files[CITATION_FILE] = citation_cff(stamp, site=site, scope=scope).encode(UTF8)
    files[CHANGES_FILE] = changes_text(stamp, changes).encode(UTF8)
    files[MANIFEST_FILE] = manifest_text(files).encode(UTF8)
    return ReleaseFiles(files=dict(sorted(files.items())))


def jsonl_bytes(table: Table, rows: list[Row]) -> bytes:
    names = table.names()
    lines = (
        json.dumps({name: row[name] for name in names}, ensure_ascii=False, separators=(",", ":")) + "\n"
        for row in rows
    )
    return "".join(lines).encode(UTF8)


def csv_bytes(table: Table, rows: list[Row]) -> bytes:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(table.names())
    for row in rows:
        writer.writerow([_cell(row[name]) for name in table.names()])
    return out.getvalue().encode(UTF8)


def manifest_text(files: Mapping[str, bytes]) -> str:
    return "".join(
        f"{sha256_of(body)}  {name}\n" for name, body in sorted(files.items()) if name != MANIFEST_FILE
    )


def sha256_of(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _cell(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list | dict):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)
