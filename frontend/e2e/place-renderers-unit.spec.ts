import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";
import { motionValue } from "framer-motion";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { BLOCK_RENDERERS } from "@/components/answer/blockRenderers";
import { MapLayerBlockView } from "@/components/answer/place/MapLayerBlockView";
import { RegionStory } from "@/components/answer/place/RegionStory";
import { RiverStage, type StageFocus } from "@/components/answer/place/RiverStage";
import { SeasonsStrip } from "@/components/answer/place/SeasonsStrip";
import { boxesMeet, saltInView, storyGeometry, storyTone, type StoryGeometry } from "@/components/answer/place/storyGeometry";
import { PLACE_KEY, StoryKey } from "@/components/answer/place/StoryKey";
import { StorySteps } from "@/components/answer/place/StorySteps";
import { SupplyMapView } from "@/components/answer/place/SupplyMapView";
import { useRiverFlow, type RiverFlow } from "@/components/answer/place/useRiverFlow";
import { SALT_EXTRA } from "@/components/map/ChoroplethLegend";
import { DISTRICTS_INDICATIVE, SURVEY_OF_INDIA_CAPTION } from "@/components/map/MapAttribution";
import { PLACE_PATTERN } from "@/components/map/MapBase";
import { project } from "@/components/map/projection";
import { decodeShapes, type DistrictShape, type ShapesFile } from "@/components/map/shapeGeometry";
import { ApiError } from "@/lib/api";
import { BLOCK_SHAPES } from "@/lib/explainerContract";
import { HYDRORIVERS_DATASET_CODE, RIVER_BASIN_PATH, RIVER_REACHES_OBJECT, type MapLayerBlock, type RegionStoryBlock, type SeasonsBlock, type SupplyMapBlock } from "@/lib/explainerPlace";
import { blockCitations, blockSentences } from "@/lib/explainerView";
import { isGone } from "@/lib/placeView";
import { BOUNDARY_DATASET_CODE, type RegionDataset } from "@/lib/regionContract";
import { ALL_PASSED, districtEntries, flowThresholds, NOT_YET, passedFraction, playingStep, stepBadges, stretchOf, type Course } from "@/lib/regionStory";
import { cumulativeLengths, framedView, insideRings, joinLines, orientDownstream, pointAlong, type Point } from "@/lib/riverGeometry";
import { riverBasinOf } from "@/lib/riverTopology";
import { annualRain, monthsText, rainfallFinding, rainText, wettestMonth } from "@/lib/seasonsView";
import { parseShape, ShapeError } from "@/lib/shape";
import { supplyLayout } from "@/lib/supplyView";

import { attribute, withApp, withReading } from "./explainerRender";
import { eagerModules } from "./moduleGraph";

const ROOT = join(__dirname, "..", "..");
const read = (...parts: string[]) => readFileSync(join(ROOT, ...parts), "utf8");
const FIXTURE = JSON.parse(read("shared", "explainer.phase-b.golden.json")) as { sections: { blocks: { id: string }[] }[] };
const KACHCHH = 449;
const INDIA_BOX = { minLongitude: 68.206, maxLongitude: 97.394, minLatitude: 6.756, maxLatitude: 37.082 };

function fixtureBlock(id: string): unknown {
  const found = FIXTURE.sections.flatMap((section) => section.blocks).find((block) => block.id === id);
  if (!found) throw new Error(`the phase B fixture has block ${id}`);
  return structuredClone(found);
}

const story = (): RegionStoryBlock => parseShape(BLOCK_SHAPES.region_story, fixtureBlock("s1.b1"));
const placedStory = (): RegionStoryBlock => {
  const block = story();
  return { ...block, steps: block.steps.map((step) => ({ districtLgd: KACHCHH, sentence: { ...step.sentence, text: `In Kachchh, ${step.sentence.text}` } })) };
};
const layerBlock = (): MapLayerBlock => parseShape(BLOCK_SHAPES.map_layer, fixtureBlock("s2.b1"));
const seasons = (): SeasonsBlock => parseShape(BLOCK_SHAPES.seasons, fixtureBlock("s3.b1"));
const supply = (): SupplyMapBlock => parseShape(BLOCK_SHAPES.supply_map, fixtureBlock("s6.b1"));

function topology() {
  return {
    type: "Topology",
    transform: { scale: [0.01, 0.01], translate: [69.5, 23.0] },
    objects: {
      reaches: {
        type: "GeometryCollection",
        geometries: [
          { type: "LineString", id: 1, arcs: [0], properties: { nextDown: 2, ordStra: 2 } },
          { type: "LineString", id: 2, arcs: [1], properties: { nextDown: 3, ordStra: 3 } },
          { type: "LineString", id: 3, arcs: [-3], properties: { nextDown: 0, ordStra: 3 } },
          { type: "LineString", id: 4, arcs: [3], properties: { nextDown: 2, ordStra: 1 } }
        ]
      }
    },
    arcs: [
      [[30, 60], [-5, -10]],
      [[25, 50], [-5, -10]],
      [[10, 20], [10, 20]],
      [[40, 45], [-15, 5]]
    ]
  };
}

let shapesCache: DistrictShape[] | null = null;
function shapes(): DistrictShape[] {
  shapesCache ??= decodeShapes(JSON.parse(read("frontend", "public", "boundaries", "district-shapes.json")) as ShapesFile);
  return shapesCache;
}

function storyGeometryOfFixture(): StoryGeometry {
  const geometry = storyGeometry(placedStory(), shapes(), riverBasinOf(topology(), 3));
  if (!geometry) throw new Error("the fixture story draws");
  return geometry;
}

function still(): RiverFlow {
  return { progress: motionValue(1), moving: false, passed: ALL_PASSED, replay: null };
}

function moving(): RiverFlow {
  return { progress: motionValue(0), moving: true, passed: NOT_YET, replay: null };
}

function focusOf(flow: RiverFlow, geometry: StoryGeometry, district: number | null = null, stretch = false): StageFocus {
  return { district, stretch, reached: geometry.fractions.map((fraction) => fraction <= flow.passed), onStep: () => undefined };
}

function stage(flow: RiverFlow, focus?: StageFocus): string {
  const geometry = storyGeometryOfFixture();
  return renderToStaticMarkup(
    createElement(RiverStage, {
      geometry,
      flow,
      fillOf: (shape: DistrictShape) => storyTone(geometry, shape.lgd, flow.passed),
      focus: focus ?? focusOf(flow, geometry),
      summary: "Saran from its source to its outlet, with Kachchh."
    })
  );
}

function backendScalar(file: string, name: string): string {
  const found = new RegExp(`^${name} = \\(?\\s*"([^"]+)"`, "m").exec(read("backend", "app", ...file.split("/")));
  if (!found) throw new Error(`${name} is not a string in backend/app/${file}`);
  return found[1];
}

test("the basin topology decodes quantized arcs, reversed arcs and joined arcs to the coordinates worked out by hand", () => {
  const basin = riverBasinOf(topology(), 3);
  const line = (id: number) => basin.reaches.get(id)?.line.map(([x, y]) => [Number(x.toFixed(6)), Number(y.toFixed(6))]);
  expect(line(1)).toEqual([[69.8, 23.6], [69.75, 23.5]]);
  expect(line(3)).toEqual([[69.7, 23.4], [69.6, 23.2]]);
  expect(basin.reaches.get(4)).toMatchObject({ nextDown: 2, ordStra: 1 });
  const joined = topology();
  joined.objects.reaches.geometries[0].arcs = [0, 1];
  expect(riverBasinOf(joined, 3).reaches.get(1)?.line.map(([x, y]) => [Number(x.toFixed(6)), Number(y.toFixed(6))])).toEqual([[69.8, 23.6], [69.75, 23.5], [69.7, 23.4]]);
  const { type, objects } = topology();
  const plain = { type, objects, arcs: [[[69.8, 23.6], [69.75, 23.5]], [[69.75, 23.5], [69.7, 23.4]], [[69.6, 23.2], [69.7, 23.4]], [[69.9, 23.45], [69.75, 23.5]]] };
  expect(riverBasinOf(plain, 3).reaches.get(3)?.line).toEqual([[69.7, 23.4], [69.6, 23.2]]);
});

test("a basin off the river contract is refused", () => {
  expect(() => riverBasinOf({ ...topology(), extra: true }, 3)).toThrow(ShapeError);
  expect(() => riverBasinOf(topology(), 2)).toThrow("its outlet reach 2");
  const missingArc = topology();
  missingArc.objects.reaches.geometries[0].arcs = [9];
  expect(() => riverBasinOf(missingArc, 3)).toThrow("arc indexes below 4");
  const offEarth = topology();
  offEarth.transform.translate = [200, 23];
  expect(() => riverBasinOf(offEarth, 3)).toThrow(ShapeError);
  const twice = topology();
  twice.objects.reaches.geometries[1].id = 1;
  expect(() => riverBasinOf(twice, 3)).toThrow("one geometry per reach");
  expect(RIVER_REACHES_OBJECT).toBe(backendScalar("research/rivers.py", "RIVER_REACHES_OBJECT"));
  expect(HYDRORIVERS_DATASET_CODE).toBe(backendScalar("research/rivers.py", "HYDRORIVERS_DATASET_CODE"));
  expect(`/api${RIVER_BASIN_PATH(3)}`).toBe(backendScalar("research/rivers.py", "RIVER_BASIN_ROUTE").replace("{mainRiv}", "3"));
  expect(BOUNDARY_DATASET_CODE).toBe(backendScalar("research/datasets.py", "BOUNDARY_DATASET_CODE"));
});

test("reaches are turned to flow downstream, joined once at each junction and measured along the path", () => {
  const oriented = orientDownstream([[[0, 0], [1, 0]], [[2, 0], [1, 0]], [[2, 0], [3, 0]]]);
  expect(oriented).toEqual([[[0, 0], [1, 0]], [[1, 0], [2, 0]], [[2, 0], [3, 0]]]);
  expect(orientDownstream([[[1, 0], [0, 0]], [[1, 0], [2, 0]]])).toEqual([[[0, 0], [1, 0]], [[1, 0], [2, 0]]]);
  const points = joinLines(oriented);
  expect(points).toEqual([[0, 0], [1, 0], [2, 0], [3, 0]]);
  expect(cumulativeLengths(points)).toEqual([0, 1, 2, 3]);
  expect(cumulativeLengths([[0, 0], [3, 4]])).toEqual([0, 5]);
  expect(pointAlong(points, [0, 1, 2, 3], 0.5)).toEqual([1.5, 0]);
  expect(pointAlong(points, [0, 1, 2, 3], 2)).toEqual([3, 0]);
});

test("a point inside a hole is outside its district, and the view keeps the story's 4:3 frame and minimum span", () => {
  const rings: Point[][] = [
    [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]],
    [[4, 4], [6, 4], [6, 6], [4, 6], [4, 4]]
  ];
  expect([insideRings([2, 2], rings), insideRings([5, 5], rings), insideRings([11, 5], rings)]).toEqual([true, false, false]);
  expect(framedView({ minX: 0, minY: 0, maxX: 40, maxY: 10 }, { aspect: 4 / 3, minSpan: 20, padding: 0.1 })).toEqual({ x: -4, y: -13, width: 48, height: 36 });
  expect(framedView({ minX: 0, minY: 0, maxX: 2, maxY: 1 }, { aspect: 4 / 3, minSpan: 120, padding: 0.1 })).toEqual({ x: -59, y: -44.5, width: 120, height: 90 });
});

test("districts light in the server's path order, each step is reached when the water enters its district, and badges group steps", () => {
  const lines: Point[][] = [[[0, 0], [1, 0]], [[1, 0], [2, 0]], [[2, 0], [3, 0]]];
  const course: Course = { lines, points: [[0, 0], [1, 0], [2, 0], [3, 0]], lengths: [0, 1, 2, 3] };
  const box = (from: number, to: number): Point[][] => [[[from, -1], [to, -1], [to, 1], [from, 1], [from, -1]]];
  const rings = new Map([[1, box(-0.5, 1.5)], [2, box(1.5, 3.5)]]);
  expect([...districtEntries(course, [1, 2, 7], rings)]).toEqual([[1, 0], [2, 2 / 3], [7, 2 / 3]]);
  expect([...districtEntries(course, [2, 1], rings)]).toEqual([[2, 2 / 3], [1, 2 / 3]]);
  expect(stretchOf(course, box(1.5, 3.5))).toEqual([lines[1], lines[2]]);
  expect(flowThresholds(new Map([[1, 0], [2, 0.5]]), [0.5, 1])).toEqual([0, 0.5, 1]);
  expect([passedFraction([0, 0.5, 1], -0.1), passedFraction([0, 0.5, 1], 0.4), passedFraction([0, 0.5, 1], 1)]).toEqual([NOT_YET, 0, 1]);
  expect([playingStep([0, 0.5, 1, 0], 0.6), playingStep([0.5, 0.5], 0.5), playingStep([0, 0.5], 1), playingStep([0, 0.5], NOT_YET)]).toEqual([1, 0, null, null]);
  expect(stepBadges(story().steps)).toEqual([]);
  const steps = placedStory().steps;
  expect(stepBadges(steps)).toEqual([{ districtLgd: KACHCHH, label: "1–4", first: 0 }]);
  const mixed = [steps[0], { ...steps[1], districtLgd: 7 }, steps[2], { ...steps[3], districtLgd: null }];
  expect(stepBadges(mixed)).toEqual([{ districtLgd: KACHCHH, label: "1, 3", first: 0 }, { districtLgd: 7, label: "2", first: 1 }]);
});

test("the Kutch Ajrakh story is drawn from its basin and the real Kachchh polygon, framed 4:3 around them", () => {
  const geometry = storyGeometryOfFixture();
  const source = project(69.8, 23.6);
  expect(geometry.river?.course.points[0][0]).toBeCloseTo(source.x, 6);
  expect(geometry.river?.course.points[0][1]).toBeCloseTo(source.y, 6);
  expect(geometry.river?.course.lines).toHaveLength(3);
  expect(geometry.river?.tributaries.map((line) => line.order)).toEqual([1]);
  expect([...geometry.entries]).toEqual([[KACHCHH, 0]]);
  expect(geometry.fractions).toEqual([0, 0, 0, 0]);
  expect(geometry.thresholds).toEqual([0, 1]);
  expect(geometry.badges.map(({ districtLgd, label }) => [districtLgd, label])).toEqual([[KACHCHH, "1–4"]]);
  expect(geometry.view.width / geometry.view.height).toBeCloseTo(4 / 3, 9);
  expect(geometry.context.some((shape) => shape.lgd === KACHCHH)).toBe(true);
  expect(geometry.river?.stretches.get(KACHCHH)).toMatch(/^M/);
});

test("the story rests complete, with the full river, every reached district and every step; the flow plays only when asked", () => {
  function Probe({ reduce, drawn = true }: { reduce: boolean; drawn?: boolean }) {
    const flow = useRiverFlow([0, 1], { expected: true, drawn }, reduce);
    return createElement("span", { "data-moving": String(flow.moving), "data-passed": flow.passed, "data-replay": String(flow.replay !== null) });
  }
  expect(renderToStaticMarkup(createElement(Probe, { reduce: true }))).toContain('data-moving="false" data-passed="1" data-replay="false"');
  expect(renderToStaticMarkup(createElement(Probe, { reduce: false }))).toContain('data-moving="false" data-passed="1" data-replay="true"');
  expect(renderToStaticMarkup(createElement(Probe, { reduce: false, drawn: false }))).toContain('data-moving="false" data-passed="1" data-replay="false"');

  const full = stage(still());
  expect(attribute(full, "river-course", "data-flow")).toEqual(["still"]);
  const course = /<path[^>]*data-testid="river-course"[^>]*>/.exec(full)?.[0] ?? "";
  expect(course).not.toContain("stroke-dasharray");
  expect(/<path[^>]*data-lgd="449"[^>]*>/.exec(full)?.[0]).toContain(`url(#${PLACE_PATTERN})`);
  expect(attribute(full, "story-badge", "data-reached")).toEqual(["true"]);
  expect(full).toContain(">Source<");
  expect(full).toContain(">Outlet<");

  const flowing = stage(moving());
  expect(attribute(flowing, "river-course", "data-flow")).toEqual(["moving"]);
  expect(/<path[^>]*data-testid="river-course"[^>]*>/.exec(flowing)?.[0]).toContain('stroke-dasharray="0 1"');
  expect(/<path[^>]*data-lgd="449"[^>]*>/.exec(flowing)?.[0]).not.toContain(`url(#${PLACE_PATTERN})`);
  expect(/<path[^>]*data-lgd="449"[^>]*>/.exec(flowing)?.[0]).toContain("stroke-terracotta");
  expect(attribute(flowing, "story-badge", "data-reached")).toEqual(["false"]);

  const geometry = storyGeometryOfFixture();
  const steps = withReading(createElement(StorySteps, { block: placedStory(), focus: focusOf(still(), geometry), step: null }));
  expect(attribute(steps, "story-step", "data-reached")).toEqual(["true", "true", "true", "true"]);
  expect(steps).toContain("Kachchh · Gujarat");
  for (const step of placedStory().steps) expect(steps).toContain(step.sentence.text);
});

test("a step the server could not place in a district its sentence names is numbered, with no district and no badge", () => {
  const unplaced = storyGeometry(story(), shapes(), riverBasinOf(topology(), 3));
  expect(unplaced?.badges).toEqual([]);
  const html = withReading(createElement(StorySteps, { block: story(), focus: { district: null, stretch: false, reached: [true, true, true, true], onStep: () => undefined }, step: null }));
  expect(html.replace(/<[^>]+>/g, " ")).toMatch(/Step 1[\s\S]*Step 2[\s\S]*Step 3[\s\S]*Step 4/);
  expect(html).not.toContain("Kachchh · Gujarat");
  expect(html).not.toContain("aria-pressed");
});

test("a chosen step outlines its district and draws its stretch of the river", () => {
  const geometry = storyGeometryOfFixture();
  const chosen = stage(still(), focusOf(still(), geometry, KACHCHH, true));
  expect(chosen).toContain('data-testid="river-stretch"');
  expect(chosen).toContain('data-testid="district-outlines"');
  expect(stage(still())).not.toContain('data-testid="river-stretch"');
});

test("every map carries the boundary caption word for word, and the client's caption is the server's", () => {
  const caption = backendScalar("research/datasets.py", "BOUNDARY_CAPTION").trim();
  expect(`${SURVEY_OF_INDIA_CAPTION} ${DISTRICTS_INDICATIVE}`).toBe(caption);
  expect(story().boundaryCaption).toBe(caption);
  const storyHtml = withApp(createElement(RegionStory, { block: story() }));
  expect(storyHtml).toContain(caption);
  expect(storyHtml).toContain('data-testid="map-placeholder"');
  expect(attribute(storyHtml, "story-step", "data-testid")).toHaveLength(4);
  const layerHtml = withApp(createElement(MapLayerBlockView, { block: layerBlock() }));
  expect(layerHtml).toContain(caption);
  expect(layerHtml).toContain('data-layer="soil-ph-0-5cm"');
});

test("a map layer the server no longer serves is not drawn; other failures offer a retry", () => {
  expect(isGone({ cause: new ApiError(404, "Not Found", null) })).toBe(true);
  expect(isGone({ cause: new ApiError(503, "Unavailable", null) })).toBe(false);
  expect(isGone({ cause: new Error("network") })).toBe(false);
  expect(isGone(null)).toBe(false);
});

const CHIRPS: RegionDataset = {
  code: "CHIRPS_3_0",
  title: "Climate Hazards Center InfraRed Precipitation with Stations v3.0",
  publisher: "Climate Hazards Center, UC Santa Barbara",
  edition: "3.0",
  period: "1991-2020",
  nativeResolution: "0.05 degree",
  licence: "CC BY 4.0",
  licenceUrl: "https://creativecommons.org/licenses/by/4.0/",
  attribution: "Climate Hazards Center, UC Santa Barbara (CHIRPS3)",
  citation: null,
  url: "https://data.chc.ucsb.edu/products/CHIRPS/v3.0/"
};

test("a seasons block without rainfall shows its season rows and no month strip", () => {
  const html = withReading(createElement(SeasonsStrip, { block: seasons() }));
  expect(html).not.toContain('data-testid="rainfall-bars"');
  expect(html).not.toContain('data-testid="month-header"');
  expect(html).not.toContain('data-testid="dataset-credit"');
  expect(html.match(/data-testid="season-chip"[^>]*>Monsoon</g)).toHaveLength(1);
  for (const row of seasons().rows) expect(html).toContain(row.sentence.text);
});

test("rainfall draws twelve months with the wettest month read out, and a month row fills its own months", () => {
  const block = seasons();
  const millimetres = [1, 0, 0.5, 0, 2, 40, 120, 80, 30, 5, 1, 0];
  const rainy = parseShape(BLOCK_SHAPES.seasons, {
    ...block,
    rows: [{ ...block.rows[0], months: [6, 7, 8, 9], season: null }, { ...block.rows[0], sentence: { ...block.rows[0].sentence, id: "s3.b1.2" } }],
    rainfall: { district: { districtLgd: KACHCHH, name: "Kachchh", stateName: "Gujarat" }, datasetCode: CHIRPS.code, period: "1991-2020", millimetres },
    datasets: [CHIRPS]
  });
  expect(wettestMonth(rainy.rainfall!)).toBe(7);
  expect([rainText(120), rainText(0.5), rainText(312.46)]).toEqual(["120 mm", "0.5 mm", "312 mm"]);
  expect([monthsText([6, 7, 8, 9]), monthsText([1, 3, 4]), monthsText([])]).toEqual(["June–September", "January, March–April", ""]);
  const html = withReading(createElement(SeasonsStrip, { block: rainy }));
  expect(html).toContain('data-testid="month-header"');
  expect(attribute(html, "rainfall-reading", "data-testid")).toHaveLength(1);
  expect(html.replace(/<[^>]+>/g, "")).toContain("Wettest · July · 120 mm");
  const heights = [...html.matchAll(/data-month="(\d+)"[^>]*><span[^>]*style="height:([\d.]+)%"/g)].map((found) => [Number(found[1]), Number(found[2])]);
  expect(heights).toHaveLength(12);
  expect(heights[6]).toEqual([7, 100]);
  expect(heights[7]).toEqual([8, 66.67]);
  const cells = [...html.matchAll(/data-on="(true|false)"/g)].map((found) => found[1] === "true");
  expect(cells.map((on, index) => (on ? index + 1 : 0)).filter(Boolean)).toEqual([6, 7, 8, 9]);
  expect(html).toContain("June–September");
  expect(html.replace(/<[^>]+>/g, "")).toContain("Rainfall · Kachchh, Gujarat · monthly normal · 1991-2020");
  expect(annualRain(rainy.rainfall!)).toBeCloseTo(1 + 0.5 + 2 + 40 + 120 + 80 + 30 + 5 + 1, 9);
  expect(rainfallFinding(rainy.rainfall!)).toBe("July is the wettest month in Kachchh: 120 mm of a 280 mm year");
  expect(html).toContain(">July is the wettest month in Kachchh: 120 mm of a 280 mm year<");
  expect(html).toContain(">All 12 values<");
  expect(html).toContain(CHIRPS.title);
});

test("supply groups origins by material, states a shared sentence once and pins only placed origins inside the map", () => {
  const block = supply();
  const { groups } = supplyLayout(block, INDIA_BOX);
  expect(groups.map((group) => [group.heading, group.origins.map((origin) => origin.origin), group.sentences.length])).toEqual([
    ["Indigo", ["Shikarpur", "Dhamadka"], 1],
    ["Blocks", ["Pethapur"], 1]
  ]);
  const unplaced = withReading(createElement(SupplyMapView, { block }));
  expect(unplaced).not.toContain('data-testid="map-placeholder"');
  expect(unplaced).not.toContain('data-testid="supply-pin"');
  expect(unplaced.match(/Indigo came from Shikarpur in Sindh and was also grown in Dhamadka\./g)).toHaveLength(1);

  const placed = parseShape(BLOCK_SHAPES.supply_map, {
    ...block,
    links: [
      { ...block.links[0], wikidataId: "Q1", latitude: 27.95, longitude: 50.1 },
      { ...block.links[1], wikidataId: "Q2", latitude: 23.4, longitude: 70.0 },
      block.links[2]
    ]
  });
  const pins = supplyLayout(placed, INDIA_BOX).groups.flatMap((group) => group.origins.map((origin) => [origin.origin, origin.pin]));
  expect(pins).toEqual([["Shikarpur", null], ["Dhamadka", 1], ["Pethapur", null]]);
  const html = withReading(createElement(SupplyMapView, { block: placed }));
  expect(html).toContain('data-testid="map-placeholder"');
  expect(html).toContain('href="https://www.wikidata.org/wiki/Q1"');
  expect(html).toContain('href="https://www.wikidata.org/wiki/Q2"');
  expect(attribute(html, "supply-pin", "data-testid")).toHaveLength(1);
});

test("the place renderers are registered and their sentences are numbered and translated like any block", () => {
  for (const kind of ["region_story", "map_layer", "seasons", "supply_map"] as const) expect(BLOCK_RENDERERS[kind]).toBeDefined();
  const lazy = renderToStaticMarkup(createElement(BLOCK_RENDERERS.region_story!, { block: story() }));
  expect(lazy).toContain('data-testid="map-placeholder"');
  expect(blockSentences(story()).map((sentence) => sentence.id)).toEqual(["s1.b1.1", "s1.b1.2", "s1.b1.3", "s1.b1.4"]);
  expect(blockSentences(seasons())).toHaveLength(1);
  expect(blockSentences(supply())).toHaveLength(3);
  expect(blockSentences(layerBlock())).toEqual([]);
  expect(blockCitations(story()).map((citation) => citation.claimId)).toContain("47766797-6f8a-5369-bf51-6122e1c52329");
});

test("map code is loaded only when a map is drawn, so the asking screen stays light", () => {
  const eager = eagerModules("@/components/answer/blockRenderers");
  expect(eager.has("components/answer/place/SeasonsStrip.tsx")).toBe(true);
  for (const heavy of ["components/map/indiaGeometry.ts", "components/map/projection.ts", "components/map/shapeGeometry.ts", "components/map/IndiaMap.tsx", "components/answer/place/RegionStory.tsx", "components/answer/place/MapLayerBlockView.tsx", "components/answer/place/SupplyPins.tsx"]) {
    expect(eager.has(heavy), heavy).toBe(false);
  }
});

test("place renderers lay out in shrinkable columns so nothing widens a phone page", () => {
  const geometry = storyGeometryOfFixture();
  const html = [
    withApp(createElement(RegionStory, { block: story() })),
    withReading(createElement(SupplyMapView, { block: supply() })),
    withReading(createElement(StorySteps, { block: story(), focus: focusOf(still(), geometry), step: 0 })),
    withReading(createElement(SeasonsStrip, { block: seasons() }))
  ].join("");
  const templates = [...html.matchAll(/grid-cols-\[([^\]]+)\]/g)].map((found) => found[1]);
  expect(templates.length).toBeGreaterThan(0);
  for (const template of templates) {
    for (const track of template.split("_")) expect(track, template).toMatch(/^(minmax\(0,|repeat\(\d+,minmax\(0,)/);
  }
  expect(html).not.toMatch(/\b(min-)?w-\[\d{3,}px\]/);
});

test("the story key explains the salt stipple only where the Rann is in the frame, beside the place hatch", () => {
  const kachchh = storyGeometryOfFixture();
  expect(saltInView(kachchh.view)).toBe(true);
  const kolkata = project(88.36, 22.57);
  expect(saltInView({ x: kolkata.x - 20, y: kolkata.y - 15, width: 40, height: 30 })).toBe(false);
  expect(boxesMeet({ x: 0, y: 0, width: 2, height: 2 }, { x: 1, y: 1, width: 2, height: 2 })).toBe(true);
  expect(boxesMeet({ x: 0, y: 0, width: 1, height: 1 }, { x: 2, y: 2, width: 1, height: 1 })).toBe(false);
  const key = renderToStaticMarkup(createElement(StoryKey, { block: placedStory(), geometry: kachchh, layered: false }));
  expect(key).toContain(SALT_EXTRA.label);
  expect(key).toContain(PLACE_KEY);
  const layered = renderToStaticMarkup(createElement(StoryKey, { block: placedStory(), geometry: kachchh, layered: true }));
  expect(layered).not.toContain(PLACE_KEY);
});
