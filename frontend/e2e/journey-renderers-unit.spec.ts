import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";
import { createElement, type ReactElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { BLOCK_RENDERERS } from "@/components/answer/blockRenderers";
import type { CitationLookup } from "@/components/answer/CitationContext";
import { FilmSceneProvider } from "@/components/answer/FilmScene";
import { MAX_ZOOM } from "@/components/answer/journey/journeyGeometry";
import { TimelineMap, TimelineMapView } from "@/components/answer/journey/TimelineMap";
import { ZoomDistrictMap } from "@/components/answer/journey/ZoomDistrict";
import { ZoomStory, ZoomStoryView } from "@/components/answer/journey/ZoomStory";
import { decodeShapes, type DistrictShape, type ShapesFile } from "@/components/map/shapeGeometry";
import { BLOCK_SHAPES, type TypedBlockKind } from "@/lib/explainerContract";
import type { TimelineMapBlock } from "@/lib/explainerPlay";
import type { SectionView } from "@/lib/explainerState";
import { blockSentences, blockSourceIds, explainerSourceNumbers } from "@/lib/explainerView";
import { sceneStep, stepAt } from "@/lib/filmScenes";
import { parseShape } from "@/lib/shape";
import { entryState, placedPlaces, timelineEntries, timelineStops, yearSpanText } from "@/lib/timelineView";
import { zoomSummary } from "@/lib/zoomView";

import { attribute, FIXED_WIDE_WIDTH, gridTracks, SHRINKABLE_TRACK, shownText, withApp } from "./explainerRender";
import { eagerModules } from "./moduleGraph";
import { PHASE_C, phaseCBlock } from "./playFixture";

const zoom = () => phaseCBlock("zoom_story", "s3.b1");
const timeline = () => phaseCBlock("timeline_map", "s4.b1");
const GI_JOURNAL = "d0f53ee9-4b97-5df7-a367-686957bdb7c8";
const MORDANT_PAPER = "9187df8b-62e3-510a-ba5d-827ec098c84c";
const ALIZARIN_RECORD = "ffd974aa-9172-566a-8a38-dcc5c3c4f2d6";
const TEXTILE_SOCIETY = "f60ab91b-7057-56fe-a4c0-17664472b776";
const AJRAKH_INTRODUCTION = "56c24809-a5fd-5d90-b6db-e55d7be09c07";
const KACHCHH = 449;
const INDIA_BOX = { minLongitude: 68.206, maxLongitude: 97.394, minLatitude: 6.756, maxLatitude: 37.082 };
const BOUNDARY_CAPTION = "External boundaries of India as depicted by Survey of India. District boundaries are indicative.";
const LOOKUP: CitationLookup = {
  numbers: new Map([
    [GI_JOURNAL, 1],
    [MORDANT_PAPER, 2],
    [ALIZARIN_RECORD, 3],
    [TEXTILE_SOCIETY, 4],
    [AJRAKH_INTRODUCTION, 5]
  ]),
  sourcesById: new Map()
};

let shapesCache: DistrictShape[] | null = null;

function shapes(): DistrictShape[] {
  shapesCache ??= decodeShapes(JSON.parse(readFileSync(join(__dirname, "..", "public", "boundaries", "district-shapes.json"), "utf8")) as ShapesFile);
  return shapesCache;
}

function parsedBlock<K extends TypedBlockKind>(kind: K, value: unknown) {
  return parseShape(BLOCK_SHAPES[kind], value);
}

function drawn(child: ReactElement): string {
  return withApp(child, LOOKUP);
}

function filmed(child: ReactElement, progress: number): string {
  return drawn(createElement(FilmSceneProvider, { value: { progress } }, child));
}

function placedTimeline(): TimelineMapBlock {
  const block = timeline();
  const places = block.places.map((place) => {
    if (place.name === "Dhamadka") return { ...place, wikidataId: "Q1", latitude: 23.6, longitude: 69.6 };
    if (place.name === "Sindh") return { ...place, wikidataId: "Q2", latitude: 25.9, longitude: 68.5 };
    if (place.name === "Kutch") return { ...place, wikidataId: "Q3", latitude: 23.7, longitude: 69.8 };
    return place;
  });
  return parseShape(BLOCK_SHAPES.timeline_map, { ...block, places });
}

function disabledButtons(html: string): string[] {
  return [...html.matchAll(/<button[^>]*disabled=""[^>]*>(.*?)<\/button>/g)].map((found) => found[1].replace(/<[^>]+>/g, ""));
}

function pinLabels(html: string): string[] {
  return [...html.matchAll(/data-testid="map-pin-label">(\d+)<\/text>/g)].map((found) => found[1]);
}

test("the zoom story and the timeline map are drawn through the renderer registry, their code loaded on demand", () => {
  for (const kind of ["zoom_story", "timeline_map"] as const) expect(BLOCK_RENDERERS[kind]).toBeDefined();
  expect(renderToStaticMarkup(createElement(BLOCK_RENDERERS.zoom_story!, { block: zoom() }))).toContain('data-testid="map-placeholder"');
  expect(renderToStaticMarkup(createElement(BLOCK_RENDERERS.timeline_map!, { block: timeline() }))).toContain('data-testid="map-placeholder"');
  const eager = eagerModules("@/components/answer/blockRenderers");
  expect(eager.has("components/answer/journey/journeyRenderers.tsx")).toBe(true);
  for (const heavy of [
    "components/answer/journey/ZoomStory.tsx",
    "components/answer/journey/ZoomDistrict.tsx",
    "components/answer/journey/ZoomLevelView.tsx",
    "components/answer/journey/TimelineMap.tsx",
    "components/answer/journey/TimelinePins.tsx",
    "components/answer/journey/journeyGeometry.ts",
    "components/map/IndiaMap.tsx",
    "components/map/projection.ts"
  ]) {
    expect(eager.has(heavy), heavy).toBe(false);
  }
});

test("both kinds join the answer's one numbering: sentences in the server's order, the compound's record after its citations", () => {
  expect(blockSentences(zoom()).map((sentence) => sentence.id)).toEqual(["s3.b1.1", "s3.b1.2", "s3.b1.3"]);
  expect(blockSourceIds(zoom())).toEqual([GI_JOURNAL, GI_JOURNAL, MORDANT_PAPER, MORDANT_PAPER, ALIZARIN_RECORD]);
  expect(blockSentences(timeline()).map((sentence) => sentence.id)).toEqual(["s4.b1.1", "s4.b1.2", "s4.b1.3", "s4.b1.4"]);
  const sections = PHASE_C.sections.map((section, index) => ({
    id: section.id,
    discipline: "OVERVIEW",
    title: section.id,
    order: index + 1,
    state: "READY",
    searched: null,
    blocks: section.blocks.map((block) => parsedBlock(block.kind as TypedBlockKind, structuredClone(block)))
  })) as unknown as SectionView[];
  expect([...explainerSourceNumbers(sections).keys()]).toEqual(PHASE_C.sources.map((source) => source.id));
});

test("the zoom draws one level at a time, the district first, with a rail of every level", () => {
  const html = drawn(createElement(ZoomStoryView, { block: zoom(), reduce: false, at: 0, onChoose: () => undefined }));
  const shown = shownText(html);
  expect(attribute(html, "zoom-story", "data-motion")).toEqual(["zoom"]);
  expect(attribute(html, "zoom-story", "data-level")).toEqual(["DISTRICT"]);
  expect(attribute(html, "zoom-story", "aria-label")).toEqual([zoomSummary(zoom())]);
  expect(zoomSummary(zoom())).toBe("Kachchh → Ajrak Printing Materials 1 → Alizarin");
  expect(attribute(html, "zoom-rail-level", "aria-pressed")).toEqual(["true", "false", "false"]);
  expect([...html.matchAll(/data-testid="zoom-rail-level"[^>]*>([^<]+)</g)].map((found) => found[1])).toEqual(["District", "Workshop", "Molecule"]);
  expect(attribute(html, "zoom-level", "data-level")).toEqual(["DISTRICT"]);
  expect(html).toContain(">District · 1 of 3<");
  expect(html).toContain(">Kachchh</h3>");
  expect(shown).toContain("Ajrakh printing is practised at Kachchh and Barmer.");
  expect(html).toContain('data-testid="map-placeholder"');
  expect(disabledButtons(html)).toEqual(["Zoom out"]);
});

test("the picture level carries its open licence and author, the molecule level its 3D view and PubChem record", () => {
  const workshop = drawn(createElement(ZoomStoryView, { block: zoom(), reduce: false, at: 1, onChoose: () => undefined }));
  expect(attribute(workshop, "zoom-level", "data-level")).toEqual(["WORKSHOP"]);
  expect(workshop).toContain(">Ajrak Printing Materials 1</h3>");
  expect(workshop).toContain('alt="Sticky gums used during indigo printing."');
  expect(workshop).toContain("SMarndi");
  expect(workshop).toContain('href="https://creativecommons.org/licenses/by-sa/4.0"');
  expect(workshop).toContain(">CC BY-SA 4.0<");
  expect(workshop).toContain("Wikimedia Commons");
  expect(workshop).toContain('href="https://commons.wikimedia.org/wiki/File:Ajrak_Printing_Materials_1.jpg"');
  const molecule = drawn(createElement(ZoomStoryView, { block: zoom(), reduce: false, at: 2, onChoose: () => undefined }));
  expect(attribute(molecule, "zoom-level", "data-level")).toEqual(["MOLECULE"]);
  expect(attribute(molecule, "molecule-3d", "data-status")).toEqual(["waiting"]);
  expect(molecule).toContain("PubChem CID 6293");
  expect(molecule).toMatch(/aria-label="Source 3[^"]*"[^>]*data-testid="source-chip"/);
  expect(molecule).not.toContain("</h3>");
  expect(disabledButtons(molecule)).toEqual(["Zoom in"]);
  const clamped = drawn(createElement(ZoomStoryView, { block: zoom(), reduce: false, at: 9, onChoose: () => undefined }));
  expect(attribute(clamped, "zoom-story", "data-level")).toEqual(["MOLECULE"]);
});

test("reduced motion shows every level as a list, in zoom order, with no rail and no zoom buttons", () => {
  const html = drawn(createElement(ZoomStoryView, { block: zoom(), reduce: true, at: 0, onChoose: () => undefined }));
  expect(attribute(html, "zoom-story", "data-motion")).toEqual(["none"]);
  expect(attribute(html, "zoom-level", "data-level")).toEqual(["DISTRICT", "WORKSHOP", "MOLECULE"]);
  expect(html).toContain('data-testid="zoom-list"');
  expect(html).not.toContain('data-testid="zoom-rail"');
  expect(html).not.toContain("Zoom in");
  for (const level of zoom().levels) expect(shownText(html)).toContain(level.sentence.text);
});

test("in a film the zoom moves through its levels with the scene, and the rail only marks the level", () => {
  expect([0, 0.33, 0.34, 0.67, 1].map((progress) => stepAt(progress, 3))).toEqual([0, 0, 1, 2, 2]);
  const middle = filmed(createElement(ZoomStory, { block: zoom() }), 0.5);
  expect(attribute(middle, "zoom-story", "data-level")).toEqual(["WORKSHOP"]);
  expect(middle).not.toContain('aria-pressed="');
  expect(attribute(middle, "zoom-rail-level", "aria-current")).toEqual(["", "step", ""]);
  expect(middle).not.toContain("Zoom in");
  expect(attribute(filmed(createElement(ZoomStory, { block: zoom() }), 1), "zoom-story", "data-level")).toEqual(["MOLECULE"]);
  expect(attribute(drawn(createElement(ZoomStory, { block: zoom() })), "zoom-story", "data-level")).toEqual(["DISTRICT"]);
});

test("the district level zooms into the register's polygon under the boundary caption, holds still when not moving, and draws no map for a district the shapes lack", () => {
  const block = zoom();
  const district = block.levels[0].district!;
  const boundary = { caption: block.boundaryCaption!, dataset: block.datasets[0] };
  const moving = drawn(createElement(ZoomDistrictMap, { shapes: shapes(), district, boundary, moving: true }));
  expect(attribute(moving, "zoom-district", "data-lgd")).toEqual([String(KACHCHH)]);
  expect(attribute(moving, "zoom-district", "data-scale")).toEqual([String(MAX_ZOOM)]);
  expect(moving).toMatch(new RegExp(`data-testid="district-outlines"[\\s\\S]*data-lgd="${KACHCHH}"`));
  expect(moving).toContain(">Kachchh</text>");
  expect(shownText(moving)).toContain(BOUNDARY_CAPTION);
  expect(moving).toContain("Indian district boundaries, matched to LGD codes");
  expect(moving).not.toContain("Designer Portal");
  const still = drawn(createElement(ZoomDistrictMap, { shapes: shapes(), district, boundary, moving: false }));
  expect(attribute(still, "zoom-district", "data-scale")).toEqual(["1"]);
  const unknown = drawn(createElement(ZoomDistrictMap, { shapes: shapes(), district: { ...district, districtLgd: 999999 }, boundary, moving: true }));
  expect(unknown).toBe("");
});

test("a span of years reads as the texts state it", () => {
  expect(yearSpanText(1586, 1586)).toBe("1586");
  expect(yearSpanText(1586, 1631)).toBe("1586–1631");
  expect(yearSpanText(1401, 1500)).toBe("15th century");
  expect(yearSpanText(1001, 1400)).toBe("11th–14th century");
  expect(yearSpanText(2001, 2100)).toBe("21st century");
  expect(yearSpanText(1101, 1200)).toBe("12th century");
  expect(yearSpanText(1201, 1300)).toBe("13th century");
  expect(yearSpanText(1950, 1959)).toBe("1950s");
  expect(yearSpanText(1955, 1959)).toBe("1955–1959");
});

test("points and routes are listed in time order, each with its years, places and citation", () => {
  const entries = timelineEntries(timeline());
  expect(entries.map((entry) => [entry.key, yearSpanText(entry.yearFrom, entry.yearTo)])).toEqual([
    ["point:0", "15th century"],
    ["point:1", "1586"],
    ["route:0", "1586–1631"],
    ["point:2", "2001"]
  ]);
  expect(timelineStops(entries)).toEqual([1401, 1586, 2001]);
  expect(entries.map((entry) => entryState(entry, 1586))).toEqual(["past", "current", "current", "later"]);
  expect(placedPlaces(timeline(), INDIA_BOX).map((place) => [place.name, place.pin, place.beyond])).toEqual([["Fustat", 1, true]]);
  const html = drawn(createElement(TimelineMapView, { block: timeline(), at: 2, onChoose: () => undefined }));
  const shown = shownText(html);
  expect(attribute(html, "timeline-map", "data-year")).toEqual(["2001"]);
  expect(attribute(html, "timeline-item", "data-kind")).toEqual(["point", "point", "route", "point"]);
  expect(attribute(html, "timeline-entry", "data-state")).toEqual(["past", "past", "past", "current"]);
  expect([...html.matchAll(/data-testid="timeline-years">([^<]+)</g)].map((found) => found[1])).toEqual(["15th century", "1586", "1586–1631", "2001"]);
  expect(shown).toContain("Sindh");
  expect(shown).toContain("Kutch");
  expect(html.match(/data-testid="citation-chip"/g)).toHaveLength(4);
  for (const sentence of blockSentences(timeline())) expect(shown).toContain(sentence.text);
  expect(attribute(html, "timeline-entry-pin", "data-testid")).toHaveLength(1);
});

test("the slider runs over every point's and route's years and the map follows it", () => {
  const latest = drawn(createElement(TimelineMapView, { block: timeline(), at: 2, onChoose: () => undefined }));
  const slider = /<input[^>]*type="range"[^>]*>/.exec(latest)?.[0] ?? "";
  for (const part of ['min="0"', 'max="2"', 'step="1"', 'value="2"', 'aria-valuetext="2001"']) expect(slider).toContain(part);
  expect([...latest.matchAll(/data-testid="timeline-year">([^<]+)</g)].map((found) => found[1])).toEqual(["2001"]);
  expect(latest).toMatch(/<span>15th century<\/span><span>2001<\/span>/);
  const earliest = drawn(createElement(TimelineMapView, { block: timeline(), at: 0, onChoose: () => undefined }));
  expect(attribute(earliest, "timeline-map", "data-year")).toEqual(["1401"]);
  expect(attribute(earliest, "timeline-entry", "data-state")).toEqual(["current", "later", "later", "later"]);
  expect(earliest).toContain('aria-valuetext="15th century"');
  expect(attribute(earliest, "timeline-edge-post", "data-pin")).toEqual(["1"]);
  expect([sceneStep(2, 3, 0, true), sceneStep(2, 3, 0, false), sceneStep(2, 3, null, false), sceneStep(2, 3, 0.5, false)]).toEqual([2, 0, 2, 1]);
  expect(attribute(filmed(createElement(TimelineMap, { block: timeline() }), 0), "timeline-map", "data-year")).toEqual(["1401"]);
  expect(attribute(filmed(createElement(TimelineMap, { block: timeline() }), 0.5), "timeline-map", "data-year")).toEqual(["1586"]);
  expect(attribute(drawn(createElement(TimelineMap, { block: timeline() })), "timeline-map", "data-year")).toEqual(["2001"]);
});

test("a place beyond India is a signpost at the frame's edge on the plain ground, with its Wikidata item, under the boundary caption", () => {
  const html = drawn(createElement(TimelineMapView, { block: timeline(), at: 2, onChoose: () => undefined }));
  expect(attribute(html, "timeline-edge-post", "data-pin")).toEqual(["1"]);
  expect(attribute(html, "timeline-edge-post", "data-angle")).toEqual(["180"]);
  expect(html).toContain(">1 Fustat</text>");
  expect(pinLabels(html)).toEqual([]);
  expect(html).not.toContain('data-testid="timeline-route"');
  expect(html).toContain('href="https://www.wikidata.org/wiki/Q839456"');
  expect(shownText(html)).toContain(BOUNDARY_CAPTION);
  expect(html).not.toMatch(/Pakistan|Egypt<\/text>/);
});

test("placed places inside the frame are pins, and a stated move between two placed ends is a route", () => {
  const block = placedTimeline();
  const latest = drawn(createElement(TimelineMapView, { block, at: 2, onChoose: () => undefined }));
  expect(pinLabels(latest).sort()).toEqual(["2", "3", "4"]);
  expect(attribute(latest, "timeline-route", "data-testid")).toHaveLength(1);
  expect(attribute(latest, "timeline-entry-pin", "data-testid")).toHaveLength(4);
  const earliest = drawn(createElement(TimelineMapView, { block, at: 0, onChoose: () => undefined }));
  expect(pinLabels(earliest)).toEqual([]);
  expect(earliest).not.toContain('data-testid="timeline-route"');
  expect(attribute(earliest, "timeline-edge-post", "data-pin")).toEqual(["1"]);
});

test("with nothing placed there is no map, and with one moment there is no slider", () => {
  const block = timeline();
  const unplaced = parseShape(BLOCK_SHAPES.timeline_map, { ...block, places: block.places.map((place) => ({ ...place, wikidataId: null, latitude: null, longitude: null })) });
  const listOnly = drawn(createElement(TimelineMapView, { block: unplaced, at: 2, onChoose: () => undefined }));
  expect(listOnly).not.toContain('data-testid="timeline-pins"');
  expect(listOnly).not.toContain('data-testid="map-attribution"');
  expect(attribute(listOnly, "timeline-entry", "data-testid")).toHaveLength(4);
  const single = parseShape(BLOCK_SHAPES.timeline_map, { ...block, places: block.places.slice(0, 1), points: block.points.slice(0, 1), routes: [] });
  const one = drawn(createElement(TimelineMapView, { block: single, at: 0, onChoose: () => undefined }));
  expect(one).not.toContain('type="range"');
  expect(attribute(one, "timeline-entry", "data-state")).toEqual(["current"]);
  expect(attribute(one, "timeline-edge-post", "data-pin")).toEqual(["1"]);
});

test("journey renderers lay out in shrinkable columns so nothing widens a phone page", () => {
  const block = zoom();
  const html = [
    drawn(createElement(ZoomStoryView, { block, reduce: false, at: 1, onChoose: () => undefined })),
    drawn(createElement(ZoomStoryView, { block, reduce: true, at: 0, onChoose: () => undefined })),
    drawn(createElement(ZoomDistrictMap, { shapes: shapes(), district: block.levels[0].district!, boundary: { caption: block.boundaryCaption!, dataset: block.datasets[0] }, moving: true })),
    drawn(createElement(TimelineMapView, { block: placedTimeline(), at: 1, onChoose: () => undefined }))
  ].join("");
  const tracks = gridTracks(html);
  expect(tracks.length).toBeGreaterThan(0);
  for (const track of tracks) expect(track, track).toMatch(SHRINKABLE_TRACK);
  expect(html).not.toMatch(FIXED_WIDE_WIDTH);
  expect(html).toContain('data-testid="zoom-district"');
});
