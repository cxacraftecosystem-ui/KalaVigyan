import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { creditedDatasets, GroundCredits } from "@/components/map/place-context/GroundCredits";
import { GroundFigure } from "@/components/map/place-context/GroundFigure";
import { ABROAD_LABEL, GroundLegend, NAMED_RIVER_LABEL } from "@/components/map/place-context/GroundLegend";
import { GroundMap } from "@/components/map/place-context/GroundMap";
import { drawnRivers, type DrawnRiver } from "@/components/map/place-context/useGroundRivers";
import { craftGroundShape, parseWhyHereSpec, type CraftGround, type GroundPin, type GroundRiver } from "@/lib/placeGround";
import type { RegionDataset } from "@/lib/regionContract";
import type { BasinReach, LonLat, RiverBasin } from "@/lib/riverTopology";
import { parseShape } from "@/lib/shape";

import { attribute } from "./explainerRender";

const GOLDEN = JSON.parse(readFileSync(join(__dirname, "..", "..", "shared", "place.ground.golden.json"), "utf8")) as Record<string, unknown>;
const OSM_CREDIT = "© OpenStreetMap contributors";

function dataset(code: string, attribution: string | null): RegionDataset {
  return { code, title: `${code} title`, publisher: null, edition: "1", period: "static", nativeResolution: "vector", licence: "Open", licenceUrl: null, attribution, citation: null, url: null };
}

const PIN: GroundPin = { key: "abroad-Q9900001", name: "Abroad region", roles: ["PRACTISED", "ORIGIN"], country: "Pakistan", wikidataId: "Q9900001", longitude: 77.3, latitude: 20.4 };
const RIVER: GroundRiver = { key: "river-9-7-9", name: "Test River", mainRiv: 9, reachIds: [7, 8, 9], hydrorivers: dataset("HYDRORIVERS_1_0", "WWF"), names: dataset("OSM_RIVER_NAMES", OSM_CREDIT) };

function reach(id: number, nextDown: number, line: LonLat[]): [number, BasinReach] {
  return [id, { id, nextDown, ordStra: 1, line, districts: null }];
}

const BASIN: RiverBasin = {
  mainRiv: 9,
  reaches: new Map([reach(7, 8, [[76.6, 20.4], [76.8, 20.2]]), reach(8, 9, [[76.8, 20.2], [77.1, 19.9]]), reach(9, 0, [[77.1, 19.9], [77.4, 19.6]])])
};

const ground = (changes: Partial<CraftGround> = {}): CraftGround => ({ ...parseShape(craftGroundShape, GOLDEN), ...changes });

test("a ground carries its places abroad and its rivers when the server sends them, and reads as before without them", () => {
  expect(parseShape(craftGroundShape, GOLDEN).abroad).toBeUndefined();
  const marked = parseWhyHereSpec({ ground: { ...GOLDEN, abroad: [PIN], rivers: [RIVER] }, notes: [] });
  expect(marked?.ground.abroad).toEqual([PIN]);
  expect(marked?.ground.rivers).toEqual([RIVER]);
  expect(parseWhyHereSpec({ ground: { ...GOLDEN, abroad: [{ ...PIN, wikidataId: "37211" }] }, notes: [] })).toBeNull();
  expect(parseWhyHereSpec({ ground: { ...GOLDEN, abroad: [{ ...PIN, roles: [] }] }, notes: [] })).toBeNull();
  expect(parseWhyHereSpec({ ground: { ...GOLDEN, rivers: [{ ...RIVER, reachIds: [] }] }, notes: [] })).toBeNull();
});

test("a river is drawn from its basin file only when every reach is there and some of it is in the frame", () => {
  const frame = ground().frame;
  const [drawn] = drawnRivers([RIVER], new Map([[9, BASIN]]), frame);
  expect(drawn.lines).toEqual([BASIN.reaches.get(7)?.line, BASIN.reaches.get(8)?.line, BASIN.reaches.get(9)?.line]);
  expect(drawnRivers([{ ...RIVER, reachIds: [7, 8, 10] }], new Map([[9, BASIN]]), frame)).toEqual([]);
  expect(drawnRivers([RIVER], new Map(), frame)).toEqual([]);
  const far = { ...BASIN, reaches: new Map([reach(7, 8, [[80, 25], [80.1, 25]]), reach(8, 9, [[80.1, 25], [80.2, 25]]), reach(9, 0, [[80.2, 25], [80.3, 25]])]) };
  expect(drawnRivers([RIVER], new Map([[9, far]]), frame)).toEqual([]);
});

test("the map pins a place abroad as a ring with its name and draws a named river over a halo, labelled", () => {
  const frame = ground().frame;
  const rivers: DrawnRiver[] = drawnRivers([RIVER], new Map([[9, BASIN]]), frame);
  const html = renderToStaticMarkup(createElement(GroundMap, { frame, pins: [], deposits: [], radiusKm: 50, title: "T", description: "D", marks: { abroad: [PIN], rivers } }));
  expect(attribute(html, "ground-abroad-pin", "data-testid")).toHaveLength(1);
  expect(/<circle[^>]*data-testid="ground-abroad-pin"[^>]*>/.exec(html)?.[0]).toContain('stroke="var(--terracotta)"');
  expect(html).toContain(">Abroad region<");
  expect(/<path[^>]*data-testid="ground-named-river"[^>]*>/.exec(html)?.[0]).toContain('stroke="var(--map-river)"');
  expect(html).toContain(">Test River<");
  const plain = renderToStaticMarkup(createElement(GroundMap, { frame, pins: [], deposits: [], radiusKm: 50, title: "T", description: "D" }));
  expect(plain).not.toContain("ground-abroad");
  expect(plain).not.toContain("ground-named-rivers");
});

test("each drawn river cites its HydroRIVERS row and its name's row once, and a place abroad its Wikidata item", () => {
  const listed = ground().datasets;
  expect(creditedDatasets(listed, [RIVER, { ...RIVER, key: "river-2", names: dataset("WIKIDATA_RIVER_NAMES", null) }]).map((found) => found.code)).toEqual([
    ...listed.map((found) => found.code),
    "HYDRORIVERS_1_0",
    "OSM_RIVER_NAMES",
    "WIKIDATA_RIVER_NAMES"
  ]);
  const credits = renderToStaticMarkup(createElement(GroundCredits, { layers: [], datasets: [], sources: [], marks: { abroad: [PIN], rivers: [RIVER] } }));
  expect(credits).toContain(OSM_CREDIT);
  expect(credits).toContain("HYDRORIVERS_1_0 title");
  expect(credits.replace(/<[^>]+>/g, "")).toContain("Abroad region placed by Wikidata Q9900001 · CC0");
  expect(credits).toContain('href="https://www.wikidata.org/wiki/Q9900001"');
});

test("the figure lists a place abroad in its legend and credits at rest, and a named river once its basin has drawn", () => {
  const figure = renderToStaticMarkup(createElement(GroundFigure, { ground: ground({ abroad: [PIN], rivers: [RIVER] }) }));
  expect(figure).toContain(ABROAD_LABEL);
  expect(figure).toContain('data-testid="abroad-source"');
  expect(figure).not.toContain(NAMED_RIVER_LABEL);
  expect(figure).not.toContain(OSM_CREDIT);
  const legend = renderToStaticMarkup(createElement(GroundLegend, { frame: ground().frame, deposits: [], classes: ground().classes, radiusKm: 50, placed: "P", named: { abroad: false, rivers: true } }));
  expect(legend).toContain(NAMED_RIVER_LABEL);
  expect(legend).not.toContain(ABROAD_LABEL);
});
