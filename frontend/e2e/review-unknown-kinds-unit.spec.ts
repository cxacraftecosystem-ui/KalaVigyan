import { expect, test } from "@playwright/test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { QueueItemView, type QueueHandlers } from "@/components/review/QueueItemView";
import { reviewQueuePageShape } from "@/lib/reviewQueueContract";
import { kindTabs } from "@/lib/reviewQueueView";
import { parseShape } from "@/lib/shape";

const CRAFT = { slug: "Kutch-Ajrakh", name: "Kutch Ajrakh", path: "/crafts/Kutch-Ajrakh" };
const BASE = { origin: "RESEARCH", submittedAt: "2026-11-23T09:00:00Z", craft: CRAFT, proposer: null };
const SOURCE = { title: "Drying printed cloth", url: "https://crafts.example.org/drying", licence: null, reliability: "B", quotes: [{ text: "the printed cloth is dried in the sun", locator: "p. 12" }] };

const STAGE_ITEM = {
  ...BASE,
  id: "00000000-0000-4000-8000-000000000201",
  kind: "STAGES",
  stage: {
    name: "Drying in the sun",
    description: null,
    processes: [{ id: "00000000-0000-4000-8000-000000000202", name: "Process", stages: [{ id: "00000000-0000-4000-8000-000000000203", ordinal: 1, name: "Soaking" }] }],
    facts: [{ id: "00000000-0000-4000-8000-000000000204", text: "The printed cloth is dried in the sun.", sources: [SOURCE] }]
  }
};

const STRUCTURE = {
  kind: "NATIVE_NAME",
  subject: { kind: "craft", slug: "Kutch-Ajrakh" },
  subjectName: "Kutch Ajrakh",
  pageUrl: "/crafts/Kutch-Ajrakh",
  target: null,
  current: null,
  item: { kind: "NATIVE_NAME", text: "Ajrak", language: "sd", script: "Latn" },
  statement: "Printers in the delta call the cloth ajrak, after their word for blue.",
  field: "HISTORY",
  note: null,
  taskKey: null,
  sources: [SOURCE],
  checks: [],
  conflicting: [],
  stale: null
};

const STRUCTURE_ITEM = { ...BASE, origin: "AGENT", id: "00000000-0000-4000-8000-000000000205", kind: "STRUCTURE", structure: STRUCTURE };
const LATER_ITEM = { ...BASE, id: "00000000-0000-4000-8000-000000000206", kind: "LATER_KIND", later: { anything: true } };
const LATER_STRUCTURE = {
  ...STRUCTURE_ITEM,
  id: "00000000-0000-4000-8000-000000000207",
  structure: { ...STRUCTURE, kind: "LATER_STRUCTURE", item: { kind: "LATER_STRUCTURE", words: "a later entry" } }
};

const PAGE = {
  schemaVersion: 1,
  kinds: ["FACTS", "STRUCTURE", "LATER_KIND", "STAGES"],
  counts: { FACTS: 0, STRUCTURE: 2, LATER_KIND: 1, STAGES: 1 },
  total: 4,
  items: [LATER_ITEM, STRUCTURE_ITEM, LATER_STRUCTURE, STAGE_ITEM],
  nextCursor: null
};

const HANDLERS: QueueHandlers = { decide: async () => null, decidedElsewhere: () => undefined };

test("the live web skips a review kind it does not know and keeps every item it knows", () => {
  const page = parseShape(reviewQueuePageShape, PAGE, "ignore");
  expect(page.kinds).toEqual(["FACTS", "STRUCTURE", "STAGES"]);
  expect(page.items.map((item) => [item.kind, item.id])).toEqual([
    ["STRUCTURE", STRUCTURE_ITEM.id],
    ["STAGES", STAGE_ITEM.id]
  ]);
  expect(kindTabs(page).map((tab) => tab.label)).toEqual(["All (3)", "Facts (0)", "Structure (2)", "Process stages (1)"]);
});

test("a page carrying an unknown kind still renders its known items", () => {
  const page = parseShape(reviewQueuePageShape, PAGE, "ignore");
  const markup = page.items.map((item) => renderToStaticMarkup(createElement(QueueItemView, { item, handlers: HANDLERS }))).join("");
  expect(markup).toContain("Printers in the delta call the cloth ajrak, after their word for blue.");
  expect(markup).toContain("Drying in the sun");
  expect(markup).toContain("The printed cloth is dried in the sun.");
  expect(markup).not.toContain("a later entry");
});

test("the unit specs and the development server still refuse an unknown kind, so the drift is caught", () => {
  expect(() => parseShape(reviewQueuePageShape, PAGE, "refuse")).toThrow();
  expect(() => parseShape(reviewQueuePageShape, { ...PAGE, kinds: ["FACTS"], items: [LATER_STRUCTURE] }, "refuse")).toThrow();
  const known = { ...PAGE, kinds: ["FACTS", "STRUCTURE", "STAGES"], items: [STRUCTURE_ITEM, STAGE_ITEM] };
  expect(parseShape(reviewQueuePageShape, known, "refuse").items).toHaveLength(2);
});
