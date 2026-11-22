from __future__ import annotations

import json
from collections.abc import Mapping

from .open_data_changes import EXAMPLES_MAX, ReleaseChanges, TableChanges
from .open_data_release import ReleaseStamp
from .open_data_schema import Table
from .open_data_scope import WHOLE, ReleaseScope
from .open_data_tables import TABLES
from .open_data_text import (
    ATTRIBUTION,
    CITED_WORKS,
    CODE_URL,
    CREATOR,
    LEFT_OUT,
    LICENCE_ID,
    LICENCE_NAME,
    LICENCE_URL,
    data_page,
)

__all__ = ["MANIFEST_FILE", "changes_text", "citation_cff", "readme_text"]

MANIFEST_FILE = "SHA256SUMS"
FIRST_RELEASE = "This is the first release."


def readme_text(
    stamp: ReleaseStamp, counts: Mapping[str, int], *, site: str, scope: ReleaseScope = WHOLE
) -> str:
    parts = [
        f"# {scope.title}\n",
        f"Version {stamp.version}, released {stamp.released.isoformat()}.\n",
        f"{scope.summary}\n",
        "## Cite this dataset\n",
        f"{scope.citation(stamp.version, stamp.released, stamp.doi)}\n",
        f"This version: {stamp.doi_url()}. Every version: {stamp.concept_doi_url()}.\n",
        "```bibtex\n" + scope.bibtex(stamp.version, stamp.released, stamp.doi) + "\n```\n",
        "## Licence\n",
        f"KalaVigyan's own text and structure in this release are licensed under {LICENCE_NAME} "
        f"({LICENCE_ID}, {LICENCE_URL}). Give this attribution: {ATTRIBUTION}\n",
        f"{CITED_WORKS}\n",
        "## What it holds\n",
        _holdings(counts),
        "## What it leaves out\n",
        "".join(f"- {item}\n" for item in LEFT_OUT),
        "## Files\n",
        _files_text(),
        "## Fields\n",
        "\n".join(_fields(table) for table in TABLES),
        "## About\n",
        _about(site, scope),
    ]
    return "\n".join(parts)


def _about(site: str, scope: ReleaseScope) -> str:
    about = (
        f"KalaVigyan: {site.rstrip('/')}. This dataset's page: {data_page(site)}. The code that builds it: "
        f"{CODE_URL}. Its changes against the previous release are in CHANGES.md.\n"
    )
    page, whole = scope.craft_page(site), scope.whole_note(site)
    if page is None or whole is None:
        return about
    return f"{about}\nThe monograph of {scope.name}: {page}. {whole}\n"


def changes_text(stamp: ReleaseStamp, changes: ReleaseChanges) -> str:
    head = f"# Changes in version {stamp.version}\n"
    if changes.previous is None:
        return f"{head}\n{FIRST_RELEASE}\n"
    rows = "".join(
        f"| {name} | {found.counts()['added']} | {found.counts()['removed']} | {found.counts()['changed']} |\n"
        for name, found in changes.tables.items()
    )
    details = "".join(_table_changes(name, found) for name, found in changes.tables.items() if found.any())
    return (
        f"{head}\nCompared with version {changes.previous}. Rows are named by their key "
        f"(see datapackage.json, primaryKey).\n\n| Table | Added | Removed | Changed |\n|---|---:|---:|---:|\n"
        f"{rows}{details}"
    )


def citation_cff(stamp: ReleaseStamp, *, site: str, scope: ReleaseScope = WHOLE) -> str:
    quoted = json.dumps
    lines = [
        "cff-version: 1.2.0",
        f"message: {quoted('If you use this dataset, cite it as below.')}",
        "type: dataset",
        f"title: {quoted(scope.title)}",
        f"version: {quoted(stamp.version)}",
        f"doi: {quoted(stamp.doi)}",
        f"date-released: {quoted(stamp.released.isoformat())}",
        f"license: {LICENCE_ID}",
        f"url: {quoted(data_page(site))}",
        f"repository-code: {quoted(CODE_URL)}",
        "authors:",
        f"  - name: {quoted(CREATOR)}",
        "identifiers:",
        "  - type: doi",
        f"    value: {quoted(stamp.concept_doi)}",
        f"    description: {quoted('Every version of the dataset')}",
        "  - type: doi",
        f"    value: {quoted(stamp.doi)}",
        f"    description: {quoted('This version')}",
        *_page_identifier(scope.craft_page(site), scope.name),
        "keywords:",
        *(f"  - {quoted(keyword)}" for keyword in scope.keywords),
        f"abstract: {quoted(scope.summary)}",
    ]
    return "\n".join(lines) + "\n"


def _page_identifier(page: str | None, name: str | None) -> list[str]:
    if page is None:
        return []
    described = json.dumps(f"The monograph of {name}")
    return ["  - type: url", f"    value: {json.dumps(page)}", f"    description: {described}"]


def _holdings(counts: Mapping[str, int]) -> str:
    rows = "".join(
        f"| {table.title} | `{table.name}.jsonl`, `{table.name}.csv` | {counts.get(table.name, 0)} | "
        f"{table.description} |\n"
        for table in TABLES
    )
    return f"| Table | Files | Rows | What it is |\n|---|---|---:|---|\n{rows}"


def _files_text() -> str:
    return (
        "- `<table>.jsonl`: JSON Lines in UTF-8, one record per line, every field present.\n"
        "- `<table>.csv`: the same rows for spreadsheets, in UTF-8; lists and objects are written as JSON, "
        "and an empty cell is a field with no value.\n"
        "- `datapackage.json`: the Frictionless Data Package descriptor, with every field's type and meaning.\n"
        "- `CITATION.cff`: how to cite this version.\n"
        "- `CHANGES.md`: what changed since the previous release.\n"
        f"- `{MANIFEST_FILE}`: the SHA-256 checksum of every other file; check them with "
        f"`sha256sum -c {MANIFEST_FILE}`.\n"
    )


def _fields(table: Table) -> str:
    rows = "".join(
        f"| `{column.name}` | {column.type} | {'yes' if column.required else 'no'} | {column.description} |\n"
        for column in table.columns
    )
    key = ", ".join(f"`{name}`" for name in table.key)
    return (
        f"### {table.title} (`{table.name}`)\n\n{table.description} Key: {key}.\n\n"
        f"| Field | Type | Never empty | Meaning |\n|---|---|---|---|\n{rows}"
    )


def _table_changes(name: str, found: TableChanges) -> str:
    lines = [f"\n### {name}\n"]
    for label, keys in (("Added", found.added), ("Removed", found.removed), ("Changed", found.changed)):
        if keys:
            shown = ", ".join(keys[:EXAMPLES_MAX])
            more = f" and {len(keys) - EXAMPLES_MAX} more" if len(keys) > EXAMPLES_MAX else ""
            lines.append(f"- {label}: {shown}{more}.\n")
    return "".join(lines)
