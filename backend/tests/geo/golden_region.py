import json
from dataclasses import dataclass, replace
from decimal import ROUND_HALF_UP, Decimal
from functools import cache
from pathlib import Path
from typing import Any

from app.geo.layers import LAYERS_BY_ID
from app.geo.places import region_places
from app.geo.rainfall import RAINFALL_DATASET_CODE, DistrictRainfall, MonthValue, rainfall_from
from app.geo.records import (
    GEOLOGY_STAT,
    GEOLOGY_UNIT,
    GEOLOGY_VARIABLE,
    LITHOLOGY_TWIN_PREFIX,
    DatasetRecord,
    LayerListing,
    LayerRow,
    LayerValues,
    LocationRecord,
    RegionRecords,
    StateRecord,
    StoredLayer,
    ValueRecord,
)
from app.models import DistrictEnvValue, DistrictGeology
from app.research.blocks_place import DistrictRef
from app.research.citations import SourceRef
from app.research.crafts import CraftRef
from app.research.datasets import BOUNDARY_DATASET_CODE
from app.services.claim_seed import seed_id

from ..contracts.golden import golden_json
from ..contracts.phase_b_golden import catalog_dataset, geo_etl_datasets

GOLDEN_CRAFT = "region.craft.golden.json"
GOLDEN_LAYERS = "region.layers.golden.json"
GOLDEN_LAYER = "region.layer.golden.json"
EXTRACT = Path(__file__).with_name("geo_district_env_extract.json")

AJRAKH = CraftRef(slug="Kutch-Ajrakh", name="Kutch Ajrakh", path="/crafts/Kutch-Ajrakh")
GUJARAT = StateRecord(24, "Gujarat")
KACHCHH = 449
KACHCHH_DISTRICT = DistrictRef(district_lgd=KACHCHH, name="Kachchh", state_name="Gujarat")
VAV_THARAD = 789
GI_JOURNAL = str(seed_id("source", "ie:ajrakh:S1"))
GI_JOURNAL_TITLE = (
    "Geographical Indications Journal No. 188 (19 Dec 2023), G.I. Application No. 1050 - Kutch Ajrakh "
    "(journal copy)"
)
WORLDCOVER_READ = "40 m (overview read, factor 4, nearest)"
SOIL_PH_SERIES = ("SOILGRIDS_2_0", "phh2o", "0-5cm", "DISTRICT_MEAN")
LISTED = (("soil-ph-0-5cm", "pH"), ("annual-mean-temperature", "degC"), ("cropland-share", "fraction"))
LISTED_SERIES = (
    ("GHCN_CAMS_T2M", "annual_mean_temperature", "1981-2025", "NORMAL"),
    ("ESA_WORLDCOVER_2021_V200", "landcover_cropland", "2021", "SHARE"),
)


def column_digits(column: Any) -> int:
    return int(column.type.scale)


STORED_DIGITS = column_digits(DistrictEnvValue.__table__.c.value)
SHARE_DIGITS = column_digits(DistrictGeology.__table__.c.areaShare)


@dataclass(frozen=True)
class GeologyRow:
    district_lgd: int
    dataset_code: str
    lithology: str
    lithology_name: str | None
    area_share: float | None
    method: str
    mineral_occurrences: list[Any] | None


@cache
def _extract_text() -> str:
    return EXTRACT.read_text(encoding="utf-8")


def extract() -> dict[str, Any]:
    body: dict[str, Any] = json.loads(_extract_text())
    return body


def stored(value: float | None, digits: int = STORED_DIGITS) -> float | None:
    if value is None:
        return None
    places = Decimal(1).scaleb(-digits)
    return float(Decimal(repr(value)).quantize(places, rounding=ROUND_HALF_UP))


def series_of(row: ValueRecord) -> tuple[str, str, str, str]:
    return (row.dataset_code, row.variable, row.depth_or_period, row.stat)


def env_rows(district: int | None = None) -> tuple[ValueRecord, ...]:
    body = extract()
    methods = body["methods"]
    return tuple(
        ValueRecord(lgd, code, variable, period, stat, stored(value), text, unit, grid, methods[method])
        for lgd, code, variable, period, stat, value, text, unit, method, grid in body["values"]
        if district is None or lgd == district
    )


def geology_rows(district: int) -> tuple[GeologyRow, ...]:
    body = extract()
    return tuple(
        GeologyRow(lgd, code, lithology, name, stored(share, SHARE_DIGITS), body["methods"][method], found)
        for lgd, code, lithology, name, share, method, found in body["geology"]
        if lgd == district
    )


def region_rows(district: int) -> tuple[ValueRecord, ...]:
    kept = [row for row in env_rows(district) if not row.variable.startswith(LITHOLOGY_TWIN_PREFIX)]
    rocks = [
        ValueRecord(
            row.district_lgd,
            row.dataset_code,
            GEOLOGY_VARIABLE,
            "",
            GEOLOGY_STAT,
            row.area_share,
            row.lithology_name or row.lithology,
            GEOLOGY_UNIT,
            None,
            row.method,
        )
        for row in geology_rows(district)
        if row.area_share is not None
    ]
    return (*kept, *rocks)


def stored_row(district: int, series: tuple[str, str, str, str]) -> ValueRecord:
    [row] = [row for row in env_rows(district) if series_of(row) == series]
    return row


def kachchh_values() -> tuple[ValueRecord, ...]:
    return region_rows(KACHCHH)


def kachchh_monthly_rain() -> tuple[MonthValue, ...]:
    rows = extract()["monthlyRain"]["rows"]
    return tuple(
        MonthValue(depth_or_period=period, value=stored(value), unit=unit)
        for lgd, _code, _variable, period, _stat, value, _text, unit, _method, _grid in rows
        if lgd == KACHCHH
    )


def kachchh_rainfall() -> DistrictRainfall:
    chirps = replace(
        golden_datasets()[RAINFALL_DATASET_CODE], doi=geo_etl_datasets()[RAINFALL_DATASET_CODE]["doi"]
    )
    found = rainfall_from(KACHCHH_DISTRICT, chirps, kachchh_monthly_rain())
    assert found is not None
    return found


def layer_rows() -> tuple[ValueRecord, ...]:
    return tuple(row for row in env_rows() if series_of(row) == SOIL_PH_SERIES)


SOIL_PH = {row.district_lgd: row.value for row in layer_rows() if row.value is not None}
LISTED_ROWS = tuple(stored_row(KACHCHH, series) for series in LISTED_SERIES)


def dataset_record(row: dict[str, Any]) -> DatasetRecord:
    return DatasetRecord(
        code=row["code"],
        title=row["title"],
        publisher=row["publisher"],
        edition=row["edition"],
        period=row["period"],
        native_resolution=row["nativeResolution"],
        licence=row["licence"],
        licence_url=row["licenceUrl"],
        attribution=row["attribution"],
        citation=row["citation"],
        url=row["url"],
    )


def run_periods() -> dict[str, str]:
    return {code: period for run in extract()["runs"] for code, period in run["periods"].items()}


def golden_datasets() -> dict[str, DatasetRecord]:
    periods = run_periods()
    rows = {code: catalog_dataset(code) | {"period": period} for code, period in periods.items()}
    rows[BOUNDARY_DATASET_CODE] = catalog_dataset(BOUNDARY_DATASET_CODE)
    return {code: dataset_record(row) for code, row in sorted(rows.items())}


def location(**changes: Any) -> LocationRecord:
    fields: dict[str, Any] = {
        "id": "location-kachchh",
        "precision": "DISTRICT",
        "state": GUJARAT,
        "district_lgd": KACHCHH,
        "district_name": "Kachchh",
        "has_polygon": True,
        "place_label": "Ajrakhpur, Kachchh",
        "source_id": GI_JOURNAL,
        "source_title": GI_JOURNAL_TITLE,
        "level": "PROVISIONAL",
    }
    return LocationRecord(**(fields | changes))


def gi_journal_source() -> SourceRef:
    [found] = [s for s in golden_json("science.process.golden.json")["sources"] if s["id"] == GI_JOURNAL]
    return SourceRef.model_validate(found)


def golden_region_records() -> RegionRecords:
    return RegionRecords(
        craft=AJRAKH,
        places=region_places([location()], [GUJARAT]),
        district_values=kachchh_values(),
        state_totals=(),
        district_totals={},
        datasets=golden_datasets(),
        sources={GI_JOURNAL: gi_journal_source()},
    )


def golden_listing() -> LayerListing:
    datasets = golden_datasets()
    layers = tuple(StoredLayer(LAYERS_BY_ID[layer_id], unit) for layer_id, unit in LISTED)
    codes = {layer.spec.dataset_code for layer in layers}
    return LayerListing(
        layers=layers,
        datasets={code: datasets[code] for code in codes},
        boundary=datasets[BOUNDARY_DATASET_CODE],
    )


def golden_layer_values() -> LayerValues:
    datasets = golden_datasets()
    rows = sorted(layer_rows(), key=lambda row: row.district_lgd, reverse=True)
    return LayerValues(
        layer=StoredLayer(LAYERS_BY_ID["soil-ph-0-5cm"], "pH"),
        dataset=datasets["SOILGRIDS_2_0"],
        rows=tuple(
            LayerRow(row.district_lgd, row.value, row.resolution) for row in rows if row.value is not None
        ),
        boundary=datasets[BOUNDARY_DATASET_CODE],
    )
