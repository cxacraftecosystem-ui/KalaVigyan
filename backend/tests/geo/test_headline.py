import dataclasses
from collections import Counter

from app.geo.headline import HEADLINE_SERIES, headline_rows
from app.geo.places import region_places
from app.geo.records import SeriesTotals
from app.geo.region_view import craft_region, district_value, region_facets

from .golden_region import GUJARAT, KACHCHH, SOIL_PH_SERIES, golden_region_records, location, stored_row

SOIL = "SOILGRIDS_2_0"
CHELSA = "CHELSA_2_1_1981_2010"
CHIRPS = "CHIRPS_3_0"
GHCN = "GHCN_CAMS_T2M"
RIVERS = "HYDRORIVERS_1_0"
FOREST = "HANSEN_GFC_2025_V1_13"
COVER = "ESA_WORLDCOVER_2021_V200"
RELIEF = "COPERNICUS_DEM_GLO90"


def listed(facet: str) -> list[tuple[str, str, str | None, str]]:
    return [(s.dataset_code, s.variable, s.depth_or_period, s.stat) for s in HEADLINE_SERIES[facet]]


def test_each_facet_heads_with_its_map_layers_the_two_climate_trends_and_the_rock_types() -> None:
    assert listed("SOIL") == [
        (SOIL, variable, "0-5cm", "DISTRICT_MEAN") for variable in ("phh2o", "soc", "clay", "sand", "cec")
    ]
    assert listed("CLIMATE") == [
        (GHCN, "annual_mean_temperature", None, "NORMAL"),
        (CHELSA, "max_temperature_warmest_month", "1981-2010", "NORMAL"),
        (CHELSA, "min_temperature_coldest_month", "1981-2010", "NORMAL"),
        (CHIRPS, "annual_precipitation", None, "NORMAL"),
        (CHIRPS, "monsoon_share_jjas", None, "NORMAL"),
        (CHIRPS, "annual_precipitation", None, "TREND_PER_DECADE"),
        (CHIRPS, "annual_precipitation", None, "TREND_P_VALUE"),
        (GHCN, "annual_mean_temperature", None, "TREND_PER_DECADE"),
        (GHCN, "annual_mean_temperature", None, "TREND_P_VALUE"),
    ]
    assert listed("WATER") == [
        (RIVERS, "river_density", "", "DENSITY"),
        (RIVERS, "distance_centroid_to_major_river", "", "DISTANCE"),
    ]
    assert listed("FOREST") == [
        (FOREST, "treecover2000", "2000", "DISTRICT_MEAN"),
        (FOREST, "forest_loss_canopy30_share", "2001-2025", "SHARE"),
    ]
    assert listed("LAND_COVER") == [
        (COVER, f"landcover_{cover}", "2021", "SHARE")
        for cover in ("tree_cover", "cropland", "built_up", "bare_sparse_vegetation")
    ]
    assert listed("TERRAIN") == [
        (RELIEF, "elevation", "", "DISTRICT_MEAN"),
        (RELIEF, "slope", "", "DISTRICT_MEAN"),
    ]
    assert listed("GEOLOGY") == [
        ("USGS_MRDS", "mineral_occurrences", "", "COUNT"),
        ("GLIM_1_0_05DEG", "lithology", "", "SHARE"),
    ]


def test_kachchh_shows_its_headline_values_and_leaves_the_rest_to_the_map() -> None:
    records = golden_region_records()
    [place] = craft_region(records).places
    shown = Counter(facet.facet for facet in place.facets for _ in facet.values)
    assert shown == {
        "SOIL": 5,
        "CLIMATE": 9,
        "WATER": 2,
        "FOREST": 2,
        "LAND_COVER": 4,
        "TERRAIN": 2,
        "GEOLOGY": 6,
    }
    stats = {value.stat for facet in place.facets for value in facet.values}
    assert not stats & {
        "DISTRICT_P10",
        "DISTRICT_P90",
        "DISTRICT_MIN",
        "DISTRICT_MAX",
        "UNCERTAINTY_Q05_MEAN",
    }
    assert not {value.period for facet in place.facets for value in facet.values} & {"1981", "2025"}


def test_the_map_s_district_panel_still_lists_every_stored_value() -> None:
    records = golden_region_records()
    values = [district_value(row, records.datasets[row.dataset_code]) for row in records.district_values]
    soil = next(facet for facet in region_facets(values) if facet.facet == "SOIL")
    assert len(soil.values) == 8 * 5


def test_a_normal_stored_over_another_period_than_its_dataset_s_is_not_a_headline() -> None:
    records = golden_region_records()
    normal = stored_row(KACHCHH, (CHIRPS, "annual_precipitation", "1981-2025", "NORMAL"))
    older = dataclasses.replace(normal, depth_or_period="2016-2025")
    assert headline_rows([normal, older], records.datasets) == [normal]


def test_a_state_place_shows_only_its_headline_aggregates() -> None:
    surface = SeriesTotals(
        GUJARAT.lgd, *SOIL_PH_SERIES, "pH", None, 2, 29.0, 4.0, 15.0, 7.0, 8.0, (None,), (), 2, 4.0
    )
    deeper = dataclasses.replace(surface, depth_or_period="5-15cm")
    vav = location(id="location-vav", district_lgd=789, district_name="Vav-Tharad", has_polygon=False)
    records = dataclasses.replace(
        golden_region_records(),
        places=region_places([vav], []),
        district_values=(),
        state_totals=(surface, deeper),
        district_totals={GUJARAT.lgd: 34},
    )
    [place] = craft_region(records).places
    assert [(v.depth, v.value) for f in place.facets for v in f.values] == [("0-5cm", 7.25)]
