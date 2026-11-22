import { expect, test } from "@playwright/test";
import { createElement } from "react";

import type { CitationLookup } from "@/components/answer/CitationContext";
import { ExplainerSectionView } from "@/components/answer/ExplainerSectionView";
import { ExpertPanel } from "@/components/answer/experts/ExpertPanel";
import type { ExplainerBlock } from "@/lib/explainerContract";
import type { ExpertViewBlock } from "@/lib/explainerExperts";
import type { SectionView } from "@/lib/explainerState";
import { blockSentences, explainerSourceNumbers } from "@/lib/explainerView";
import { agreementText, sectionRuns } from "@/lib/expertPanel";

import { attribute, FIXED_WIDE_WIDTH, gridTracks, SHRINKABLE_TRACK, shownText, withReading } from "./explainerRender";
import { phaseBBlock } from "./phaseBFixture";

const historian = () => phaseBBlock("expert_view", "s5.b1");
const anthropologist = () => phaseBBlock("expert_view", "s5.b2");
const GI_JOURNAL = "d0f53ee9-4b97-5df7-a367-686957bdb7c8";
const KHAMIR_PART_1 = "5de57c2d-f9af-57c3-8a42-3b624976dbb8";
const AJRAKH_INTRODUCTION = "56c24809-a5fd-5d90-b6db-e55d7be09c07";

function differCard(html: string): string {
  const start = html.indexOf('data-testid="experts-differ"');
  if (start < 0) throw new Error("no Experts differ card");
  return html.slice(start);
}

function section(blocks: readonly unknown[]): SectionView {
  return { id: "s5", discipline: "HISTORY", title: "History", order: 1, state: "READY", searched: null, blocks: blocks as ExplainerBlock[] };
}

test("a section's expert views form one panel where the first one stands, and every other block stands alone", () => {
  const prose = { id: "s5.b9", kind: "prose", version: 1, reuse: null, sentences: [] };
  const images = { ...prose, id: "s5.b8", kind: "images" };
  const later = { ...historian(), id: "s5.b4", seat: "ECONOMIST" as const };
  const runs = sectionRuns(section([prose, historian(), anthropologist(), images, later]).blocks);
  expect(runs.map((run) => (run.kind === "experts" ? `experts:${run.key}:${run.views.map((view) => view.seat).join(",")}` : `block:${run.block.id}`))).toEqual([
    "block:s5.b9",
    "experts:s5.b1:HISTORIAN,ANTHROPOLOGIST,ECONOMIST",
    "block:s5.b8"
  ]);
});

test("the panel draws each seat's cited take and one Experts differ card with both seats' citations side by side", () => {
  const lookup: CitationLookup = {
    numbers: new Map([
      [AJRAKH_INTRODUCTION, 1],
      [GI_JOURNAL, 2],
      [KHAMIR_PART_1, 3]
    ]),
    sourcesById: new Map()
  };
  const views = [historian(), anthropologist()];
  const html = withReading(createElement(ExpertPanel, { views, reduce: true }), lookup);
  expect(attribute(html, "expert-seat", "data-seat")).toEqual(["HISTORIAN", "ANTHROPOLOGIST"]);
  expect(html).toContain(">Historian<");
  expect(html).toContain(">Anthropologist<");
  for (const view of views) for (const sentence of view.take) expect(shownText(html)).toContain(sentence.text);
  expect(attribute(html, "experts-differ", "data-testid")).toHaveLength(1);
  const card = differCard(html);
  expect(card).toContain("Experts differ");
  expect(attribute(card, "experts-differ-side", "data-seat")).toEqual(["HISTORIAN", "ANTHROPOLOGIST"]);
  expect(shownText(card)).toContain(historian().differs[0].thisView.text);
  expect(shownText(card)).toContain(anthropologist().differs[0].thisView.text);
  expect(attribute(card, "citation-chip", "data-numbers")).toEqual(["2", "3"]);
});

test("one seat alone, or a difference only one seat states, draws no Experts differ card", () => {
  expect(withReading(createElement(ExpertPanel, { views: [historian()], reduce: true }))).not.toContain('data-testid="experts-differ"');
  const silent = { ...anthropologist(), differs: [] };
  expect(withReading(createElement(ExpertPanel, { views: [historian(), silent], reduce: true }))).not.toContain('data-testid="experts-differ"');
});

test("agreements are named under the seat and its sentences join the answer's one numbering", () => {
  expect(agreementText({ agreesWith: ["CHEMIST", "BOTANIST"] })).toBe("Agrees with Chemist and Botanist");
  expect(agreementText({ agreesWith: [] })).toBeNull();
  const agreeing = { ...historian(), agreesWith: ["ANTHROPOLOGIST" as const] } as ExpertViewBlock;
  expect(withReading(createElement(ExpertPanel, { views: [agreeing], reduce: true }))).toContain("Agrees with Anthropologist");
  expect(blockSentences(historian()).map((sentence) => sentence.id)).toEqual(["s5.b1.1", "s5.b1.2", "s5.b1.3"]);
  expect([...explainerSourceNumbers([section([historian(), anthropologist()])]).keys()]).toEqual([AJRAKH_INTRODUCTION, GI_JOURNAL, KHAMIR_PART_1]);
});

test("a section draws its expert views as one panel inside shrinkable columns", () => {
  const html = withReading(createElement(ExplainerSectionView, { section: section([historian(), anthropologist()]), streaming: false, reduce: true, onActive: () => undefined }));
  expect(attribute(html, "expert-panel", "data-testid")).toHaveLength(1);
  expect(attribute(html, "explainer-block", "data-kind")).toEqual(["expert_view", "expert_view"]);
  const tracks = gridTracks(html);
  expect(tracks.length).toBeGreaterThan(0);
  for (const track of tracks) expect(track).toMatch(SHRINKABLE_TRACK);
  expect(html).not.toMatch(FIXED_WIDE_WIDTH);
});
