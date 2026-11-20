import { expect, test } from "@playwright/test";
import { motionValue } from "framer-motion";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { RiverStage } from "@/components/answer/place/RiverStage";
import { storyGeometry, storyTone, type StoryGeometry } from "@/components/answer/place/storyGeometry";
import { storyLayerFill, storyLayerInView } from "@/components/answer/place/storyLayer";
import { StoryLayerReadout, storyScopeNote } from "@/components/answer/place/StoryLayerReadout";
import type { StoryLayer } from "@/components/answer/place/useStoryLayer";
import { NO_DATA_TONE } from "@/components/map/DistrictLayer";
import { IndiaLocator, locatorLabel } from "@/components/map/IndiaLocator";
import { decodeShapes, type DistrictShape, type ShapesFile } from "@/components/map/shapeGeometry";
import { layerInView, viewClasses } from "@/lib/layerClasses";
import type { MapLayer } from "@/lib/regionContract";
import { ALL_PASSED } from "@/lib/regionStory";

import { attribute, shownText } from "./explainerRender";
import { phaseBBlock, readRepo } from "./phaseBFixture";

const KACHCHH = 449;
const NATIONAL_CLASSES = [
  { min: 0, max: 100 },
  { min: 100, max: 1000 },
  { min: 1000, max: 2000 },
  { min: 2000, max: 3000 },
  { min: 3000, max: 4000 }
];

let shapesCache: DistrictShape[] | null = null;
function shapes(): DistrictShape[] {
  shapesCache ??= decodeShapes(JSON.parse(readRepo("frontend", "public", "boundaries", "district-shapes.json")) as ShapesFile);
  return shapesCache;
}

function geometry(): StoryGeometry {
  const drawn = storyGeometry(phaseBBlock("region_story", "s1.b1"), shapes(), null);
  if (!drawn) throw new Error("the fixture story draws without its river");
  return drawn;
}

function layer(id: string, values: Record<string, number>): MapLayer {
  const body = JSON.parse(readRepo("shared", "region.layer.golden.json")) as MapLayer;
  return { ...body, layer: { ...body.layer, id }, classes: NATIONAL_CLASSES, values };
}

function shownValues(drawn: StoryGeometry, valueAt: (position: number) => number): Record<string, number> {
  const far = shapes().filter((shape) => !drawn.context.includes(shape)).slice(0, 40);
  return Object.fromEntries([
    ...drawn.context.map((shape, position) => [String(shape.lgd), valueAt(position)]),
    ...far.map((shape, position) => [String(shape.lgd), 1000 + position * 75])
  ]);
}

test("a chosen layer spreads the districts the story shows over its palette's ramp, lowest first, so rising and falling values draw two different maps", () => {
  const drawn = geometry();
  const count = drawn.context.length;
  expect(count).toBeGreaterThanOrEqual(5);
  const rising = layer("annual-precipitation", shownValues(drawn, (position) => 10 + position * 5));
  const falling = layer("annual-precipitation", shownValues(drawn, (position) => 10 + (count - 1 - position) * 5));
  const tones = (chosen: MapLayer) => drawn.context.map((shape) => storyLayerFill(drawn, chosen)(shape));
  expect(new Set(tones(rising)).size).toBe(storyLayerInView(drawn, rising)?.classes.length);
  expect(tones(rising)).not.toEqual(tones(falling));
  expect(tones(rising)[0]).toBe("fill-[var(--rain-1)]");
  expect(tones(rising)[count - 1]).toBe("fill-[var(--rain-6)]");
  expect(tones(falling)[0]).toBe("fill-[var(--rain-6)]");
  expect(drawn.context.some((shape) => shape.lgd === KACHCHH)).toBe(true);
});

test("a story layer takes the palette /map gives it: rain for rainfall, the pH ramp's fixed breaks for soil pH, density for a variable no palette names", () => {
  const drawn = geometry();
  const values = shownValues(drawn, (position) => 10 + position * 5);
  const rain = layer("annual-precipitation", values);
  const soil = layer("soil-ph-0-5cm", shownValues(drawn, (position) => 5 + (position % 5)));
  const other = layer("unnamed-layer", values);
  other.layer = { ...other.layer, variable: "unnamed_measure" };
  const tones = (chosen: MapLayer) => drawn.context.map((shape) => storyLayerFill(drawn, chosen)(shape));
  expect(tones(rain).every((tone) => tone !== null && tone.includes("--rain-"))).toBe(true);
  expect(tones(other).every((tone) => tone !== null && tone.includes("--density-"))).toBe(true);
  expect(tones(soil).slice(0, 5)).toEqual(["fill-[var(--ph-1)]", "fill-[var(--ph-2)]", "fill-[var(--ph-3)]", "fill-[var(--ph-4)]", "fill-[var(--ph-5)]"]);
});

test("districts are classed over the values on the map, by inclusive quantiles cut to three figures, as the server classes India", () => {
  expect(viewClasses([10, 1, 2, 3, 4, 5, 6, 7, 8, 9])).toEqual([
    { min: 1, max: 2.8 },
    { min: 2.8, max: 4.6 },
    { min: 4.6, max: 6.4 },
    { min: 6.4, max: 8.2 },
    { min: 8.2, max: 10 }
  ]);
  expect(viewClasses([40, 10, 30, 20])).toEqual([
    { min: 10, max: 17.5 },
    { min: 17.5, max: 25 },
    { min: 25, max: 32.5 },
    { min: 32.5, max: 40 }
  ]);
  expect(viewClasses([3, 3, 8])).toEqual([{ min: 3, max: 8 }]);
  expect(viewClasses([7])).toEqual([{ min: 7, max: 7 }]);
  expect(viewClasses([1234.5, 1, 2])).toEqual([
    { min: 1, max: 1.67 },
    { min: 1.67, max: 413 },
    { min: 413, max: 1234.5 }
  ]);
  expect(() => viewClasses([])).toThrow(RangeError);
});

test("a layer in view keeps only the districts drawn, and none drawn is no layer", () => {
  const body = layer("soil-ph-0-5cm", { "449": 8.1, "441": 7.6, "999": 6.0 });
  expect(layerInView(body, [449, 441, 449, 5])).toMatchObject({ values: { "449": 8.1, "441": 7.6 }, classes: [{ min: 7.6, max: 7.85 }, { min: 7.85, max: 8.1 }] });
  expect(layerInView(body, [5, 6])).toBeNull();
  const drawn = geometry();
  const far = layer("elevation", { "999999": 4 });
  expect(storyLayerInView(drawn, far)).toBeNull();
  expect(new Set(drawn.context.map((shape) => storyLayerFill(drawn, far)(shape)))).toEqual(new Set([NO_DATA_TONE]));
});

function chosenStory(data: MapLayer | null): StoryLayer {
  return { offered: [], chosen: data ? data.layer.id : null, choose: () => undefined, layer: { data, failure: null, retry: () => undefined } };
}

test("a chosen layer reads out each story district's value and a legend scoped to the districts on the map", () => {
  const drawn = geometry();
  const block = phaseBBlock("region_story", "s1.b1");
  const national = layer("annual-precipitation", shownValues(drawn, (position) => 300 + position * 10));
  national.layer = { ...national.layer, title: "Annual precipitation", unit: "mm/year" };
  const shown = storyLayerInView(drawn, national);
  if (!shown) throw new Error("the fixture layer has values on the map");
  const shapes = { data: drawn.context, failure: null, retry: () => undefined };
  const html = renderToStaticMarkup(createElement(StoryLayerReadout, { block, story: chosenStory(national), shown, shapes }));
  const kachchh = drawn.context.findIndex((shape) => shape.lgd === KACHCHH);
  expect(shownText(html)).toContain("Kachchh");
  expect(html).toContain(`${300 + kachchh * 10}`);
  expect(attribute(html, "choropleth-scope", "data-testid")).toHaveLength(1);
  expect(html).toContain("var(--rain-1)");
  expect(html).not.toContain("var(--density-");
  expect(shownText(html)).toContain(storyScopeNote(shown));
  expect(storyScopeNote(shown)).toBe(`Shades compare the ${drawn.context.length} districts on this map.`);
  expect(renderToStaticMarkup(createElement(StoryLayerReadout, { block, story: chosenStory(null), shown: null, shapes }))).toBe("");
  const empty = renderToStaticMarkup(createElement(StoryLayerReadout, { block, story: chosenStory(layer("elevation", { "999999": 4 })), shown: null, shapes }));
  expect(attribute(empty, "story-layer-empty", "data-testid")).toHaveLength(1);
});

test("the India locator marks the story's districts and its frame on the whole of India, named for screen readers", () => {
  const drawn = geometry();
  const block = phaseBBlock("region_story", "s1.b1");
  const label = locatorLabel(block.districts);
  expect(label).toBe("Where in India: Kachchh, Gujarat");
  expect(locatorLabel([])).toBe("Where in India");
  const marked = [...drawn.districts.values()].map((district) => district.shape);
  const html = renderToStaticMarkup(createElement(IndiaLocator, { marked, frame: drawn.view, label }));
  expect(html).toContain('role="img"');
  expect(html).toContain(`aria-label="${label}"`);
  expect(attribute(html, "india-locator-mark", "data-testid")).toHaveLength(marked.length);
  expect(attribute(html, "india-locator-frame", "width")).toEqual([String(drawn.view.width)]);
  expect(html).toMatch(/viewBox="0 0 1000 /);
  expect(html).not.toMatch(/https?:\/\//);
  const stage = renderToStaticMarkup(
    createElement(RiverStage, {
      geometry: drawn,
      flow: { progress: motionValue(1), moving: false, passed: ALL_PASSED, replay: null },
      fillOf: (shape: DistrictShape) => storyTone(drawn, shape.lgd, ALL_PASSED),
      focus: { district: null, stretch: false, reached: [], onStep: () => undefined },
      summary: "Kachchh.",
      inset: createElement(IndiaLocator, { marked, frame: drawn.view, label })
    })
  );
  expect(stage.indexOf("india-locator")).toBeGreaterThan(stage.indexOf("river-stage"));
});
