import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { PLACE_KIND, placeMapMarks } from "@/components/map/PlaceMarkers";
import { mapPins } from "@/components/map/place-context/GroundFigure";
import { PlaceGroundView } from "@/components/map/place-context/PlaceGroundPanel";
import { COMPONENT_VIEWS } from "@/components/monograph/componentViews";
import { heldNotes, WhyHereView } from "@/components/monograph/kinds/place/WhyHereView";
import { frameView, kmUnits, placed, ringsIn } from "@/lib/groundFrame";
import type { ComponentViewProps } from "@/lib/componentViewContract";
import { APP_KINDS } from "@/lib/monographScopes";
import { craftGroundShape, mapGroundPath, parseWhyHereSpec, WHY_HERE_KIND, type CraftGround, type GroundNote, type GroundPlace, type MapPlaceGround, type Point } from "@/lib/placeGround";
import { bandText, commodityWord, elevationText, materialSentence, placesTitle } from "@/lib/placeGroundView";
import { parseShape } from "@/lib/shape";

const SHARED = join(__dirname, "..", "..", "shared");
const GOLDEN: unknown = JSON.parse(readFileSync(join(SHARED, "place.ground.golden.json"), "utf8"));
const GROUND: CraftGround = parseShape(craftGroundShape, GOLDEN);
const [VILLAGE] = GROUND.places;
const LABEL = "ground-fixture/geography/why-here";

function viewProps(spec: object, unitRefs: string[]): ComponentViewProps {
  const component = { label: LABEL, chapter: "why", anchor: "#c", kind: WHY_HERE_KIND, title: "The ground under Ground fixture", description: "A map.", field: "GEOGRAPHY", fields: [], subjects: [] };
  return { component, spec: spec as Record<string, unknown>, unitRefs, renderUnit: (ref) => `[note ${ref}]`, renderComponent: () => null };
}

function drawn(spec: object, unitRefs: string[] = []): string {
  return renderToStaticMarkup(createElement(() => WhyHereView(viewProps(spec, unitRefs))));
}

function place(name: string, changes: Partial<GroundPlace> = {}): GroundPlace {
  return { ...VILLAGE, key: name, name, ...changes };
}

test("the golden ground parses as the API writes it and the view is registered as an app kind", () => {
  expect([VILLAGE.name, VILLAGE.ground.river?.distanceKm, VILLAGE.ground.lake?.distanceKm, GROUND.deposits.length]).toEqual(["Fixture village", 10.4, 45.8, 2]);
  expect(parseWhyHereSpec({ ground: GOLDEN, notes: [{ reading: "river", unit: "u0001" }] })?.notes).toEqual([{ reading: "river", unit: "u0001" }]);
  expect(parseWhyHereSpec({ ground: GOLDEN, notes: [{ reading: "sky", unit: "u0001" }] })).toBeNull();
  expect(COMPONENT_VIEWS[WHY_HERE_KIND]).toBe(WhyHereView);
  expect(APP_KINDS.has(WHY_HERE_KIND)).toBe(true);
});

test("readings are written in metres and kilometres, and a material's deposits as data", () => {
  expect(elevationText(VILLAGE.ground.elevation)).toBe("300–600 m");
  expect([bandText(null), bandText(100), bandText(1000), bandText(4000)]).toEqual(["Below 100 m", "100–300 m", "1,000–2,000 m", "Above 4,000 m"]);
  expect(VILLAGE.materials.map((match) => materialSentence(match, GROUND.radiusKm, VILLAGE.name))).toEqual([
    "1 recorded aluminium deposit within 50 km of Fixture village, the nearest 33.4 km away.",
    "1 recorded iron deposit within 50 km of Fixture village, the nearest 11.1 km away."
  ]);
  const brass = { material: "Brass", commodities: ["Copper", "Zinc"], count: 3, nearestKm: 4 };
  expect(materialSentence(brass, 50, "Moradabad")).toBe("3 recorded copper or zinc deposits within 50 km of Moradabad, the nearest 4 km away.");
  expect([commodityWord("Stone, Dimension"), commodityWord("Sulfur"), commodityWord("Copper")]).toEqual(["dimension stone", "sulphur", "copper"]);
});

test("a figure names up to three places and counts the rest", () => {
  expect(placesTitle([place("Ajrakhpur")])).toBe("Ajrakhpur");
  expect(placesTitle([place("Ajrakhpur"), place("Dhamadka"), place("Bhuj")])).toBe("Ajrakhpur, Dhamadka and Bhuj");
  expect(placesTitle(["A", "B", "C", "D", "E"].map((name) => place(name)))).toBe("A, B and 3 more places");
  expect(mapPins([place("Ajrakhpur")]).map((pin) => pin.label)).toEqual(["Ajrakhpur"]);
  expect(mapPins([place("Ajrakhpur"), place("Dhamadka")]).map((pin) => pin.label)).toEqual(["1", "2"]);
});

test("the frame is drawn to scale: the place at its centre and the radius in the same units", () => {
  const view = frameView(GROUND.frame);
  expect(view.width).toBe(640);
  expect(view.height).toBeCloseTo(640.58, 2);
  const centre = placed(view, [77, 20]);
  expect(centre.x).toBeCloseTo(320, 6);
  expect(centre.y).toBeCloseTo(320.29, 2);
  expect(kmUnits(view, 50)).toBeCloseTo(275.9, 1);
  const far: Point[] = [[60, 10], [61, 10], [61, 11]];
  const near: Point[] = [[76, 19], [77, 19], [77, 20]];
  expect(ringsIn(GROUND.frame, [far])).toEqual([]);
  expect(ringsIn(GROUND.frame, [near])).toEqual([near]);
});

test("the why here figure draws the place, its matched deposits, its measured ground and the cited sentence beside its reading", () => {
  const notes: GroundNote[] = [
    { reading: "river", unit: "u0001" },
    { reading: "lake", unit: "u0009" }
  ];
  expect(heldNotes(notes, ["u0001"])).toEqual([notes[0]]);
  const html = drawn({ ground: GOLDEN, notes }, ["u0001"]);
  expect(html).toContain('data-testid="why-here"');
  expect(html.match(/data-testid="ground-pin"/g)).toHaveLength(1);
  expect(html.match(/data-matched=""/g)).toHaveLength(2);
  for (const text of ["300–600 m", "10.4 km", "45.8 km", "2 within 50 km", "Clays and earths the craft works", "River clay", "1 recorded iron deposit within 50 km of Fixture village", "A fixture source that places the craft", "All 3 values"]) {
    expect(html).toContain(text);
  }
  expect(html).toContain("[note u0001]");
  expect(html).not.toContain("[note u0009]");
  expect(drawn({ ground: { ...(GOLDEN as object), places: [] }, notes: [] })).toBe("");
});

test("choosing a craft place on the map opens the ground measured there", () => {
  const marks = placeMapMarks([{ key: "district-449", name: "Kachchh", longitude: 69.86, latitude: 23.73, total: 1, family: null, href: "/crafts", crafts: [] }], 1);
  expect(marks.map((mark) => [mark.kind, mark.place])).toEqual([[PLACE_KIND, { longitude: 69.86, latitude: 23.73 }]]);
  expect(mapGroundPath(69.86, 23.73)).toBe("/map/ground?longitude=69.86&latitude=23.73");
  const ground: MapPlaceGround = { schemaVersion: 1, district: "Kachchh", longitude: 77, latitude: 20, radiusKm: 50, ground: VILLAGE.ground, classes: GROUND.classes, layers: GROUND.layers, datasets: [] };
  const html = renderToStaticMarkup(createElement(PlaceGroundView, { ground, headingId: "g" }));
  for (const text of ["The ground here", "Kachchh district", "300–600 m", "ETOPO1, sha256 abcdef012345", "Natural Earth 1:10m rivers, 5.0.0"]) expect(html).toContain(text);
});
