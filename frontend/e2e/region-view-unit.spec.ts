import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";

import type { CraftPage, PagePlace } from "@/lib/craftPageContract";
import { pageSourceNumbers, pageSourcesById, sourceGroups } from "@/lib/craftPageView";
import { placesInDistrict } from "@/lib/craftPlaces";
import { chosenLayerId } from "@/lib/mapLayers";
import { craftRegionShape, mapLayerListShape, mapLayerShape, type CraftRegion, type MapLayer, type RegionPlace } from "@/lib/regionContract";
import {
  checkedLayer,
  checkedRegion,
  datasetIndex,
  datasetMethods,
  datasetOf,
  inheritedNote,
  layerCaption,
  layerClassLabels,
  layerFills,
  layerOptions,
  layerSummary,
  periodText,
  placeSubtitle,
  regionHighlight,
  shownFacets,
  statCaption,
  toneIndex,
  valueLabel,
  valueProvenance,
  valueReading
} from "@/lib/regionView";
import { parseShape, ShapeError } from "@/lib/shape";

import { emptyPage } from "./craftPageFixture";

const SHARED = join(__dirname, "..", "..", "shared");

function golden<T>(name: string): T {
  return JSON.parse(readFileSync(join(SHARED, name), "utf8")) as T;
}

function region(edit: (body: CraftRegion) => void = () => undefined): CraftRegion {
  const body = golden<CraftRegion>("region.craft.golden.json");
  edit(body);
  return checkedRegion(parseShape(craftRegionShape, body));
}

function layer(edit: (body: MapLayer) => void = () => undefined): MapLayer {
  const body = golden<MapLayer>("region.layer.golden.json");
  edit(body);
  return checkedLayer(parseShape(mapLayerShape, body));
}

const SHOWN_FACETS = ["SOIL", "CLIMATE", "WATER", "FOREST", "LAND_COVER", "TERRAIN", "GEOLOGY"];

function facetOf(place: RegionPlace, name: string) {
  const found = place.facets.find((facet) => facet.facet === name);
  if (!found) throw new Error(`the golden place has no ${name} facet`);
  return found;
}

function inherited(place: RegionPlace): RegionPlace {
  return {
    ...place,
    valuesFrom: "STATE",
    inheritedReason: "NO_DISTRICT_POLYGON",
    facets: [
      {
        facet: "SOIL",
        values: [{ ...place.facets[0].values[0], aggregation: "STATE_AREA_MEAN", value: 7.6, districtCount: 31, districtTotal: 33 }]
      }
    ]
  };
}

test("each Kachchh headline value reads with its unit", () => {
  const values = region().places[0].facets.flatMap((facet) => facet.values);
  expect(values.map((value) => [valueLabel(value), valueReading(value)])).toEqual([
    ["Cation exchange capacity, 0–5 cm", "22.32 cmol(c)/kg"],
    ["Clay, 0–5 cm", "22.22%"],
    ["Soil pH (in water), 0–5 cm", "pH 7.28"],
    ["Sand, 0–5 cm", "49.95%"],
    ["Soil organic carbon, 0–5 cm", "12.27 g/kg"],
    ["Warmest-month maximum temperature", "38.19 °C"],
    ["Coldest-month minimum temperature", "13.21 °C"],
    ["Annual precipitation", "449.36 mm/year"],
    ["Annual precipitation", "70.76 mm/year per decade"],
    ["Annual precipitation", "p = 0.005"],
    ["Monsoon share, June–September", "96.09% of annual"],
    ["Annual mean temperature", "27.07 °C"],
    ["Annual mean temperature", "0.3 °C per decade"],
    ["Annual mean temperature", "p < 0.001"],
    ["Distance to a major river", "56.76 km"],
    ["River density", "0.24 km/km²"],
    ["Share of the 2000 forest lost", "2.59% of 2000 forest"],
    ["Tree cover in 2000", "0%"],
    ["Bare or sparse vegetation", "25.46%"],
    ["Built-up", "0.89%"],
    ["Cropland", "30.14%"],
    ["Tree cover", "1.65%"],
    ["Elevation", "36.87 m"],
    ["Slope", "0.74°"],
    ["Rock type", "Basic volcanic rocks · 9.38%"],
    ["Rock type", "Evaporites · 0.4%"],
    ["Rock type", "Mixed sedimentary rocks · 5.92%"],
    ["Rock type", "Siliciclastic sedimentary rocks · 14.67%"],
    ["Rock type", "Unconsolidated sediments · 69.64%"],
    ["Mineral sites", "0 sites"]
  ]);
});

test("every value names its statistic, dataset, grid and period", () => {
  const body = region();
  const index = datasetIndex(body.datasets);
  const soil = facetOf(body.places[0], "SOIL").values[0];
  const cover = facetOf(body.places[0], "LAND_COVER").values[0];
  expect(valueProvenance(soil, datasetOf(index, soil.datasetCode))).toBe("District mean · SoilGrids 2.0 · 250 m · modelled, 2020 release");
  expect(valueProvenance(cover, datasetOf(index, cover.datasetCode))).toBe(
    "Share of district area · ESA WorldCover 10 m 2021 v200 · 40 m (overview read, factor 4, nearest) · 2021"
  );
});

test("a district place names its district and is highlighted alone", () => {
  const body = region();
  const place = body.places[0];
  expect(place.placeLabel).toBe("Kachchh");
  expect(placeSubtitle(place, [])).toBe("District, Gujarat");
  expect(inheritedNote(place)).toBeNull();
  expect(shownFacets(place).map((facet) => facet.facet)).toEqual(SHOWN_FACETS);
  const highlight = regionHighlight(body);
  expect([...highlight.districts]).toEqual([449]);
  expect([...highlight.states]).toEqual([]);
});

test("facets arriving out of order are shown in the contract order", () => {
  const body = region((value) => value.places[0].facets.reverse());
  expect(shownFacets(body.places[0]).map((facet) => facet.facet)).toEqual(SHOWN_FACETS);
});

test("a district without an outline shows its state's values and says so", () => {
  const body = region((value) => (value.places[0] = inherited(value.places[0])));
  const place = body.places[0];
  expect(inheritedNote(place)).toBe("Values for Gujarat as a whole; Kachchh has no district outline.");
  expect(statCaption(place.facets[0].values[0])).toBe("State mean, area-weighted of 31 of 33 districts");
  expect([...regionHighlight(body).states]).toEqual([24]);
  expect([...regionHighlight(body).districts]).toEqual([]);
});

test("a state of practice reads as practised across the state", () => {
  const body = region((value) => {
    value.places[0] = {
      ...value.places[0],
      key: "state-24",
      scope: "STATE",
      districtLgd: null,
      districtName: null,
      placeLabel: "Gujarat",
      basis: { kind: "MASTER_LIST", sourceId: null, label: "IIT Crafts Master List, 2026-10-20", level: "REVIEWED" },
      valuesFrom: "STATE",
      facets: []
    };
  });
  const place = body.places[0];
  expect(placeSubtitle(place, [])).toBe("Practised across the state");
  expect(inheritedNote(place)).toBeNull();
  expect(shownFacets(place)).toEqual([]);
  expect([...regionHighlight(body).states]).toEqual([24]);
});

function pagePlace(name: string, kind: PagePlace["kind"], role: PagePlace["role"], district: PagePlace["district"]): PagePlace {
  return { key: `${name}-${role}`, name, kind, role, district, state: { lgd: 24, name: "Gujarat" }, country: "India", wikidataId: null, claimIds: [] };
}

test("a district card names the craft's making places inside it, once each, and no place outside it", () => {
  const kachchh = { lgd: 449, name: "Kachchh" };
  const places = [
    pagePlace("Ajrakhpur", "VILLAGE", "PRACTISED", kachchh),
    pagePlace("Ajrakhpur", "VILLAGE", "MIGRATED_TO", kachchh),
    pagePlace("Dhamadka", "VILLAGE", "HISTORIC_CENTRE", kachchh),
    pagePlace("Khavda", "VILLAGE", "PRACTISED", kachchh),
    pagePlace("Dhamadka River (Suran)", "RIVER", "MATERIAL_SOURCE", kachchh),
    pagePlace("Kachchh", "DISTRICT", "PRACTISED", kachchh),
    pagePlace("Pethapur", "VILLAGE", "MATERIAL_SOURCE", { lgd: 441, name: "Gandhinagar" }),
    pagePlace("Barmer", "DISTRICT", "PRACTISED", { lgd: 99, name: "Barmer" })
  ];
  const named = placesInDistrict(places, 449);
  expect(named).toEqual(["Ajrakhpur", "Dhamadka", "Khavda"]);
  expect(placeSubtitle(region().places[0], named)).toBe("District, Gujarat · includes Ajrakhpur, Dhamadka and Khavda");
  expect(placesInDistrict(places, 99)).toEqual([]);
});

test("raw codes, units and periods read in words", () => {
  const [first] = region().places[0].facets[0].values;
  const bulk = { ...first, variable: "bdod", depth: "0-5cm", unit: "kg/dm3", value: 1.45 };
  expect([valueLabel(bulk), valueReading(bulk)]).toEqual(["Bulk density, 0–5 cm", "1.45 g/cm³"]);
  const january = { ...first, datasetCode: "CHELSA_2_1_1981_2010", variable: "mean_temperature", depth: null, period: "1981-2010-01", stat: "NORMAL" as const, unit: "degC", value: 19.56, resolution: "30 arc-seconds (about 1 km)" };
  expect(valueLabel(january)).toBe("Mean temperature, January");
  expect(periodText(january.period)).toBe("1981–2010");
  expect(periodText("2001-2025")).toBe("2001–2025");
  expect(periodText("modelled, 2020 release")).toBe("modelled, 2020 release");
  const significance = { ...first, variable: "annual_precipitation", depth: null, period: "1981-2025", stat: "TREND_P_VALUE" as const, unit: "p-value", value: 0.0000123 };
  expect([valueLabel(significance), valueReading(significance)]).toEqual(["Annual precipitation", "p < 0.001"]);
  const canopy = { ...first, variable: "forest_loss_canopy30_share", depth: null, period: "2001-2025", stat: "SHARE" as const, unit: "fraction of 2000 forest", value: 0.0259 };
  expect([valueLabel(canopy), valueReading(canopy), statCaption(canopy)]).toEqual(["Share of the 2000 forest lost", "2.59% of 2000 forest", "Share of the 2000 forest"]);
  const cover = { ...canopy, variable: "forest_canopy30", period: "2000", unit: "fraction of land", value: 0.012 };
  expect([valueLabel(cover), valueReading(cover), statCaption(cover)]).toEqual(["Forest cover, canopy of 30% or more", "1.2% of land", "Share of district land"]);
  const lost = layer((body) => (body.layer = { ...body.layer, stat: "SHARE", unit: "fraction of 2000 forest" }));
  expect(layerCaption(lost).split(" · ")[0]).toBe("Share of the 2000 forest");
  const order = { ...first, datasetCode: "HYDRORIVERS_1_0", variable: "max_strahler_order", depth: null, period: "static", stat: "DISTRICT_MAX" as const, unit: "Strahler order", value: 6 };
  expect([valueLabel(order), valueReading(order)]).toEqual(["Largest river order (Strahler)", "6"]);
  const slope = { ...first, datasetCode: "COPERNICUS_DEM_GLO90", variable: "slope", depth: null, period: "2011-2015 acquisitions", stat: "DISTRICT_MEAN" as const, unit: "degree", value: 0.74 };
  expect(valueReading(slope)).toBe("0.74°");
  const seasonality = { ...first, datasetCode: "CHELSA_2_1_1981_2010", variable: "precipitation_seasonality", depth: null, period: "1981-2010", stat: "NORMAL" as const, unit: "coefficient of variation %", value: 150.11 };
  expect(valueReading(seasonality)).toBe("150.11%");
  const index = datasetIndex(region().datasets);
  expect(valueProvenance(january, datasetOf(index, january.datasetCode))).toBe("Climate normal · CHELSA V2.1 climatologies 1981-2010 · 30 arc-seconds (about 1 km) · 1981–2010");
});

test("a craft with no places has nothing to highlight", () => {
  const body = region((value) => (value.places = []));
  const highlight = regionHighlight(body);
  expect(highlight.districts.size + highlight.states.size).toBe(0);
});

test("a geology share reads as its rock type and share", () => {
  const body = region((value) => {
    const geology = facetOf(value.places[0], "GEOLOGY");
    geology.values = [{ ...geology.values[0], variable: "lithology", valueText: "Sandstone", value: 0.42, unit: "fraction", stat: "SHARE" }];
  });
  const [rock] = facetOf(body.places[0], "GEOLOGY").values;
  expect(valueReading(rock)).toBe("Sandstone · 42%");
  expect(valueLabel(rock)).toBe("Rock type");
});

test("each dataset lists its distinct methods once", () => {
  const methods = datasetMethods(region());
  expect(methods.get("CHELSA_2_1_1981_2010")).toHaveLength(1);
  expect(methods.get("SOILGRIDS_2_0")).toHaveLength(1);
  expect(methods.get("CHIRPS_3_0")).toHaveLength(2);
  expect([...methods.keys()].sort()).toEqual([
    "CHELSA_2_1_1981_2010",
    "CHIRPS_3_0",
    "COPERNICUS_DEM_GLO90",
    "ESA_WORLDCOVER_2021_V200",
    "GHCN_CAMS_T2M",
    "GLIM_1_0_05DEG",
    "HANSEN_GFC_2025_V1_13",
    "HYDRORIVERS_1_0",
    "SOILGRIDS_2_0",
    "USGS_MRDS"
  ]);
});

test("a location's source is numbered and linked even when no claim cites it", () => {
  const body = region();
  const [place] = body.places;
  const page: CraftPage = emptyPage();
  expect([page.claims.length, page.sources.length]).toEqual([0, 0]);
  const numbers = pageSourceNumbers(page, body.sources);
  const byId = pageSourcesById(page, body.sources);
  expect(place.basis.kind).toBe("CRAFT_LOCATION");
  expect(numbers.get(place.basis.sourceId ?? "")).toBe(1);
  expect(byId.get(place.basis.sourceId ?? "")?.url).toBe("https://search.ipindia.gov.in/GIRPublicSearch/Application/Details/1050");
  expect(sourceGroups(byId.values(), numbers).flatMap((group) => group.sources.map((source) => source.id))).toEqual([place.basis.sourceId]);
});

test("the client refuses a place whose source is not listed", () => {
  expect(() => region((value) => (value.sources = []))).toThrow(ShapeError);
});

test("the client refuses a value whose dataset is not listed", () => {
  expect(() => region((value) => (value.datasets = value.datasets.filter((dataset) => dataset.code !== "USGS_MRDS")))).toThrow(ShapeError);
});

test("every district value falls in its quantile class", () => {
  const fills = layerFills(layer());
  expect(Object.fromEntries([...fills.entries()].map(([lgd, band]) => [String(lgd), band]))).toEqual({
    "438": 3,
    "441": 4,
    "444": 0,
    "447": 1,
    "449": 3,
    "455": 4,
    "459": 1,
    "460": 3,
    "462": 0
  });
});

test("the legend, caption and summary read from the layer", () => {
  const soil = layer();
  expect(layerClassLabels(soil)).toEqual(["pH 6.67–6.88", "pH 6.88–7.09", "pH 7.09–7.28", "pH 7.28–7.31", "pH 7.31–7.35"]);
  expect(layerCaption(soil)).toBe("District mean · SoilGrids 2.0 · 250 m · modelled, 2020 release");
  expect(layerSummary(soil)).toBe("Soil pH, 0-5 cm: 9 districts, pH 6.67–7.35.");
});

test("an empty layer or a mismatched dataset is refused", () => {
  expect(() => layer((value) => (value.values = {}))).toThrow(ShapeError);
  expect(() => layer((value) => (value.layer = { ...value.layer, datasetCode: "CHELSA_2_1_1981_2010" }))).toThrow(ShapeError);
});

test("layers are offered by facet and a requested id must be listed", () => {
  const list = parseShape(mapLayerListShape, golden("region.layers.golden.json"));
  expect(layerOptions(list).map((option) => [option.group, option.value, option.hint])).toEqual([
    ["Soil", "soil-ph-0-5cm", "modelled, 2020 release"],
    ["Climate", "annual-mean-temperature", "1981–2025"],
    ["Land cover", "cropland-share", "2021"]
  ]);
  expect(chosenLayerId(list, "cropland-share")).toBe("cropland-share");
  expect(chosenLayerId(list, "rainfall")).toBeNull();
  expect(chosenLayerId(list, null)).toBeNull();
  expect(chosenLayerId(null, "cropland-share")).toBeNull();
});

test("fewer classes spread across the colour ramp", () => {
  expect([0, 1, 2, 3, 4].map((band) => toneIndex(band, 5, 5))).toEqual([0, 1, 2, 3, 4]);
  expect(toneIndex(0, 1, 5)).toBe(2);
  expect([0, 1].map((band) => toneIndex(band, 2, 5))).toEqual([0, 4]);
  expect([0, 1, 2].map((band) => toneIndex(band, 3, 5))).toEqual([0, 2, 4]);
  expect(() => toneIndex(5, 5, 5)).toThrow(RangeError);
});
