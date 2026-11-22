from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from datetime import date, datetime
from typing import Any, Literal
from urllib.parse import quote

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.craft_names import load_craft_names
from app.models import Craft, OpenDataRelease
from app.research.base import ContractModel

from .open_data import craft_releases, published_releases
from .open_data_descriptor import csv_file, jsonl_file
from .open_data_release import ZENODO
from .open_data_schema import Table
from .open_data_scope import WHOLE, ReleaseScope
from .open_data_tables import TABLES
from .open_data_text import (
    ATTRIBUTION,
    CITED_WORKS,
    CODE_URL,
    CREATOR,
    DATASET_TITLE,
    LEFT_OUT,
    LICENCE_ID,
    LICENCE_NAME,
    LICENCE_URL,
    SUMMARY,
    data_page,
    page_citation_bibtex,
    page_citation_text,
)

__all__ = [
    "OPEN_DATA_SCHEMA_VERSION",
    "CraftRelease",
    "DatasetField",
    "DatasetLicence",
    "DatasetTable",
    "OpenDataListing",
    "PublishedRelease",
    "ReleaseFile",
    "listing_of",
    "open_data_listing",
]

OPEN_DATA_SCHEMA_VERSION = 1


class ReleaseFile(ContractModel):
    path: str
    bytes: int
    download_url: str


class PublishedRelease(ContractModel):
    version: str
    released_on: date
    doi: str
    doi_url: str
    record_url: str
    published_at: datetime
    total_bytes: int
    files: list[ReleaseFile]
    counts: dict[str, int]
    changes: dict[str, dict[str, int]]
    citation: str
    bibtex: str


class CraftRelease(PublishedRelease):
    craft: str
    craft_name: str
    title: str
    concept_doi: str
    concept_doi_url: str


class DatasetField(ContractModel):
    name: str
    type: str
    description: str
    required: bool


class DatasetTable(ContractModel):
    name: str
    title: str
    description: str
    key: list[str]
    files: list[str]
    fields: list[DatasetField]


class DatasetLicence(ContractModel):
    id: str
    name: str
    url: str


class OpenDataListing(ContractModel):
    schema_version: Literal[1] = OPEN_DATA_SCHEMA_VERSION
    title: str = DATASET_TITLE
    summary: str = SUMMARY
    creator: str = CREATOR
    licence: DatasetLicence = DatasetLicence(id=LICENCE_ID, name=LICENCE_NAME, url=LICENCE_URL)
    attribution: str = ATTRIBUTION
    cited_works: str = CITED_WORKS
    left_out: list[str] = list(LEFT_OUT)
    code_url: str = CODE_URL
    page_url: str
    concept_doi: str | None
    concept_doi_url: str | None
    citation: str
    bibtex: str
    latest: PublishedRelease | None
    releases: list[PublishedRelease]
    craft_releases: list[CraftRelease]
    tables: list[DatasetTable]


async def open_data_listing(session: AsyncSession, *, site: str) -> OpenDataListing:
    scoped = await craft_releases(session, ZENODO)
    names = await _craft_names(session, {row.scope for row in scoped if row.scope is not None})
    return listing_of(await published_releases(session, ZENODO), site=site, crafts=scoped, names=names)


def listing_of(
    rows: Sequence[OpenDataRelease],
    *,
    site: str,
    crafts: Sequence[OpenDataRelease] = (),
    names: Mapping[str, str] | None = None,
) -> OpenDataListing:
    releases = [PublishedRelease(**_release_fields(row, WHOLE)) for row in rows]
    concept = rows[0].conceptDoi if rows else None
    return OpenDataListing(
        page_url=data_page(site),
        concept_doi=concept,
        concept_doi_url=f"https://doi.org/{concept}" if concept else None,
        citation=releases[0].citation if releases else page_citation_text(site),
        bibtex=releases[0].bibtex if releases else page_citation_bibtex(site),
        latest=releases[0] if releases else None,
        releases=releases,
        craft_releases=[_craft_release(row, names or {}) for row in crafts],
        tables=[_table(table) for table in TABLES],
    )


async def _craft_names(session: AsyncSession, slugs: Collection[str]) -> dict[str, str]:
    if not slugs:
        return {}
    rows = await session.execute(select(Craft.slug, Craft.name).where(Craft.slug.in_(list(slugs))))
    shown = load_craft_names()
    return {slug: shown.display_name(slug, name) for slug, name in rows.tuples().all()}


def _craft_release(row: OpenDataRelease, names: Mapping[str, str]) -> CraftRelease:
    craft = str(row.scope)
    scope = ReleaseScope(craft=craft, name=names.get(craft, craft))
    return CraftRelease(
        **_release_fields(row, scope),
        craft=craft,
        craft_name=str(scope.name),
        title=scope.title,
        concept_doi=row.conceptDoi,
        concept_doi_url=f"https://doi.org/{row.conceptDoi}",
    )


def _release_fields(row: OpenDataRelease, scope: ReleaseScope) -> dict[str, Any]:
    record = (row.recordUrl or "").rstrip("/")
    published = row.publishedAt
    if published is None:
        raise ValueError(f"release {row.version} is listed as published without a publication time")
    return {
        "version": row.version,
        "released_on": row.releasedOn,
        "doi": row.doi,
        "doi_url": f"https://doi.org/{row.doi}",
        "record_url": record,
        "published_at": published,
        "total_bytes": row.totalBytes,
        "files": [_file(record, entry) for entry in row.files],
        "counts": dict(row.counts),
        "changes": {name: dict(counts) for name, counts in row.changes.items()},
        "citation": scope.citation(row.version, row.releasedOn, row.doi),
        "bibtex": scope.bibtex(row.version, row.releasedOn, row.doi),
    }


def _file(record: str, entry: dict[str, Any]) -> ReleaseFile:
    path = str(entry["path"])
    return ReleaseFile(
        path=path, bytes=int(entry["bytes"]), download_url=f"{record}/files/{quote(path)}?download=1"
    )


def _table(table: Table) -> DatasetTable:
    return DatasetTable(
        name=table.name,
        title=table.title,
        description=table.description,
        key=list(table.key),
        files=[jsonl_file(table), csv_file(table)],
        fields=[
            DatasetField(name=c.name, type=c.type, description=c.description, required=c.required)
            for c in table.columns
        ],
    )
