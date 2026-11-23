from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any

from app.core.errors import InvalidInput
from app.geo.records import DatasetRecord
from app.research.datasets import DatasetRef

__all__ = ["region_dataset", "registry_row_ref", "value_grid"]


def region_dataset(dataset: DatasetRecord) -> DatasetRef:
    return DatasetRef(
        code=dataset.code,
        title=dataset.title,
        publisher=dataset.publisher,
        edition=dataset.edition,
        period=dataset.period,
        native_resolution=dataset.native_resolution,
        licence=dataset.licence,
        licence_url=dataset.licence_url,
        attribution=dataset.attribution,
        citation=dataset.citation,
        url=dataset.url,
        version=dataset.version,
        crs=dataset.crs,
        redistributable=dataset.redistributable,
        doi=dataset.doi,
        landing_url=dataset.landing_url,
        read_on=dataset.read_on,
        sha256=dataset.sha256,
    )


def registry_row_ref(row: Mapping[str, Any]) -> DatasetRef:
    retrieved = row.get("retrievedAt")
    return region_dataset(
        DatasetRecord(
            code=row["code"],
            title=row["title"],
            publisher=row.get("publisher"),
            edition=row.get("edition"),
            period=row.get("period"),
            native_resolution=row.get("nativeResolution"),
            licence=row.get("licence"),
            licence_url=row.get("licenceUrl"),
            attribution=row.get("attribution"),
            citation=row.get("citation"),
            url=row.get("url"),
            version=row.get("version"),
            crs=row.get("crs"),
            redistributable=row.get("redistributable"),
            doi=row.get("doi"),
            landing_url=row.get("landingUrl"),
            read_on=datetime.date.fromisoformat(str(retrieved)[:10]) if retrieved else None,
            sha256=row.get("sha256"),
        )
    )


def value_grid(resolution: str | None, dataset: DatasetRecord) -> str:
    grid = resolution or dataset.native_resolution
    if not grid:
        raise InvalidInput(f"{dataset.code} names no grid for a stored value")
    return grid
