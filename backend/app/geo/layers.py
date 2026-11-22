from __future__ import annotations

import hashlib
import json
import statistics
from collections.abc import Iterable, Mapping, Sequence
from itertools import pairwise
from types import MappingProxyType
from typing import Any

from app.core.errors import InvalidInput
from app.geo.climate import MEAN_STAT, TREND_DATASETS
from app.geo.datasets import region_dataset, value_grid
from app.geo.records import DatasetRecord, LayerListing, LayerSpec, LayerValues, StoredLayer
from app.research.datasets import BOUNDARY_CAPTION, BOUNDARY_DATASET_CODE, INDIA_OUTLINE_CAPTION
from app.schemas.region import (
    LAYER_CLASS_MAX,
    BoundaryNote,
    LayerClass,
    MapLayer,
    MapLayerList,
    MapLayerSummary,
    split_depth_or_period,
)

__all__ = [
    "BREAK_FIGURES",
    "LAYERS_BY_ID",
    "MAP_LAYERS",
    "boundary_note",
    "layer_unit",
    "layer_version",
    "map_layer",
    "map_layer_list",
    "quantile_classes",
    "stored_depth_or_period",
]

BREAK_FIGURES = 3
GRID_SEPARATOR = "; "


def _soil(id_: str, title: str, variable: str) -> LayerSpec:
    return LayerSpec(id_, title, "SOILGRIDS_2_0", variable, "0-5cm", "DISTRICT_MEAN")


def _cover(id_: str, title: str, variable: str) -> LayerSpec:
    return LayerSpec(id_, title, "ESA_WORLDCOVER_2021_V200", f"landcover_{variable}", "2021", "SHARE")


def _chelsa(id_: str, title: str, variable: str) -> LayerSpec:
    return LayerSpec(id_, title, "CHELSA_2_1_1981_2010", variable, "1981-2010", MEAN_STAT)


def _trend_normal(id_: str, title: str, variable: str) -> LayerSpec:
    return LayerSpec(id_, title, TREND_DATASETS[variable], variable, None, MEAN_STAT)


MAP_LAYERS: tuple[LayerSpec, ...] = (
    _soil("soil-ph-0-5cm", "Soil pH, 0-5 cm", "phh2o"),
    _soil("soil-organic-carbon-0-5cm", "Soil organic carbon, 0-5 cm", "soc"),
    _soil("clay-0-5cm", "Clay, 0-5 cm", "clay"),
    _soil("sand-0-5cm", "Sand, 0-5 cm", "sand"),
    _soil("cation-exchange-0-5cm", "Cation exchange capacity, 0-5 cm", "cec"),
    _trend_normal("annual-mean-temperature", "Annual mean temperature", "annual_mean_temperature"),
    _chelsa("warmest-month-maximum", "Warmest-month maximum temperature", "max_temperature_warmest_month"),
    _chelsa("coldest-month-minimum", "Coldest-month minimum temperature", "min_temperature_coldest_month"),
    _trend_normal("annual-precipitation", "Annual precipitation", "annual_precipitation"),
    LayerSpec(
        "monsoon-share", "Monsoon share of rainfall", "CHIRPS_3_0", "monsoon_share_jjas", None, "NORMAL"
    ),
    LayerSpec("river-density", "River density", "HYDRORIVERS_1_0", "river_density", "", "DENSITY"),
    LayerSpec(
        "distance-to-major-river",
        "Distance to a major river",
        "HYDRORIVERS_1_0",
        "distance_centroid_to_major_river",
        "",
        "DISTANCE",
    ),
    LayerSpec(
        "tree-cover-2000",
        "Tree cover in 2000",
        "HANSEN_GFC_2025_V1_13",
        "treecover2000",
        "2000",
        "DISTRICT_MEAN",
    ),
    LayerSpec(
        "forest-loss-2001-2025",
        "Forest loss, 2001-2025",
        "HANSEN_GFC_2025_V1_13",
        "forest_loss_canopy30_share",
        "2001-2025",
        "SHARE",
    ),
    _cover("tree-cover-share", "Tree cover share", "tree_cover"),
    _cover("cropland-share", "Cropland share", "cropland"),
    _cover("built-up-share", "Built-up share", "built_up"),
    _cover("bare-ground-share", "Bare or sparse vegetation share", "bare_sparse_vegetation"),
    LayerSpec("elevation", "Elevation", "COPERNICUS_DEM_GLO90", "elevation", "", "DISTRICT_MEAN"),
    LayerSpec("slope", "Slope", "COPERNICUS_DEM_GLO90", "slope", "", "DISTRICT_MEAN"),
    LayerSpec("mineral-sites", "Mineral sites", "USGS_MRDS", "mineral_occurrences", "", "COUNT"),
)
LAYERS_BY_ID = MappingProxyType({spec.id: spec for spec in MAP_LAYERS})


def stored_depth_or_period(spec: LayerSpec, dataset: DatasetRecord) -> str | None:
    return dataset.period if spec.depth_or_period is None else spec.depth_or_period


def layer_unit(spec: LayerSpec, units: Iterable[str | None]) -> str:
    found = set(units)
    if len(found) != 1 or None in found:
        raise InvalidInput(f"layer {spec.id} has units {sorted(map(str, found))}; it needs exactly one")
    return str(found.pop())


def boundary_note(dataset: DatasetRecord) -> BoundaryNote:
    if dataset.code != BOUNDARY_DATASET_CODE:
        raise InvalidInput(f"the boundary note cites {BOUNDARY_DATASET_CODE}, not {dataset.code}")
    return BoundaryNote(caption=BOUNDARY_CAPTION, dataset=region_dataset(dataset))


def map_layer_list(listing: LayerListing) -> MapLayerList:
    if listing.boundary is None:
        raise InvalidInput(f"no {BOUNDARY_DATASET_CODE} dataset row to cite beneath the map")
    codes = sorted({layer.spec.dataset_code for layer in listing.layers})
    return MapLayerList(
        layers=[_summary(layer, listing.datasets[layer.spec.dataset_code]) for layer in listing.layers],
        datasets=[region_dataset(listing.datasets[code]) for code in codes],
        boundary=boundary_note(listing.boundary),
        outline_caption=INDIA_OUTLINE_CAPTION,
    )


def map_layer(stored: LayerValues) -> MapLayer:
    if not stored.rows:
        raise InvalidInput(f"layer {stored.layer.spec.id} has no district values")
    rows = sorted(stored.rows, key=lambda row: row.district_lgd)
    dataset = stored.dataset
    parts: dict[str, Any] = {
        "layer": _summary(stored.layer, dataset).model_dump(mode="json", by_alias=True),
        "dataset": region_dataset(dataset).model_dump(mode="json", by_alias=True),
        "resolution": GRID_SEPARATOR.join(sorted({value_grid(row.resolution, dataset) for row in rows})),
        "classes": [band.model_dump(mode="json") for band in quantile_classes([row.value for row in rows])],
        "values": {str(row.district_lgd): row.value for row in rows},
        "boundary": boundary_note(stored.boundary).model_dump(mode="json", by_alias=True),
    }
    return MapLayer.model_validate({**parts, "version": layer_version(parts)})


def quantile_classes(values: Sequence[float]) -> list[LayerClass]:
    if not values:
        raise InvalidInput("a layer needs at least one value to class")
    ordered = sorted(values)
    low, high = ordered[0], ordered[-1]
    count = min(LAYER_CLASS_MAX, len(set(ordered)))
    cuts = statistics.quantiles(ordered, n=count, method="inclusive") if count > 1 else []
    inner = sorted({rounded for cut in cuts if low < (rounded := _figures(cut)) < high})
    return [LayerClass(min=a, max=b) for a, b in pairwise([low, *inner, high])]


def layer_version(parts: Mapping[str, Any]) -> str:
    canonical = json.dumps(parts, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _summary(layer: StoredLayer, dataset: DatasetRecord) -> MapLayerSummary:
    spec = layer.spec
    stored = stored_depth_or_period(spec, dataset)
    if stored is None:
        raise InvalidInput(f"layer {spec.id}: {dataset.code} names no period")
    depth, period = split_depth_or_period(stored, dataset.period or "")
    return MapLayerSummary(
        id=spec.id,
        facet=spec.facet,
        title=spec.title,
        dataset_code=spec.dataset_code,
        variable=spec.variable,
        depth=depth,
        period=period,
        stat=spec.stat,
        unit=layer.unit,
    )


def _figures(value: float) -> float:
    return float(f"{value:.{BREAK_FIGURES}g}")
