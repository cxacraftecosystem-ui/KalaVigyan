import { expect, test } from "@playwright/test";
import { createElement } from "react";

import { TimelineMapView } from "@/components/answer/journey/TimelineMap";
import { INDIA_BOUNDS } from "@/components/map/indiaBounds";
import { BLOCK_SHAPES } from "@/lib/explainerContract";
import type { TimelineMapBlock } from "@/lib/explainerPlay";
import { blockSentences } from "@/lib/explainerView";
import { parseShape, ShapeError } from "@/lib/shape";
import { placedPlaces } from "@/lib/timelineView";

import { attribute, shownText, withApp } from "./explainerRender";
import { readRepo } from "./phaseBFixture";
import { phaseCBlock } from "./playFixture";

type BlocksFixture = { sections: { blocks: unknown[] }[] };

const GOLDEN = JSON.parse(readRepo("shared", "explainer.timeline-undated.golden.json")) as BlocksFixture;
const DHAMADKA = "Dhamadka is located approximately 50 km east of Bhuj.";

function versionTwo(): TimelineMapBlock {
  return parseShape(BLOCK_SHAPES.timeline_map, structuredClone(GOLDEN.sections[0].blocks[0]));
}

test("version 2 pins a place the district register places, without a Wikidata link", () => {
  const block = versionTwo();
  expect(block.version).toBe(2);
  const kutch = placedPlaces(block, INDIA_BOUNDS).find((place) => place.name === "Kutch");
  expect(kutch).toMatchObject({ wikidataId: null, latitude: 23.25, longitude: 69.67 });
  const html = withApp(createElement(TimelineMapView, { block, at: 2, onChoose: () => undefined }));
  expect(html).not.toContain("wikidata.org/wiki/null");
  expect(() => parseShape(BLOCK_SHAPES.timeline_map, { ...block, version: 3 })).toThrow(ShapeError);
});

test("an undated sentence is listed under the dated entries with the place it names, said once", () => {
  const block = versionTwo();
  const html = withApp(createElement(TimelineMapView, { block, at: 2, onChoose: () => undefined }));
  expect(attribute(html, "timeline-undated-entry", "data-testid")).toHaveLength(1);
  expect(shownText(html)).toContain("Without a date");
  expect(html.split(DHAMADKA).length - 1).toBe(1);
  expect(blockSentences(block).map((sentence) => sentence.id)).toEqual([...block.points, ...block.routes].map((item) => item.sentence.id).concat("s4.b1.5"));
  const plain = phaseCBlock("timeline_map", "s4.b1");
  const unlisted = withApp(createElement(TimelineMapView, { block: plain, at: 2, onChoose: () => undefined }));
  expect(unlisted).not.toContain('data-testid="timeline-undated"');
});
