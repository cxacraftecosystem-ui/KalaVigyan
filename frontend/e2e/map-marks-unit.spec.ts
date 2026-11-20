import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { mapFrame } from "@/components/map/basemap";
import { layoutPins } from "@/components/map/layout";
import { MarkControls } from "@/components/map/MarkControls";
import { MarkPanelBody, panelSurface } from "@/components/map/MarkPanel";
import { cardAbove, cardPlacement, firstCrafts, markBox, markLabel, steppedKey, type MapMark } from "@/components/map/markPlacement";
import { PinControls } from "@/components/map/PinControls";
import { MARKER_PX, placeMapMarks } from "@/components/map/PlaceMarkers";
import { RankedList } from "@/components/map/RankedList";
import { placedCircles, STATE_KIND, stateMapMarks } from "@/components/map/StateCircles";
import { StateCraftsList } from "@/components/map/StateCraftsList";
import { listCounts, stateCrafts } from "@/lib/atlasIndex";
import { parseCraftCatalogue } from "@/lib/craftCatalogueContract";
import { placeMarkers } from "@/lib/mapFamilies";
import { allCraftsLabel, allStatesLabel, stateAnchor, stateListDek } from "@/lib/mapStates";
import type { CraftMapPoint } from "@/lib/types";

const SHARED = join(__dirname, "..", "..", "shared");
const CATALOGUE = parseCraftCatalogue(JSON.parse(readFileSync(join(SHARED, "craft.catalogue.golden.json"), "utf8")));
const SCENE = { frame: mapFrame(), scale: 1.5 };

const mark = (key: string, x: number, y: number, crafts = 4): MapMark => ({
  key,
  name: key,
  kind: STATE_KIND,
  x,
  y,
  r: 20,
  count: crafts,
  crafts: Array.from({ length: crafts }, (_, at) => ({ slug: `${key}-${at}`, name: `${key} craft ${at}`, monograph: at === 0 })),
  more: { href: `/crafts?q=${key}`, label: `Read ${key}’s crafts in the atlas` }
});

test("every craft is listed under each state it is practised in, monographs first, and the rest belong to all of India", () => {
  const lists = stateCrafts(CATALOGUE);
  expect(lists.states.map((state) => [state.name, state.crafts.map((craft) => craft.displayName)])).toEqual([
    ["Rajasthan", ["Bagru Hand Block Print", "Phulkari", "Sanganeri Hand Block Printing"]],
    ["Chhattisgarh", ["Bastar Dhokra"]],
    ["Gujarat", ["Kutch Ajrakh"]],
    ["Haryana", ["Phulkari"]],
    ["Jammu and Kashmir", ["Phulkari"]],
    ["Punjab", ["Phulkari"]]
  ]);
  expect(lists.allIndia.map((craft) => craft.displayName)).toEqual(["Brass and Bell Metal Craft", "Metal Embossing"]);
  expect(listCounts(lists)).toEqual({ states: lists.states.map((state) => ({ name: state.name, count: state.crafts.length })), allIndia: 2 });
});

test("a state's mark carries its count, its crafts with their pages and a way into the atlas", () => {
  const lists = stateCrafts(CATALOGUE);
  const circles = placedCircles([
    { name: "Rajasthan", count: 3, longitude: 74.2, latitude: 27 },
    { name: "Gujarat", count: 1, longitude: 71.5, latitude: 22.6 }
  ]);
  const [rajasthan, gujarat] = stateMapMarks(circles, lists.states);
  expect([rajasthan.name, rajasthan.count, rajasthan.kind]).toEqual(["Rajasthan", 3, "State or union territory"]);
  expect(rajasthan.crafts.map((craft) => craft.slug)).toEqual(["Bagru-Hand-Block-Print", "Phulkari", "Sanganeri-Hand-Block-Printing"]);
  expect(gujarat.crafts).toEqual([{ slug: "Kutch-Ajrakh", name: "Kutch Ajrakh", monograph: true }]);
  expect(rajasthan.more).toEqual({ href: "/crafts?q=Rajasthan#atlas-search", label: "Read Rajasthan’s crafts in the atlas" });
  expect(rajasthan.r).toBeGreaterThan(gujarat.r);
  expect(markLabel(rajasthan)).toBe("Rajasthan, 3 crafts");
  expect(firstCrafts(mark("Kerala", 0, 0, 5))).toEqual({ names: ["Kerala craft 0", "Kerala craft 1", "Kerala craft 2"], rest: 2 });
});

test("a mark is a control at least 24px wide over its circle, and its card sits clear of the circle", () => {
  const frame = { x: 0, y: 0, width: 1000, height: 1000 };
  expect(markBox({ x: 250, y: 500, r: 10 }, frame)).toEqual({ left: "25.000%", top: "50.000%", width: "max(24px, 2.000%)" });
  expect(cardAbove({ y: 900 }, frame)).toBe(true);
  expect(cardAbove({ y: 100 }, frame)).toBe(false);
  expect(cardPlacement({ x: 500, y: 100, r: 30 }, { frame, scale: 1 })).toEqual({ left: "clamp(0px, calc(50.000% - 120px), calc(100% - 240px))", top: "calc(13.000% + 10px)" });
  expect(cardPlacement({ x: 500, y: 900, r: 4 }, { frame, scale: 1 })).toEqual({ left: "clamp(0px, calc(50.000% - 120px), calc(100% - 240px))", bottom: "calc(11.200% + 10px)" });
});

test("arrow keys, Home and End move between marks and wrap round", () => {
  const keys = ["a", "b", "c"];
  expect([steppedKey(keys, "a", "ArrowRight"), steppedKey(keys, "c", "ArrowDown"), steppedKey(keys, "a", "ArrowLeft"), steppedKey(keys, "b", "Home"), steppedKey(keys, "a", "End"), steppedKey(keys, "a", "Tab")]).toEqual([
    "b",
    "a",
    "c",
    "a",
    "c",
    null
  ]);
  expect([panelSurface(360), panelSurface(640), panelSurface(1440)]).toEqual(["sheet", "popover", "popover"]);
});

test("the marks are one tab stop of named buttons that each open a panel", () => {
  const marks = [mark("Uttar Pradesh", 500, 400, 64), mark("Gujarat", 200, 600, 37)];
  const html = renderToStaticMarkup(createElement(MarkControls, { marks, scene: SCENE, focus: { active: null, onActive: () => undefined }, label: "States on the map" }));
  expect(html).toContain('role="group" aria-label="States on the map"');
  expect(html.match(/data-testid="map-mark"/g)).toHaveLength(2);
  expect(html.match(/tabindex="0"/g)).toHaveLength(1);
  expect(html.match(/tabindex="-1"/g)).toHaveLength(1);
  expect(html).toContain('aria-label="Uttar Pradesh, 64 crafts"');
  expect(html.match(/aria-haspopup="dialog"/g)).toHaveLength(2);
  expect(html).not.toContain("map-mark-card");
  const shown = renderToStaticMarkup(createElement(MarkControls, { marks, scene: SCENE, focus: { active: "Gujarat", onActive: () => undefined }, label: "States" }));
  expect(shown).toContain('data-testid="map-mark-card"');
  expect(shown).toContain("Gujarat craft 0, Gujarat craft 1, Gujarat craft 2");
  expect(shown).toContain(" and 34 more");
});

test("a mark's panel lists every craft practised there, each a link to its page, with a close button", () => {
  const html = renderToStaticMarkup(createElement(MarkPanelBody, { mark: mark("Odisha", 0, 0, 12), headingId: "h", onClose: () => undefined }));
  expect(html.match(/<li/g)).toHaveLength(12);
  expect(html).toContain('href="/crafts/Odisha-11"');
  expect(html).toContain("12 crafts practised here");
  expect(html.match(/>Monograph</g)).toHaveLength(1);
  expect(html).toContain('aria-label="Close Odisha"');
  expect(html).toContain('<h2 id="h"');
  expect(html).toContain("Read Odisha’s crafts in the atlas");
});

test("the map page lists every state and under each every craft, with anchors the ranked list links to", () => {
  const lists = stateCrafts(CATALOGUE);
  const html = renderToStaticMarkup(createElement(StateCraftsList, { lists }));
  expect(html.match(/data-testid="state-crafts-group"/g)).toHaveLength(lists.states.length + 1);
  expect(html).toContain(`id="${stateAnchor("Jammu and Kashmir")}"`);
  expect(stateAnchor("Jammu & Kashmir")).toBe("state-jammu-and-kashmir");
  expect(html.match(/href="\/crafts\//g)).toHaveLength(10);
  expect(html).toContain(">All India<");
  expect(stateListDek(6, 2)).toBe("Every craft is listed under each of the 6 states and union territories where it is practised, monographs first. 2 crafts belong to all of India.");
  expect(stateListDek(1, 0)).toBe("Every craft is listed under each of the 1 state or union territory where it is practised, monographs first.");
});

test("the ranked list offers every state in place and the whole craft list beside it", () => {
  const rows = Array.from({ length: 33 }, (_, at) => ({ key: `s${at}`, name: `State ${at}`, value: 40 - at }));
  const html = renderToStaticMarkup(createElement(RankedList, { rows, label: "Crafts", all: { label: allStatesLabel(33) } }));
  expect(html).toContain('aria-expanded="false"');
  expect(html).toContain(">All 33 states and union territories</button>");
  expect(allCraftsLabel(426)).toBe("All 426 crafts in the atlas");
});

test("craft places become marks listing their crafts, and answer pins become named buttons", () => {
  const point = (key: string, name: string, slugs: string[]): CraftMapPoint => ({ key, name, latitude: 23, longitude: 70, total: slugs.length, crafts: slugs.map((slug) => ({ slug, name: slug })) });
  const markers = placeMarkers([point("district-1", "Kachchh", ["Kutch-Ajrakh"]), point("district-2", "Bastar", ["Bastar-Dhokra", "Phulkari"])], CATALOGUE);
  const marks = placeMapMarks(markers, 2);
  expect(marks.map((place) => [place.name, place.count, place.kind, place.r])).toEqual([
    ["Bastar", 2, "Craft place", MARKER_PX * 2],
    ["Kachchh", 1, "Craft place", MARKER_PX * 2]
  ]);
  expect(marks[1].crafts).toEqual([{ slug: "Kutch-Ajrakh", name: "Kutch-Ajrakh", monograph: true }]);
  const pins = layoutPins([{ key: "a", name: "Kachchh", latitude: 23.5, longitude: 69.8, total: 3 }]);
  const html = renderToStaticMarkup(createElement(PinControls, { pins, frame: { x: 0, y: 0, width: 1000, height: 1114 }, selectedKey: "a", onSelect: () => undefined }));
  expect(html).toContain('aria-label="Kachchh, 3 crafts"');
  expect(html).toContain('aria-pressed="true"');
  expect(html).toContain('tabindex="0"');
});
