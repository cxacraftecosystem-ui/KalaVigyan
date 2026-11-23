import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { StagedItemResult } from "@/components/review/StagedItemRow";
import { parseShape, ShapeError } from "@/lib/shape";
import {
  isKnownStagedItem,
  parseStagedBatch,
  parseStagedBatchList,
  STAGED_KINDS,
  stagedBatchListShape,
  stagedBatchPath,
  type StagedBatchList,
  type StagedItemView
} from "@/lib/stagedReviewContract";
import {
  batchHeading,
  batchTally,
  confirmBody,
  confirmedItemOf,
  confirmProblem,
  decisionShown,
  draftOf,
  outcomeLine,
  reasonProblem,
  sourceProblem,
  STAGED_KIND_ACTIONS,
  withBatch,
  withDraft,
  type SourceDraft
} from "@/lib/stagedReviewView";

const SHARED = join(__dirname, "..", "..", "shared");
const BATCH_ID = "6f1c2a4e-8d3b-4c5a-9e7f-0a1b2c3d4e01";
const FACT_ITEM = "6f1c2a4e-8d3b-4c5a-9e7f-0a1b2c3d4e11";
const SOURCE_ITEM = "6f1c2a4e-8d3b-4c5a-9e7f-0a1b2c3d4e12";
const BLANK_SOURCE: SourceDraft = { title: "", authors: "", year: "", containerTitle: "", kind: "" };

const golden = (): StagedBatchList => JSON.parse(readFileSync(join(SHARED, "review.staged.golden.json"), "utf8")) as StagedBatchList;
const items = (): StagedItemView[] => golden().batches[0].items;

function withItems(extra: unknown[]): unknown {
  const list = golden();
  return { ...list, batches: [{ ...list.batches[0], items: [...extra, ...list.batches[0].items] }] };
}

test("the staged batches parse exactly as the backend writes them", () => {
  const list = parseStagedBatchList(golden());
  expect(list).toEqual(golden());
  expect(list.batches).toHaveLength(1);
  expect(list.batches[0].items.map((item) => item.decision.kind)).toEqual(["FACTS", "SOURCES", "SOURCES_DIFFER"]);
  expect(list.batches[0].items.map((item) => item.state)).toEqual(["STAGED", "STAGED", "REFUSED"]);
});

test("a staged list off its contract is refused", () => {
  const [first] = items();
  expect(() => parseStagedBatchList({ ...golden(), schemaVersion: 2 })).toThrow(ShapeError);
  expect(() => parseStagedBatchList({ ...golden(), batches: [{ ...golden().batches[0], status: "PENDING" }] })).toThrow(ShapeError);
  expect(() => parseStagedBatchList({ ...golden(), batches: [{ ...golden().batches[0], createdAt: "yesterday" }] })).toThrow(ShapeError);
  expect(() => parseStagedBatchList(withItems([{ ...first, position: -1 }]))).toThrow(ShapeError);
  expect(() => parseStagedBatchList(withItems([{ ...first, email: "x@example.org" }]))).toThrow(ShapeError);
});

test("the live web leaves out a staged item of a kind it does not know and keeps the rest", () => {
  const [first, second] = items();
  const laterKind = { ...first, id: "6f1c2a4e-8d3b-4c5a-9e7f-0a1b2c3d4e19", decision: { ...first.decision, kind: "LATER_KIND" } };
  const laterSource = { ...second, id: "6f1c2a4e-8d3b-4c5a-9e7f-0a1b2c3d4e18", decision: { ...second.decision, source: { kind: "PREPRINT" } } };
  const raw = withItems([laterKind, laterSource]);
  const live = parseShape(stagedBatchListShape, raw, "ignore");
  expect(live.batches[0].items.map((item) => item.id)).toEqual(items().map((item) => item.id));
  expect(() => parseShape(stagedBatchListShape, raw, "refuse")).toThrow(ShapeError);
  expect(() => parseShape(stagedBatchListShape, withItems([laterKind]), "refuse")).toThrow(ShapeError);
});

test("an item is known only when its kind, action and source kind are all known", () => {
  const [first, second] = items();
  expect(isKnownStagedItem(first)).toBe(true);
  expect(isKnownStagedItem(second)).toBe(true);
  expect(isKnownStagedItem({ ...first, decision: { ...first.decision, kind: "LATER_KIND" } })).toBe(false);
  expect(isKnownStagedItem({ ...first, decision: { ...first.decision, action: "publish" } })).toBe(false);
  expect(isKnownStagedItem({ ...second, decision: { ...second.decision, source: { kind: "PREPRINT" } } })).toBe(false);
  expect(isKnownStagedItem({ ...first, applied: { ...first.decision, kind: "LATER_KIND" } })).toBe(false);
  expect(isKnownStagedItem(null)).toBe(true);
});

test("each kind offers only the actions the backend allows it", () => {
  const pair = ["approve", "reject"];
  expect(STAGED_KIND_ACTIONS).toEqual({
    FACTS: ["approve", "raise", "reject", "retract"],
    COMPONENTS: pair,
    LAYOUTS: pair,
    STRUCTURE: pair,
    READINGS: pair,
    LAYERS: pair,
    STAGES: pair,
    SOURCES: ["correct"],
    SOURCES_DIFFER: ["clear"]
  });
  expect(Object.keys(STAGED_KIND_ACTIONS).sort()).toEqual([...STAGED_KINDS].sort());
});

test("a draft starts as the staged decision, selected", () => {
  const [fact, source] = items().map(draftOf);
  expect(fact).toEqual({
    id: FACT_ITEM,
    kind: "FACTS",
    selected: true,
    action: "approve",
    reason: "Both quotes state the reduction in the vat.",
    fileUnder: "craft:Kutch-Ajrakh",
    source: null
  });
  expect(source.source).toEqual({
    title: "Sanganer dyes and their effluents",
    authors: "A. Sharma\nR. Gupta",
    year: "2007",
    containerTitle: "Journal of Environmental Biology",
    kind: "PAPER"
  });
});

test("an unchanged item is confirmed as it was staged", () => {
  for (const item of items()) {
    const { action, reason, craft, family, source } = item.decision;
    expect(confirmedItemOf(draftOf(item))).toEqual({ id: item.id, action, reason, craft, family, source });
  }
});

test("the confirm body keeps each changed item's id, drops nothing and skips the unselected", () => {
  const [fact, source, differ] = items().map(draftOf);
  const refiled = { ...fact, fileUnder: "family:textiles", reason: "  Both quotes state it; it belongs to the family.  " };
  const corrected = { ...source, source: { ...BLANK_SOURCE, ...source.source, year: "2008", authors: "A. Sharma\n\n R. Gupta \n" } };
  const body = confirmBody([refiled, corrected, { ...differ, selected: false }]);
  expect(body).toEqual({
    items: [
      { id: FACT_ITEM, action: "approve", reason: "Both quotes state it; it belongs to the family.", craft: null, family: "textiles", source: null },
      {
        id: SOURCE_ITEM,
        action: "correct",
        reason: "The first page names the journal and the issue year.",
        craft: null,
        family: null,
        source: { title: "Sanganer dyes and their effluents", authors: ["A. Sharma", "R. Gupta"], year: 2008, containerTitle: "Journal of Environmental Biology", kind: "PAPER" }
      }
    ]
  });
  expect(body.items.map((item) => Object.keys(item).sort())).toEqual([0, 1].map(() => ["action", "craft", "family", "id", "reason", "source"]));
});

test("a fact turned away from approval is filed nowhere", () => {
  const [fact] = items().map(draftOf);
  expect(confirmedItemOf({ ...fact, action: "reject" })).toMatchObject({ action: "reject", craft: null, family: null });
  expect(confirmedItemOf({ ...fact, fileUnder: "" })).toMatchObject({ craft: null, family: null });
});

test("a draft's problems are found before it is sent", () => {
  expect(reasonProblem("Too short")).toBe("Give the reason in at least 12 characters.");
  expect(reasonProblem("twelve chars")).toBeNull();
  expect(reasonProblem("x".repeat(501))).toBe("Keep the reason to 500 characters.");
  expect(sourceProblem(BLANK_SOURCE)).toBe("Give at least one corrected field.");
  expect(sourceProblem({ ...BLANK_SOURCE, year: "0999" })).toBe("Give the year in four digits, from 1000 to 2100.");
  expect(sourceProblem({ ...BLANK_SOURCE, year: "207" })).toBe("Give the year in four digits, from 1000 to 2100.");
  expect(sourceProblem({ ...BLANK_SOURCE, year: "2007" })).toBeNull();
  const [fact, source] = items().map(draftOf);
  expect(confirmProblem([{ ...fact, selected: false }])).toBe("Select at least one item to confirm.");
  expect(confirmProblem([fact, { ...source, reason: "short" }])).toBe("Correct the items marked above, then confirm.");
  expect(confirmProblem([fact, { ...source, reason: "short", selected: false }])).toBeNull();
});

test("a batch is headed by its client and proposer, and a decided batch is tallied", () => {
  const batch = golden().batches[0];
  expect(batchHeading(batch)).toBe("Proposed through Claude by Admin Reviewer");
  expect(batchHeading({ ...batch, proposedBy: null })).toBe("Proposed through Claude");
  expect(batchTally(batch)).toBe("0 applied · 1 refused · 0 skipped");
  expect(stagedBatchPath(BATCH_ID, "confirm")).toBe(`/review-queue/staged/${BATCH_ID}/confirm`);
});

test("each item's outcome says what happened to it", () => {
  const [fact, , differ] = items();
  expect(outcomeLine(fact)).toBeNull();
  expect(outcomeLine(differ)).toBe("This fact is not marked as one whose sources differ.");
  expect(outcomeLine({ ...fact, state: "APPLIED" })).toBe("Applied as proposed.");
  expect(outcomeLine({ ...fact, state: "APPLIED", applied: fact.decision })).toBe("Applied as you changed it.");
  expect(outcomeLine({ ...fact, state: "SKIPPED" })).toBe("Not applied, so nothing changed.");
  expect(decisionShown(differ).reason).toBe("The two values are for different stages, so both hold.");
  const markup = renderToStaticMarkup(createElement(StagedItemResult, { item: differ }));
  expect(markup).toContain("Refused");
  expect(markup).toContain("This fact is not marked as one whose sources differ.");
  expect(markup).toContain("Clear the mark");
});

test("a confirmed batch replaces the open one, and an edited draft replaces its own", () => {
  const batch = golden().batches[0];
  const confirmed = parseStagedBatch({
    ...batch,
    status: "CONFIRMED",
    decidedBy: "Admin Reviewer",
    decidedAt: "2026-11-23T07:00:00Z",
    refresh: "Refreshing the 2 pages these decisions touched now.",
    items: batch.items.map((item) => ({ ...item, state: "APPLIED", outcome: null }))
  });
  expect(withBatch([batch], confirmed)).toEqual([confirmed]);
  expect(batchTally(confirmed)).toBe("3 applied · 0 refused · 0 skipped");
  const drafts = items().map(draftOf);
  const edited = withDraft(drafts, { ...drafts[1], selected: false });
  expect(edited.map((draft) => draft.selected)).toEqual([true, false, true]);
});
