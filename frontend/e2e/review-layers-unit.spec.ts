import { expect, test } from "@playwright/test";

import type { LayerReview } from "@/lib/layerReviewContract";
import { boundsLine, layerClassLabel, layerTerms, simplificationLine, sizeLine, valueLine } from "@/lib/layerReviewView";
import { reviewQueuePageShape, type LayerItem } from "@/lib/reviewQueueContract";
import { KIND_LABELS, KIND_NOUNS, kindTabs } from "@/lib/reviewQueueView";
import { parseShape } from "@/lib/shape";

const DATASET = {
  code: "KV_TEST_CLAY_PITS",
  title: "Clay pits of Kachchh",
  publisher: "A state geological survey",
  edition: "2025",
  period: "2025",
  nativeResolution: "point sites",
  licence: "CC BY 4.0",
  licenceUrl: "https://creativecommons.org/licenses/by/4.0/",
  attribution: "A state geological survey",
  citation: "A state geological survey (2025). Clay pits of Kachchh.",
  url: "https://example.org/clay-pits.geojson",
  version: "1",
  crs: "EPSG:4326",
  redistributable: true,
  landingUrl: "https://example.org/clay-pits",
  readOn: "2026-11-23",
  sha256: "a".repeat(64)
};

const PLAN = {
  layerClass: "POINT_SITES",
  simplifiedTo: null,
  valueProperty: "pits",
  variable: "clay pits recorded at the site",
  unit: "count",
  method: "counted from the survey's site records"
};

const REVIEW = {
  dataset: DATASET,
  plan: PLAN,
  geometry: "POINT",
  features: 2,
  byteSize: 2048,
  bounds: { west: 69.75, south: 22.5, east: 72.5, north: 23.25 },
  checks: ["Its licence is open and lets anyone redistribute the data", "Points, never simplified"]
};

const ITEM = {
  id: "00000000-0000-4000-8000-000000000031",
  origin: "CONTRIBUTION",
  submittedAt: "2026-11-23T09:00:00Z",
  craft: null,
  proposer: null,
  kind: "LAYERS",
  layer: REVIEW
};

const PAGE = {
  schemaVersion: 1,
  kinds: ["FACTS", "TESTIMONY", "IMAGES", "COMPONENTS", "LAYOUTS", "STRUCTURE", "LAYERS"],
  counts: { FACTS: 0, TESTIMONY: 0, IMAGES: 0, COMPONENTS: 0, LAYOUTS: 0, STRUCTURE: 0, LAYERS: 1 },
  total: 1,
  items: [ITEM],
  nextCursor: null
};

test("a map layer proposal from the server is read with its record, plan and bounds", () => {
  const page = parseShape(reviewQueuePageShape, PAGE);
  const item = page.items[0] as LayerItem;
  expect([item.kind, item.craft, item.layer.geometry, item.layer.dataset.code]).toEqual(["LAYERS", null, "POINT", "KV_TEST_CLAY_PITS"]);
  const wrong = { ...ITEM, layer: { ...REVIEW, geometry: "VOLUME" } };
  expect(() => parseShape(reviewQueuePageShape, { ...PAGE, items: [wrong] })).toThrow();
  const missing = { ...ITEM, layer: { ...REVIEW, bounds: { west: 69.75, south: 22.5, east: 72.5 } } };
  expect(() => parseShape(reviewQueuePageShape, { ...PAGE, items: [missing] })).toThrow();
});

test("the map layers tab carries its count and its own names", () => {
  expect(kindTabs(parseShape(reviewQueuePageShape, PAGE)).at(-1)?.label).toBe("Map layers (1)");
  expect([KIND_LABELS.LAYERS, KIND_NOUNS.LAYERS]).toEqual(["Map layers", "Map layer proposal"]);
});

test("a layer's lines say its class, simplification, values, size and span", () => {
  const review = REVIEW as LayerReview;
  expect(layerClassLabel("POINT_SITES")).toBe("Point sites");
  expect(layerClassLabel("SALT_PANS")).toBe("Salt pans");
  expect(simplificationLine(review.plan)).toBe("Not simplified");
  expect(simplificationLine({ ...review.plan, simplifiedTo: 0.008 })).toBe("Simplified to 0.008 degree");
  expect(valueLine(review.plan)).toBe("clay pits recorded at the site, in count (property pits)");
  expect(valueLine({ ...review.plan, valueProperty: null })).toBe("Geometry alone");
  expect(sizeLine(review)).toBe("2 features, 2.0 KB");
  expect(boundsLine(review.bounds)).toBe("69.75° to 72.5° east, 22.5° to 23.25° north");
});

test("a layer lists its terms in reading order and its edition with its version", () => {
  const terms = layerTerms(REVIEW as LayerReview);
  expect(terms.map((term) => term.term)).toEqual([
    "Layer",
    "Geometry",
    "Simplification",
    "Values",
    "Method",
    "File",
    "Spans",
    "Edition",
    "Period",
    "Licence",
    "Attribution"
  ]);
  expect(terms.find((term) => term.term === "Edition")?.value).toBe("2025, version 1");
  expect(terms.find((term) => term.term === "Geometry")?.value).toBe("Points");
});
