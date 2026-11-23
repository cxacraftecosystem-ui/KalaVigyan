import { expect, test } from "@playwright/test";

import { envelopeLine, rangeLine, READING_ACTIONS, readingLine, readingTitle, stageLine } from "@/lib/readingReviewView";
import { reviewQueuePageShape, type ReadingItem } from "@/lib/reviewQueueContract";
import { KIND_LABELS, KIND_NOUNS, kindTabs } from "@/lib/reviewQueueView";
import { parseShape } from "@/lib/shape";

const READING = {
  stated: "130 °C",
  quantity: "TEMPERATURE",
  unit: "°C",
  min: 130,
  max: 130,
  envelopeMin: 20,
  envelopeMax: 100,
  condition: "Bath temperature",
  stage: "Madder bath",
  stageType: "DYE",
  claimId: "00000000-0000-4000-8000-000000000031",
  statement: "The madder bath is boiled at 130 °C for an hour.",
  sources: [
    { title: "Madder baths", url: "https://papers.example.org/madder", licence: "CC-BY-4.0", reliability: "B", quotes: [{ text: "boiled at 130 °C", locator: "p. 2" }] }
  ]
};

const ITEM = {
  id: "00000000-0000-4000-8000-000000000032",
  origin: "RESEARCH",
  submittedAt: "2026-11-23T09:00:00Z",
  craft: { slug: "Kutch-Ajrakh", name: "Kutch Ajrakh", path: "/crafts/Kutch-Ajrakh" },
  proposer: null,
  kind: "READINGS",
  reading: READING
};

const PAGE = {
  schemaVersion: 1,
  kinds: ["FACTS", "STRUCTURE", "READINGS"],
  counts: { FACTS: 0, STRUCTURE: 0, READINGS: 1 },
  total: 1,
  items: [ITEM],
  nextCursor: null
};

test("a reading outside its range is read from the server with its stage, its range and its sources", () => {
  const item = parseShape(reviewQueuePageShape, PAGE).items[0] as ReadingItem;
  expect([item.kind, item.reading.stated, item.reading.sources[0].quotes[0].locator]).toEqual(["READINGS", "130 °C", "p. 2"]);
  expect(() => parseShape(reviewQueuePageShape, { ...PAGE, items: [{ ...ITEM, reading: { ...READING, min: "130" } }] })).toThrow();
});

test("in production a kind this page does not know yet is left out of the tabs and the items", () => {
  const later = { ...PAGE, kinds: [...PAGE.kinds, "LATER"], counts: { ...PAGE.counts, LATER: 2 }, items: [{ kind: "LATER", id: "x" }, ITEM] };
  expect(() => parseShape(reviewQueuePageShape, later)).toThrow();
  const page = parseShape(reviewQueuePageShape, later, "ignore");
  expect(page.kinds).toEqual(["FACTS", "STRUCTURE", "READINGS"]);
  expect(page.items.map((each) => each.kind)).toEqual(["READINGS"]);
});

test("the readings tab carries its count and its own names", () => {
  expect(kindTabs(parseShape(reviewQueuePageShape, PAGE)).at(-1)?.label).toBe("Readings (1)");
  expect([KIND_LABELS.READINGS, KIND_NOUNS.READINGS]).toEqual(["Readings", "Reading outside its range"]);
  expect(READING_ACTIONS).toEqual(["approve", "reject"]);
});

test("a reading and its stage's range are written in the unit the page shows", () => {
  const review = parseShape(reviewQueuePageShape, PAGE).items[0] as ReadingItem;
  expect([readingTitle(review.reading), stageLine(review.reading)]).toEqual(["Bath temperature: 130 °C", "Madder bath, a dye stage"]);
  expect([readingLine(review.reading), envelopeLine(review.reading)]).toEqual(["130 °C", "20 to 100 °C"]);
  expect(rangeLine(null, 4, "h")).toBe("up to 4 h");
  expect(rangeLine(3, null, "h")).toBe("at least 3 h");
  expect(rangeLine(2, 12, "pH")).toBe("pH 2 to 12");
  expect(rangeLine(13, 13, "pH")).toBe("pH 13");
});
