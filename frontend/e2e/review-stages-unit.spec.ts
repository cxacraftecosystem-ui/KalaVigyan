import { expect, test } from "@playwright/test";

import { decisionBody, reviewQueuePageShape, type StageItem } from "@/lib/reviewQueueContract";
import { KIND_LABELS, KIND_NOUNS, kindTabs } from "@/lib/reviewQueueView";
import { parseShape } from "@/lib/shape";
import { CHOOSE_PLACE, placementOf, placeOptions, placeProblem, stageFactsLine, stageSources } from "@/lib/stageReviewView";

const PROCESS = "00000000-0000-4000-8000-000000000101";
const SOAK = "00000000-0000-4000-8000-000000000102";
const PRINT = "00000000-0000-4000-8000-000000000103";
const QUOTE = { text: "the printed cloth is dried in the sun", locator: "p. 12" };
const SOURCE = { title: "Drying printed cloth", url: "https://crafts.example.org/drying", licence: null, reliability: "B", quotes: [QUOTE] };

const ITEM = {
  id: "00000000-0000-4000-8000-000000000100",
  origin: "RESEARCH",
  submittedAt: "2026-11-23T09:00:00Z",
  craft: { slug: "Kutch-Ajrakh", name: "Kutch Ajrakh", path: "/crafts/Kutch-Ajrakh" },
  proposer: null,
  kind: "STAGES",
  stage: {
    name: "Drying in the sun",
    description: null,
    processes: [
      {
        id: PROCESS,
        name: "Process",
        stages: [
          { id: SOAK, ordinal: 1, name: "Soaking" },
          { id: PRINT, ordinal: 2, name: "Printing" }
        ]
      }
    ],
    facts: [
      { id: "00000000-0000-4000-8000-000000000104", text: "The printed cloth is dried in the sun.", sources: [SOURCE] },
      { id: "00000000-0000-4000-8000-000000000105", text: "Drying fixes the mordant.", sources: [SOURCE, { ...SOURCE, quotes: [{ text: "drying fixes it", locator: null }] }] }
    ]
  }
};

const PAGE = {
  schemaVersion: 1,
  kinds: ["FACTS", "TESTIMONY", "STRUCTURE", "STAGES"],
  counts: { FACTS: 0, TESTIMONY: 0, STRUCTURE: 0, STAGES: 1 },
  total: 1,
  items: [ITEM],
  nextCursor: null
};

test("a process stage answers found is read with its processes and facts, and a stage whose place is not a number is refused", () => {
  const page = parseShape(reviewQueuePageShape, PAGE);
  const item = page.items[0] as StageItem;
  expect([item.kind, item.stage.name, item.stage.processes[0].stages.map((stage) => stage.name)]).toEqual(["STAGES", "Drying in the sun", ["Soaking", "Printing"]]);
  const untold = { ...ITEM, stage: { ...ITEM.stage, processes: [{ id: PROCESS, name: "Process", stages: [{ id: SOAK, ordinal: "1", name: "Soaking" }] }] } };
  expect(() => parseShape(reviewQueuePageShape, { ...PAGE, items: [untold] })).toThrow();
});

test("the stages tab is named and counted with the other kinds", () => {
  const page = parseShape(reviewQueuePageShape, PAGE);
  expect([KIND_LABELS.STAGES, KIND_NOUNS.STAGES]).toEqual(["Process stages", "Process stage"]);
  expect(kindTabs(page).map((tab) => tab.label)).toEqual(["All (1)", "Facts (0)", "Testimony (0)", "Structure (0)", "Process stages (1)"]);
});

test("a stage is placed first or after a numbered stage of its process", () => {
  const item = parseShape(reviewQueuePageShape, PAGE).items[0] as StageItem;
  const options = placeOptions(item.stage);
  expect(options.map((option) => option.label)).toEqual(["First, before Soaking", "After stage 1, Soaking", "After stage 2, Printing"]);
  expect(new Set(options.map((option) => option.group))).toEqual(new Set(["Process"]));
  expect(placementOf(options[0].value)).toEqual({ processId: PROCESS, afterStageId: null });
  expect(placementOf(options[2].value)).toEqual({ processId: PROCESS, afterStageId: PRINT });
  expect(placementOf("")).toBeNull();
});

test("approving needs a place, rejecting does not, and the place travels with the note", () => {
  expect(placeProblem("approve", "")).toBe(CHOOSE_PLACE);
  expect(placeProblem("reject", "")).toBeNull();
  const placement = placementOf(`${PROCESS}|${SOAK}`);
  expect(decisionBody("approve", " Dried before washing. ", placement)).toEqual({ note: "Dried before washing.", processId: PROCESS, afterStageId: SOAK });
  expect(decisionBody("reject", "Not a stage of this craft.", null)).toEqual({ reason: "Not a stage of this craft." });
});

test("the sources of a stage's facts are shown once with every quote", () => {
  const item = parseShape(reviewQueuePageShape, PAGE).items[0] as StageItem;
  const sources = stageSources(item.stage);
  expect(sources.map((source) => [source.title, source.quotes.map((quote) => quote.text)])).toEqual([["Drying printed cloth", ["the printed cloth is dried in the sun", "drying fixes it"]]]);
  expect([stageFactsLine(1), stageFactsLine(2)]).toEqual(["The fact an answer found about it", "The 2 facts answers found about it"]);
});
