import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { pickerOptions } from "@/components/map/LayerPicker";
import { MineralSymbols, symbolPath } from "@/components/map/physical/MineralsLayer";
import { reliefSteps } from "@/components/map/physical/PhysicalSide";
import { ReliefUnder } from "@/components/map/physical/ReliefLayer";
import { RiversOver, RiversUnder } from "@/components/map/physical/RiversLayer";
import { PALETTE_FILLS, paletteFill } from "@/components/map/rampFills";
import { classIndexOf, districtSteps, LAYER_PALETTES, layerPalette, PALETTE_STEPS, paletteClasses, paletteSeries, spreadStep, type PaletteName } from "@/lib/mapPalettes";
import { mineralFinding, mineralSites, physicalLayerId, PHYSICAL_GROUP, PHYSICAL_LAYERS, riverWidth, tally, type MineralsFile, type ReliefFile, type RiversFile } from "@/lib/mapPhysical";
import type { MapLayer, MapLayerList, MapLayerSummary } from "@/lib/regionContract";

import { FRONTEND } from "./moduleGraph";

const read = <T>(name: string) => JSON.parse(readFileSync(join(FRONTEND, "public", "layers", name), "utf8")) as T;
const TOKENS = readFileSync(join(FRONTEND, "app", "tokens.css"), "utf8");
const BACKEND_LAYERS = readFileSync(join(FRONTEND, "..", "backend", "app", "geo", "layers.py"), "utf8");
const RELIEF = read<ReliefFile>("relief.json");
const RIVERS = read<RiversFile>("rivers.json");
const MINERALS = read<MineralsFile>("minerals.json");

function summary(id: string, variable: string, unit = "%"): MapLayerSummary {
  return { id, facet: "SOIL", title: id, datasetCode: "X", variable, depth: null, period: "2020", stat: "DISTRICT_MEAN", unit };
}

function layer(id: string, variable: string, values: Record<string, number>, unit = "%"): MapLayer {
  const dataset = { code: "X", title: "X", publisher: null, edition: "1", period: "2020", nativeResolution: "1 km", licence: "CC BY 4.0", licenceUrl: null, attribution: null, citation: null, url: null };
  return { layer: summary(id, variable, unit), dataset, resolution: "1 km", classes: [{ min: 0, max: 10 }, { min: 10, max: 20 }, { min: 20, max: 30 }], values, version: "0".repeat(64), boundary: { caption: "", dataset } };
}

test("every layer the backend serves has a palette, and each kind of data takes its own ramp", () => {
  const ids = [...BACKEND_LAYERS.matchAll(/(?:_soil|_cover|_chelsa|_trend_normal)\("([a-z0-9-]+)"|LayerSpec\(\s*"([a-z0-9-]+)"/g)].map((found) => found[1] ?? found[2]);
  expect(ids.length).toBeGreaterThanOrEqual(20);
  for (const id of ids) expect(Object.keys(LAYER_PALETTES), id).toContain(id);
  const ramps = (names: string[]) => names.map((id) => LAYER_PALETTES[id].ramp);
  expect(ramps(["annual-precipitation", "monsoon-share", "river-density", "distance-to-major-river"])).toEqual(["rain", "rain", "rain", "rain"]);
  expect(ramps(["annual-mean-temperature", "warmest-month-maximum", "coldest-month-minimum"])).toEqual(["heat", "heat", "heat"]);
  expect(ramps(["tree-cover-2000", "tree-cover-share", "cropland-share"])).toEqual(["cover", "cover", "cover"]);
  expect(ramps(["soil-organic-carbon-0-5cm", "clay-0-5cm", "sand-0-5cm", "cation-exchange-0-5cm", "bare-ground-share"])).toEqual(["earth", "earth", "earth", "earth", "earth"]);
  expect(LAYER_PALETTES["soil-ph-0-5cm"]).toMatchObject({ ramp: "ph", kind: "diverging" });
  expect(LAYER_PALETTES.elevation).toMatchObject({ ramp: "elevation", kind: "hypsometric" });
  expect(LAYER_PALETTES["distance-to-major-river"].reversed).toBe(true);
  expect(ids.filter((id) => LAYER_PALETTES[id].ramp === "density").sort()).toEqual(["built-up-share", "mineral-sites", "slope"]);
  expect(layerPalette(summary("new-rain", "seasonal_precipitation")).ramp).toBe("rain");
  expect(layerPalette(summary("new", "unknown")).ramp).toBe("density");
  expect([paletteSeries(LAYER_PALETTES["annual-precipitation"]), paletteSeries(LAYER_PALETTES["clay-0-5cm"])]).toEqual(["var(--series-rain)", "var(--chart-series)"]);
});

test("every palette step is a token in every theme, and its fill class names that token", () => {
  for (const [ramp, steps] of Object.entries(PALETTE_STEPS) as [PaletteName, number][]) {
    expect(PALETTE_FILLS[ramp], ramp).toHaveLength(steps);
    for (let step = 1; step <= steps; step += 1) {
      expect(TOKENS.match(new RegExp(`--${ramp}-${step}: #[0-9A-F]{6};`, "g"))?.length ?? 0, `${ramp}-${step}`).toBeGreaterThanOrEqual(4);
      expect(paletteFill(ramp, step)).toBe(`fill-[var(--${ramp}-${step})]`);
    }
  }
  for (const step of [1, 2, 3, 4, 5, 6]) expect(TOKENS).toContain(`--mineral-${step}: #`);
  expect(TOKENS).toContain("--map-relief-shade: #");
  expect(paletteFill("earth", 9)).toBe("fill-[var(--earth-6)]");
});

test("soil pH keeps the agronomic classes with 6.5 to 7.5 in the middle, whatever the data", () => {
  const ph = layer("soil-ph-0-5cm", "phh2o", { "1": 5.2, "2": 6.9, "3": 7.5, "4": 9.1 }, "pH");
  const classes = paletteClasses(ph);
  expect(classes.map((band) => [band.min, band.max, band.step])).toEqual([
    [null, 5.5, 1],
    [5.5, 6.5, 2],
    [6.5, 7.5, 3],
    [7.5, 8.5, 4],
    [8.5, null, 5]
  ]);
  expect([...districtSteps(ph).steps.entries()]).toEqual([
    [1, 1],
    [2, 3],
    [3, 4],
    [4, 5]
  ]);
  const elevation = paletteClasses(layer("elevation", "elevation", { "1": 50 }, "m"));
  expect(elevation).toHaveLength(7);
  expect(classIndexOf(elevation, 4500)).toBe(6);
  expect(classIndexOf(elevation, 100)).toBe(1);
});

test("a quantile layer spreads its classes over the ramp, and a reversed one runs the other way", () => {
  expect([spreadStep(0, 3, 6), spreadStep(1, 3, 6), spreadStep(2, 3, 6), spreadStep(0, 1, 6)]).toEqual([1, 4, 6, 3]);
  const clay = paletteClasses(layer("clay-0-5cm", "clay", { "1": 5 }));
  expect(clay.map((band) => band.step)).toEqual([1, 4, 6]);
  const distance = paletteClasses(layer("distance-to-major-river", "distance_centroid_to_major_river", { "1": 5 }, "km"));
  expect(distance.map((band) => band.step)).toEqual([6, 3, 1]);
  expect(classIndexOf(clay, 30)).toBe(2);
});

test("the layer picker offers the land and water layers first, before the district layers", () => {
  expect(PHYSICAL_LAYERS.map((entry) => entry.id)).toEqual(["relief", "rivers", "minerals"]);
  expect([physicalLayerId("rivers"), physicalLayerId("clay-0-5cm"), physicalLayerId(null)]).toEqual(["rivers", null, null]);
  const list: MapLayerList = { layers: [summary("clay-0-5cm", "clay")], datasets: [], boundary: { caption: "", dataset: layer("x", "x", {}).dataset }, outlineCaption: "" };
  const options = pickerOptions(list);
  expect(options.map((option) => option.value)).toEqual(["relief", "rivers", "minerals", "clay-0-5cm"]);
  expect(options.slice(0, 3).every((option) => option.group === PHYSICAL_GROUP)).toBe(true);
  expect(pickerOptions(null)).toHaveLength(3);
});

test("the relief layer draws six bands over the land, the shaded relief through a mask, and a legend of seven bands", () => {
  const markup = renderToStaticMarkup(createElement(ReliefUnder, { file: RELIEF }));
  expect(markup.match(/data-band="/g)).toHaveLength(6);
  expect(markup).toContain('fill="var(--elevation-1)"');
  expect(markup).toContain('fill="var(--elevation-7)"');
  expect(markup).toContain(`href="${RELIEF.shade.href}"`);
  expect(markup).toContain('fill="var(--map-relief-shade)"');
  expect(reliefSteps(RELIEF).map((step) => step.colour)).toEqual([1, 2, 3, 4, 5, 6, 7].map((step) => `var(--elevation-${step})`));
  const names = RELIEF.ranges.map((range) => range.text);
  for (const name of ["Himalaya", "Karakoram", "Western Ghats", "Eastern Ghats", "Vindhya Range", "Satpura Range", "Aravalli Range", "Deccan Plateau"]) expect(names).toContain(name);
  expect(RELIEF.peaks[0].elevation).toBe(Math.max(...RELIEF.peaks.map((peak) => peak.elevation)));
});

test("rivers are drawn heavier as they grow, with lakes in the water fill and the major rivers named in italic", () => {
  const ranks = RIVERS.ranks.map((group) => group.rank).sort((a, b) => a - b);
  const widths = ranks.map(riverWidth);
  expect(widths).toEqual([...widths].sort((a, b) => b - a));
  const under = renderToStaticMarkup(createElement(RiversUnder, { file: RIVERS }));
  expect(under.match(/data-rank="/g)).toHaveLength(RIVERS.ranks.length);
  expect(under).toContain('fill="var(--map-water)"');
  const over = renderToStaticMarkup(createElement(RiversOver, { file: RIVERS }));
  for (const name of ["Ganga", "Brahmaputra", "Indus", "Godavari", "Krishna", "Narmada", "Kaveri", "Mahanadi"]) expect(over).toContain(`>${name}</text>`);
  expect(over).toContain("font-reading italic");
});

test("mineral deposits keep one class and one shape each, and the finding is counted from the sites", () => {
  const sites = mineralSites(MINERALS);
  expect(sites).toHaveLength(MINERALS.sites.length);
  expect(MINERALS.classes).toHaveLength(6);
  const byState = new Map<string, number>();
  for (const row of MINERALS.sites) if (row[2]) byState.set(row[2], (byState.get(row[2]) ?? 0) + 1);
  const [topState, topCount] = [...byState.entries()].sort((a, b) => b[1] - a[1])[0];
  expect(tally(sites.map((site) => site.state))[0]).toEqual({ key: topState, label: topState, count: topCount });
  expect(mineralFinding(sites, MINERALS.classes)).toContain(`${topState} holds ${topCount} of the ${sites.length} recorded deposits`);
  expect(new Set([0, 1, 2, 3, 4, 5].map((index) => symbolPath(index, 0, 0, 1))).size).toBe(6);
  const markup = renderToStaticMarkup(createElement("svg", null, createElement(MineralSymbols, { sites, scale: 1 })));
  expect(markup.match(/data-class="/g)).toHaveLength(sites.length);
  expect(markup).toContain('fill="var(--mineral-1)"');
  expect(MINERALS.source.licence).toContain("Public domain");
  expect(new Set(sites.map((site) => site.status))).toEqual(new Set(MINERALS.statuses.map((status) => `${status[0]}${status.slice(1).toLowerCase()}`)));
});
