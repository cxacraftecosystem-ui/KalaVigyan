from typing import Any

from app.geo.layers import LAYERS_BY_ID
from app.geo.places import region_places
from app.geo.records import (
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
from app.research.citations import SourceRef
from app.research.crafts import CraftRef
from app.services.claim_seed import seed_id

from ..contracts.golden import golden_json

GOLDEN_CRAFT = "region.craft.golden.json"
GOLDEN_LAYERS = "region.layers.golden.json"
GOLDEN_LAYER = "region.layer.golden.json"

AJRAKH = CraftRef(slug="Kutch-Ajrakh", name="Kutch Ajrakh", path="/crafts/Kutch-Ajrakh")
GUJARAT = StateRecord(24, "Gujarat")
KACHCHH = 449
VAV_THARAD = 789
GI_JOURNAL = str(seed_id("source", "ie:ajrakh:S1"))
GI_JOURNAL_TITLE = (
    "Geographical Indications Journal No. 188 (19 Dec 2023), G.I. Application No. 1050 - Kutch Ajrakh "
    "(journal copy)"
)
WORLDCOVER_READ = "40 m (overview read, factor 4, nearest)"

CROPLAND = (
    "ESA_WORLDCOVER_2021_V200",
    "landcover_cropland",
    "2021",
    "SHARE",
    0.236,
    "fraction",
    WORLDCOVER_READ,
)
TEMPERATURE_NORMAL = (
    "GHCN_CAMS_T2M",
    "annual_mean_temperature",
    "1981-2025",
    "NORMAL",
    27.07,
    "degC",
    "0.5 degree",
)
KACHCHH_ROWS = (
    CROPLAND,
    ("SOILGRIDS_2_0", "phh2o", "0-5cm", "DISTRICT_MEAN", 8.1, "pH", None),
    ("USGS_MRDS", "mineral_occurrences", "", "COUNT", 41.0, "sites", None),
    ("CHELSA_2_1_1981_2010", "annual_precipitation", "1981-2010", "NORMAL", 372.4, "mm/year", None),
    ("SOILGRIDS_2_0", "clay", "0-5cm", "DISTRICT_MEAN", 27.4, "%", None),
    ("COPERNICUS_DEM_GLO90", "elevation", "", "DISTRICT_MEAN", 52.3, "m", None),
    ("CHELSA_2_1_1981_2010", "annual_mean_temperature", "1981-2010", "NORMAL", 26.6, "degC", None),
    (
        "ESA_WORLDCOVER_2021_V200",
        "landcover_bare_sparse_vegetation",
        "2021",
        "SHARE",
        0.312,
        "fraction",
        WORLDCOVER_READ,
    ),
)
SOIL_PH = {438: 7.8, 441: 7.6, 444: 6.4, 447: 7.9, 449: 8.1, 455: 8.0, 459: 7.2, 460: 8.3, 462: 6.9}
LISTED = (("soil-ph-0-5cm", "pH"), ("annual-mean-temperature", "degC"), ("cropland-share", "fraction"))
LISTED_ROWS = (TEMPERATURE_NORMAL, CROPLAND)


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


def golden_datasets() -> dict[str, DatasetRecord]:
    rows = [*golden_json(GOLDEN_CRAFT)["datasets"], *golden_json(GOLDEN_LAYERS)["datasets"]]
    rows.append(golden_json(GOLDEN_LAYERS)["boundary"]["dataset"])
    return {row["code"]: dataset_record(row) for row in rows}


def golden_methods() -> dict[str, str]:
    facets = golden_json(GOLDEN_CRAFT)["places"][0]["facets"]
    return {value["datasetCode"]: value["method"] for facet in facets for value in facet["values"]}


def kachchh_values() -> tuple[ValueRecord, ...]:
    methods = golden_methods()
    return tuple(
        ValueRecord(KACHCHH, code, variable, stored, stat, value, None, unit, grid, methods[code])
        for code, variable, stored, stat, value, unit, grid in KACHCHH_ROWS
    )


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
        coverage=(),
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
        boundary=datasets["DR_DISTRICT_SHAPES"],
    )


def golden_layer_values() -> LayerValues:
    datasets = golden_datasets()
    return LayerValues(
        layer=StoredLayer(LAYERS_BY_ID["soil-ph-0-5cm"], "pH"),
        dataset=datasets["SOILGRIDS_2_0"],
        rows=tuple(LayerRow(lgd, value, None) for lgd, value in reversed(SOIL_PH.items())),
        boundary=datasets["DR_DISTRICT_SHAPES"],
    )
