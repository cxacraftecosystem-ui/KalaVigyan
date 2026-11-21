from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .open_data_release import ReleaseStamp
from .open_data_schema import Column, Table
from .open_data_tables import TABLES
from .open_data_text import (
    CREATOR,
    DATASET_TITLE,
    KEYWORDS,
    LICENCE_ID,
    LICENCE_NAME,
    LICENCE_URL,
    SUMMARY,
    data_page,
)

__all__ = [
    "CSV_SUFFIX",
    "FOREIGN_KEYS",
    "JSONL_SUFFIX",
    "PACKAGE_FILE",
    "PACKAGE_NAME",
    "FileFacts",
    "csv_file",
    "jsonl_file",
    "package_descriptor",
]

PACKAGE_FILE = "datapackage.json"
PACKAGE_NAME = "kalavigyan-open-knowledge"
JSONL_SUFFIX = ".jsonl"
CSV_SUFFIX = ".csv"
CSV_RESOURCE = "{name}-csv"

FOREIGN_KEYS: Mapping[str, tuple[tuple[str, str, str], ...]] = {
    "citations": (("claim_id", "claims", "id"), ("source_id", "sources", "id")),
    "crafts": (("category", "categories", "slug"), ("family", "families", "slug")),
    "craft_places": (("craft", "crafts", "slug"),),
    "families": (("category", "categories", "slug"),),
    "stages": (("craft", "crafts", "slug"),),
    "materials": (("craft", "crafts", "slug"),),
    "reactions": (("craft", "crafts", "slug"),),
    "native_names": (("craft", "crafts", "slug"), ("claim_id", "claims", "id")),
    "gi_records": (("craft", "crafts", "slug"),),
}

FileFacts = Mapping[str, tuple[int, str]]


def jsonl_file(table: Table) -> str:
    return f"{table.name}{JSONL_SUFFIX}"


def csv_file(table: Table) -> str:
    return f"{table.name}{CSV_SUFFIX}"


def package_descriptor(stamp: ReleaseStamp, files: FileFacts, *, site: str) -> dict[str, Any]:
    return {
        "profile": "data-package",
        "name": PACKAGE_NAME,
        "id": stamp.doi_url(),
        "title": DATASET_TITLE,
        "description": SUMMARY,
        "version": stamp.version,
        "created": f"{stamp.released.isoformat()}T00:00:00Z",
        "homepage": data_page(site),
        "keywords": list(KEYWORDS),
        "licenses": [{"name": LICENCE_ID, "path": LICENCE_URL, "title": LICENCE_NAME}],
        "contributors": [{"title": CREATOR, "role": "author"}],
        "sources": [{"title": "KalaVigyan", "path": site.rstrip("/")}],
        "resources": [resource for table in TABLES for resource in _resources(table, files)],
    }


def _resources(table: Table, files: FileFacts) -> list[dict[str, Any]]:
    jsonl, csv = jsonl_file(table), csv_file(table)
    common = {"title": table.title, "description": table.description, "encoding": "utf-8"}
    return [
        {
            "name": table.name,
            "path": jsonl,
            "profile": "data-resource",
            "format": "jsonl",
            "mediatype": "application/jsonl",
            **common,
            **_facts(files, jsonl),
            "schema": _schema(table, csv_names=False),
        },
        {
            "name": CSV_RESOURCE.format(name=table.name),
            "path": csv,
            "profile": "tabular-data-resource",
            "format": "csv",
            "mediatype": "text/csv",
            **common,
            "dialect": {"delimiter": ",", "lineTerminator": "\n", "quoteChar": '"', "header": True},
            **_facts(files, csv),
            "schema": _schema(table, csv_names=True),
        },
    ]


def _facts(files: FileFacts, name: str) -> dict[str, Any]:
    size, digest = files[name]
    return {"bytes": size, "hash": f"sha256:{digest}"}


def _schema(table: Table, *, csv_names: bool) -> dict[str, Any]:
    schema: dict[str, Any] = {
        "fields": [_field(column) for column in table.columns],
        "primaryKey": list(table.key),
        "missingValues": [""],
    }
    keys = FOREIGN_KEYS.get(table.name, ())
    if keys:
        schema["foreignKeys"] = [
            {
                "fields": column,
                "reference": {
                    "resource": CSV_RESOURCE.format(name=target) if csv_names else target,
                    "fields": field,
                },
            }
            for column, target, field in keys
        ]
    return schema


def _field(column: Column) -> dict[str, Any]:
    found: dict[str, Any] = {"name": column.name, "type": column.type, "description": column.description}
    if column.required:
        found["constraints"] = {"required": True}
    return found
