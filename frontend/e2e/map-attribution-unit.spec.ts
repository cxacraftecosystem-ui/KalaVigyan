import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { AnswerMapSource } from "@/components/answer/place/AnswerMapSource";
import { NATURAL_EARTH_CREDIT } from "@/components/map/basemap";
import { craftsMapSource } from "@/components/map/CraftsMapSection";
import { BOUNDARY_ATTRIBUTION, CRAFT_LIST_COUNTS, MapSourceLine, OSM_COPYRIGHT_URL, OSM_CREDIT } from "@/components/map/MapSourceLine";
import { mapLayerListShape } from "@/lib/regionContract";
import { parseShape } from "@/lib/shape";

const LAYERS = parseShape(mapLayerListShape, JSON.parse(readFileSync(join(__dirname, "..", "..", "shared", "region.layers.golden.json"), "utf8")));
const OUTLINE = "External boundaries of India as depicted by Survey of India.";
const DISTRICTS = "External boundaries of India as depicted by Survey of India. District boundaries are indicative.";

function words(html: string): string {
  return html.replace(/<!-- -->/g, "").replace(/<[^>]+>/g, "").replace(/\s+/g, " ").trim();
}

test("the layer list serves both captions: the outline alone for maps of states or places, the district line too for district maps", () => {
  expect(LAYERS.outlineCaption).toBe(OUTLINE);
  expect(LAYERS.boundary.caption).toBe(DISTRICTS);
});

test("a map's source line prints the caption the server gave, then the credits, with the OpenStreetMap link", () => {
  const states = renderToStaticMarkup(createElement(MapSourceLine, { caption: LAYERS.outlineCaption, counts: true }));
  expect(words(states)).toBe(`${OUTLINE} ${NATURAL_EARTH_CREDIT} ${BOUNDARY_ATTRIBUTION} ${CRAFT_LIST_COUNTS} ${OSM_CREDIT}`.replace(/\s+/g, " "));
  expect(states).toContain(`href="${OSM_COPYRIGHT_URL}"`);
  const districts = renderToStaticMarkup(createElement(MapSourceLine, { caption: LAYERS.boundary.caption, counts: false }));
  expect(words(districts)).toBe(`${DISTRICTS} ${NATURAL_EARTH_CREDIT} ${BOUNDARY_ATTRIBUTION} ${OSM_CREDIT}`.replace(/\s+/g, " "));
});

test("until the layer list arrives a map prints its credits and no caption of its own making", () => {
  const waiting = words(renderToStaticMarkup(createElement(MapSourceLine, { caption: null, counts: false })));
  expect(waiting).toBe(`${NATURAL_EARTH_CREDIT} ${BOUNDARY_ATTRIBUTION} ${OSM_CREDIT}`.replace(/\s+/g, " "));
  expect(waiting).not.toContain("Survey of India");
  expect(words(renderToStaticMarkup(createElement(AnswerMapSource, { boundary: null, caption: null, coordinates: true })))).not.toContain("Survey of India");
});

test("the landing map's caption is the board's: the outline, Natural Earth and the craft list counts", () => {
  expect(craftsMapSource(OUTLINE)).toBe(`${OUTLINE} ${NATURAL_EARTH_CREDIT} ${CRAFT_LIST_COUNTS}`);
  expect(craftsMapSource(null)).toBe(`${NATURAL_EARTH_CREDIT} ${CRAFT_LIST_COUNTS}`);
});
