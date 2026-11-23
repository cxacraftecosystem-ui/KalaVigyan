from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import replace
from functools import cache
from types import MappingProxyType
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.dataset_registry import registry_rows
from app.geo.records import DatasetRecord
from app.models import EnvDataset
from app.research.datasets import DatasetEntry

__all__ = [
    "CONTRIBUTED",
    "SET_PER_RUN",
    "SITE",
    "dataset_record",
    "dataset_registry",
    "entry_columns",
    "registry_entries",
    "sync_registry",
    "synced_columns",
]

SITE = "SITE"
SET_PER_RUN = "set per run"
CONTRIBUTED = "CONTRIBUTED"


def registry_entries(rows: Iterable[Mapping[str, Any]]) -> tuple[DatasetEntry, ...]:
    entries = tuple(DatasetEntry.model_validate(row) for row in rows)
    codes = [entry.code for entry in entries]
    if len(set(codes)) != len(codes):
        raise ValueError("The dataset registry records each dataset once")
    return entries


@cache
def dataset_registry() -> Mapping[str, DatasetEntry]:
    return MappingProxyType({entry.code: entry for entry in registry_entries(registry_rows())})


def entry_columns(entry: DatasetEntry) -> dict[str, Any]:
    return {
        "title": entry.title,
        "publisher": entry.publisher,
        "edition": entry.edition,
        "version": entry.version,
        "period": entry.period,
        "nativeResolution": entry.native_resolution,
        "crs": entry.crs,
        "licence": entry.licence,
        "licenceUrl": entry.licence_url,
        "attribution": entry.attribution,
        "redistributable": entry.redistributable,
        "citation": entry.citation,
        "doi": entry.doi,
        "landingUrl": entry.landing_url,
        "url": entry.url,
    }


def synced_columns(entry: DatasetEntry) -> dict[str, Any]:
    return {
        column: value
        for column, value in entry_columns(entry).items()
        if not (isinstance(value, str) and value.startswith(SET_PER_RUN))
    }


async def sync_registry(session: AsyncSession) -> list[str]:
    registry = dataset_registry()
    rows = (await session.scalars(select(EnvDataset).where(EnvDataset.code.in_(list(registry))))).all()
    for row in rows:
        for column, value in synced_columns(registry[row.code]).items():
            setattr(row, column, value)
    await session.flush()
    return sorted(row.code for row in rows)


def dataset_record(row: EnvDataset) -> DatasetRecord:
    short = DatasetRecord(
        code=row.code,
        title=row.title,
        publisher=row.publisher,
        edition=row.edition,
        period=row.period,
        native_resolution=row.nativeResolution,
        licence=row.licence,
        licence_url=row.licenceUrl,
        attribution=row.attribution,
        citation=row.citation,
        url=row.url,
    )
    if row.version is None:
        return short
    return replace(
        short,
        version=row.version,
        crs=row.crs,
        redistributable=row.redistributable,
        doi=row.doi,
        landing_url=row.landingUrl,
        read_on=None if row.retrievedAt is None else row.retrievedAt.date(),
        sha256=row.sha256,
    )
