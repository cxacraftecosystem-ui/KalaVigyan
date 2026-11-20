import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { BOARD_FRAME, BOARD_INDIA_BOX, boardBox } from "@/components/map/boardGeometry";
import { MapCanvas } from "@/components/map/MapCanvas";
import { MAP_PLACE, MapStatesFigure, SIDE_PLACE } from "@/components/map/MapStatesFigure";
import { KachchhPin, placedCircles, StateCircles } from "@/components/map/StateCircles";
import { MapLegend, NO_READING_EXTRA } from "@/components/map/ChoroplethLegend";
import { CircleKey, circleKeyBox } from "@/components/map/CirclesLegend";
import { VIEW_BOX } from "@/components/map/projection";
import { rampFill } from "@/components/map/rampFills";
import { RankedList } from "@/components/map/RankedList";
import { parseCraftCatalogue } from "@/lib/craftCatalogueContract";
import { markerFamilies, placeMarkers } from "@/lib/mapFamilies";
import { classColour, layerRamp, NO_READING_LABEL, rampStep } from "@/lib/mapRamps";
import { allStatesLabel, circleKeys, circleRadius, mapDescription, niceValue, placeLabels, rankDek, rankFinding, stateMarks } from "@/lib/mapStates";
import { mapLayerShape } from "@/lib/regionContract";
import { parseShape } from "@/lib/shape";
import type { CraftMapPoint } from "@/lib/types";

const SHARED = join(__dirname, "..", "..", "shared");
const golden = (name: string): unknown => JSON.parse(readFileSync(join(SHARED, name), "utf8"));

const state = (name: string, count: number) => ({ name, count });
const point = (key: string, name: string, slugs: string[]): CraftMapPoint => ({
  key,
  name,
  latitude: 23,
  longitude: 70,
  total: slugs.length,
  crafts: slugs.map((slug) => ({ slug, name: slug, path: `/crafts/${slug}` }))
});

test("the map's finding names the leader and how far ahead it is", () => {
  expect(rankFinding([state("Uttar Pradesh", 64), state("Gujarat", 37), state("Rajasthan", 37), state("Tamil Nadu", 27)])).toBe(
    "Uttar Pradesh practises the most crafts, 64, nearly twice as many as Gujarat or Rajasthan."
  );
  expect(rankFinding([state("A", 10), state("B", 8), state("C", 8)])).toBe("A practises the most crafts, 10; B and C follow with 8 each.");
  expect(rankFinding([state("A", 10), state("B", 4)])).toBe("A practises the most crafts, 10, more than twice as many as B.");
  expect(rankFinding([state("A", 8), state("B", 4)])).toBe("A practises the most crafts, 8, twice as many as B.");
  expect(rankFinding([state("A", 5), state("B", 5), state("C", 2)])).toBe("A and B practise the most crafts, 5 each.");
  expect(rankFinding([state("Rajasthan", 3), state("Chhattisgarh", 1), state("Gujarat", 1), state("Haryana", 1), state("Punjab", 1)])).toBe(
    "Rajasthan practises the most crafts, 3, more than twice as many as any other state."
  );
  expect(rankFinding([])).toBeNull();
});

test("the dek says how crafts of several states and of all India are counted", () => {
  expect(rankDek(81)).toBe("Circles are drawn to scale. A craft practised in several states counts in each, and 81 more belong to all of India.");
  expect(rankDek(1)).toBe("Circles are drawn to scale. A craft practised in several states counts in each, and 1 more belongs to all of India.");
  expect(rankDek(0)).toBe("Circles are drawn to scale. A craft practised in several states counts in each.");
  expect(allStatesLabel(33)).toBe("All 33 states and union territories");
  expect(mapDescription([state("A", 3)], false)).toBe("One circle per state, its area drawn to scale by the number of crafts practised there. The most: A 3. The Great and Little Rann of Kachchh are salt flat.");
});

test("circles are drawn by area, and the key takes round values below the largest", () => {
  expect(circleRadius(16, 64, 40)).toBe(20);
  expect(circleRadius(0, 64, 40)).toBe(0);
  expect([niceValue(10.67), niceValue(32), niceValue(64), niceValue(0.4), niceValue(100)]).toEqual([10, 30, 60, 1, 100]);
  expect(circleKeys(64)).toEqual([10, 30, 60]);
  expect(circleKeys(3)).toEqual([1, 3]);
  expect(circleKeys(0)).toEqual([]);
});

test("below 640px the map keeps its circles and the place pin but drops the state labels and the Rann's name, as the board does", () => {
  const scene = { frame: boardBox(BOARD_FRAME), scale: 1 };
  const circles = placedCircles([{ name: "Madhya Pradesh", count: 19, longitude: 78.6, latitude: 23.5 }]);
  const states = renderToStaticMarkup(createElement("svg", null, createElement(StateCircles, { circles, emphKey: null, scene })));
  expect(states).toContain('<g class="max-sm:hidden" data-testid="state-labels">');
  expect(states).toMatch(/data-testid="state-labels">.*Madhya Pradesh/);
  expect(states.match(/<circle/g)).toHaveLength(1);
  const pin = renderToStaticMarkup(createElement("svg", null, createElement(KachchhPin, { lines: ["Kachchh, home of", "Kutch Ajrakh"], scene })));
  expect(pin).not.toContain("max-sm:hidden");
  const canvas = renderToStaticMarkup(createElement(MapCanvas, { title: "Map", description: "India" }));
  expect(canvas).toMatch(/<g class="max-sm:hidden"><text[^>]*>Great Rann<\/text><\/g>/);
});

test("from 1024px the map page's caption, ranked list and legend stand beside the map, as the board's landing map does", () => {
  const counts = { states: [state("Uttar Pradesh", 64), state("Gujarat", 37)], allIndia: 46 };
  const rows = counts.states.map((entry) => ({ key: entry.name, name: entry.name, value: entry.count }));
  const ranking = { catalogue: null, points: { data: [], failure: null, retry: () => undefined }, counts, circles: [], rows, catalogueError: null, reloadCatalogue: () => undefined };
  const html = renderToStaticMarkup(createElement(MapStatesFigure, { ranking, boundary: null }));
  expect(html).toMatch(/<figure id="map-figure" class="kv-figure lg:grid lg:grid-cols-\[minmax\(0,6.6fr\)_minmax\(0,4.4fr\)\]/);
  expect(html).toContain("lg:[&amp;&gt;figcaption]:col-start-2");
  expect(html).toContain("lg:[&amp;&gt;div]:contents");
  expect(html.indexOf("<figcaption")).toBeLessThan(html.indexOf('data-testid="map-states-plot"'));
  expect(html.indexOf('data-testid="map-states-plot"')).toBeLessThan(html.indexOf('data-testid="map-states-side"'));
  expect(html).toMatch(/data-testid="map-states-side"><p[^>]*>Circles are drawn to scale/);
  expect(SIDE_PLACE).toContain("lg:row-start-2");
  expect(MAP_PLACE).toContain("lg:row-span-2");
});

test("the circle key leaves room above its largest circle for that circle's 12px label", () => {
  const [, minY, width, height] = circleKeyBox().split(" ").map(Number);
  const largestLabelBaseline = 1.5 + 4;
  expect(minY).toBeLessThanOrEqual(largestLabelBaseline - 12);
  expect(width).toBe(85);
  expect(minY + height).toBeGreaterThanOrEqual(25.6 * 2 + 1.5);
  const markup = renderToStaticMarkup(createElement(CircleKey, { largest: 64 }));
  expect(markup).toContain(`viewBox="${circleKeyBox()}"`);
  expect(markup).toContain(">60</text>");
});

test("state circles sit on the state points the API serves, matched by name", () => {
  const points = [point("state-24", "Gujarat", ["a"]), point("district-449", "Kachchh", ["a"]), point("state-1", "Jammu & Kashmir", ["b"])];
  const marks = stateMarks([state("Gujarat", 1), state("Jammu and Kashmir", 2), state("Goa", 4)], points);
  expect(marks.map((mark) => mark.name)).toEqual(["Gujarat", "Jammu and Kashmir"]);
});

test("labels take the first free side of their circle and drop when every side is taken", () => {
  const ask = (key: string) => ({ key, x: 100, y: 100, r: 10, width: 50, height: 10 });
  const spots = placeLabels([ask("a"), ask("b"), ask("c"), ask("d")], { x: 0, y: 0, width: 400, height: 400 });
  expect(spots.map((spot) => [spot.key, spot.anchor, spot.x])).toEqual([
    ["a", "start", 113],
    ["b", "end", 87],
    ["c", "middle", 100]
  ]);
});

test("a layer takes its variable's ramp, lowest class first, and no reading is the cross-hatch", () => {
  expect(layerRamp({ variable: "annual_mean_temperature" })).toBe("heat");
  expect(layerRamp({ variable: "annual_precipitation" })).toBe("rain");
  expect(layerRamp({ variable: "phh2o" })).toBe("density");
  expect([rampStep(0, 5), rampStep(2, 5), rampStep(4, 5), rampStep(0, 1)]).toEqual([1, 4, 6, 3]);
  const soil = parseShape(mapLayerShape, golden("region.layer.golden.json"));
  expect(classColour(soil, 0)).toBe("var(--density-1)");
  expect(rampFill("rain", 6)).toBe("fill-[var(--rain-6)]");
  expect(NO_READING_EXTRA.label).toBe(NO_READING_LABEL);
  expect(NO_READING_EXTRA.fill).toBe("url(#kv-map-nodata)");
});

test("craft places are paper discs, coloured by family only where one family holds the place", () => {
  const catalogue = parseCraftCatalogue(golden("craft.catalogue.golden.json"));
  const markers = placeMarkers([point("district-449", "Kachchh", ["Kutch-Ajrakh"]), point("district-9", "Bastar", ["Bastar-Dhokra", "Kutch-Ajrakh"]), point("state-24", "Gujarat", ["Kutch-Ajrakh"])], catalogue);
  expect(markers.map((marker) => [marker.key, marker.family?.token ?? null, marker.href])).toEqual([
    ["district-449", "textiles", "/crafts/Kutch-Ajrakh"],
    ["district-9", null, "/crafts?q=Bastar"]
  ]);
  expect(markerFamilies(markers).map((family) => family.colour)).toEqual(["var(--fam-textiles)"]);
});

test("the Natural Earth layer is laid on India's own frame", () => {
  const india = boardBox(BOARD_INDIA_BOX);
  expect(india.x).toBeCloseTo(24, 6);
  expect(india.y).toBeCloseTo(24, 6);
  expect(india.width).toBeCloseTo(VIEW_BOX.width - 48, 6);
  expect(india.height).toBeCloseTo(VIEW_BOX.height - 48, 6);
});

test("the ranked list shows ten rows, the leader in the emphasis ink, and offers the rest in place", () => {
  const rows = Array.from({ length: 12 }, (_, at) => ({ key: `s${at}`, name: `State ${at}`, value: 12 - at }));
  const html = renderToStaticMarkup(createElement(RankedList, { rows, label: "Crafts", emphKey: "s0", all: { label: "Show all 12" } }));
  expect(html.match(/data-testid="ranked-row"/g)).toHaveLength(10);
  expect(html).toContain('data-emph="true"');
  expect(html).toContain("var(--chart-emph)");
  expect(html).toContain('aria-expanded="false"');
  expect(html).toContain("Show all 12");
  const legend = renderToStaticMarkup(createElement(MapLegend, { title: "Soil pH", steps: [{ label: "pH 6.4–7.1", colour: "var(--density-1)" }], extras: [NO_READING_EXTRA] }));
  expect(legend).toContain(NO_READING_LABEL);
  expect(legend).not.toContain("No data");
});
