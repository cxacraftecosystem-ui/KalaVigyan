import { expect, test } from "@playwright/test";
import { createElement } from "react";

import { BLOCK_RENDERERS } from "@/components/answer/blockRenderers";
import type { CitationLookup } from "@/components/answer/CitationContext";
import { GeneratedExplainerView } from "@/components/answer/play/GeneratedExplainer";
import { WhatIfLab, WhatIfLabView } from "@/components/answer/play/WhatIfLab";
import type { WhatIfBlock } from "@/lib/explainerPlay";
import type { SectionView } from "@/lib/explainerState";
import { blockCitations, blockSentences, blockSourceIds, explainerSourceNumbers } from "@/lib/explainerView";
import { optionNote } from "@/lib/whatIfView";

import { attribute, FIXED_WIDE_WIDTH, gridTracks, SHRINKABLE_TRACK, shownText, withReading } from "./explainerRender";
import { phaseCBlock } from "./playFixture";

const whatIf = () => phaseCBlock("what_if", "s2.b1");
const simulation = () => phaseCBlock("simulation", "s1.b1");
const GI_JOURNAL = "d0f53ee9-4b97-5df7-a367-686957bdb7c8";
const MORDANT_PAPER = "9187df8b-62e3-510a-ba5d-827ec098c84c";
const WATER_SOURCE = "3cb53e85-da56-502e-8333-4fdbbb34b3ae";
const LOOKUP: CitationLookup = { numbers: new Map([[GI_JOURNAL, 1], [MORDANT_PAPER, 2]]), sourcesById: new Map() };

function lab(block: WhatIfBlock, reduce: boolean): string {
  return withReading(createElement(WhatIfLabView, { block, reduce }), LOOKUP);
}

test("the what-if lab is drawn through the renderer registry", () => {
  expect(BLOCK_RENDERERS.what_if).toBe(WhatIfLab);
});

test("every option is offered with its outcome count, and the first one's cited outcomes show", () => {
  const html = lab(whatIf(), false);
  const shown = shownText(html);
  expect(html).toContain(">Red dye<");
  expect(attribute(html, "what-if-option", "aria-pressed")).toEqual(["true", "false", "false"]);
  expect(attribute(html, "what-if-option", "data-unknown")).toEqual(["false", "false", "true"]);
  expect(html.match(/>2 cited outcomes</g)).toHaveLength(2);
  expect(attribute(html, "what-if-outcome", "data-testid")).toHaveLength(2);
  expect(shown).toContain("so dyeing with madder often leaves a pinkish tinge on the whites.");
  expect(shown).toContain("Tapano was developed to counteract the pinkish tinge");
  expect(shown).not.toContain("first synthesised in 1868");
  expect(html.match(/data-testid="citation-chip"/g)).toHaveLength(2);
  expect(attribute(html, "what-if", "data-chosen")).toEqual(["1"]);
  expect([optionNote({ outcomes: [] }), optionNote({ outcomes: whatIf().options[0].outcomes.slice(0, 1) }), optionNote(whatIf().options[0])]).toEqual([
    "Unknown",
    "1 cited outcome",
    "2 cited outcomes"
  ]);
});

test("a relationship that is a hypothesis is labelled as one and stated findings carry no label", () => {
  const block = whatIf();
  const [first, second] = block.options[0].outcomes;
  const hypothesis = { ...first, sentence: { ...first.sentence, level: "HYPOTHESIS" as const, citations: first.sentence.citations.map((citation) => ({ ...citation, level: "HYPOTHESIS" as const })) } };
  const html = lab({ ...block, options: [{ ...block.options[0], outcomes: [hypothesis, second] }, ...block.options.slice(1)] }, false);
  expect(attribute(html, "answer-sentence", "data-level")).toEqual(["HYPOTHESIS", "PROVISIONAL"]);
  expect(html.match(/>Hypothesis</g)).toHaveLength(1);
  expect(lab(block, false)).not.toContain(">Hypothesis<");
});

test("a flagged outcome opens its two readings after its sentence, never inside a paragraph", () => {
  const block = whatIf();
  const [first, second] = block.options[0].outcomes;
  const [cite] = first.sentence.citations;
  const readings = [
    { ...cite, quote: "Alum alone fixes the red" },
    { ...cite, id: `${cite.id}-other`, sourceId: MORDANT_PAPER, quote: "Alum with iron dulls the red" }
  ];
  const flagged = { ...first, sentence: { ...first.sentence, citations: readings, sourcesDiffer: true, differsOn: "What alum does to the red" } };
  const html = lab({ ...block, options: [{ ...block.options[0], outcomes: [flagged, second] }, ...block.options.slice(1)] }, false);
  const outcome = html.slice(html.indexOf('data-testid="what-if-outcome"'), html.indexOf("</li>"));
  expect(shownText(outcome)).toContain("<summary>Sources differ: What alum does to the red</summary>");
  expect(attribute(outcome, "sources-differ-reading", "data-cite-host")).toEqual(["", ""]);
  expect(outcome).not.toMatch(/<p[^>]*>(?:(?!<\/p>).)*<details/);
  expect(lab(block, false)).not.toContain("<details");
});

test("an option with no cited outcome is shown as Unknown and given none", () => {
  const block = whatIf();
  const html = lab({ ...block, options: [block.options[2], block.options[0]] }, false);
  expect(attribute(html, "what-if-option", "aria-pressed")).toEqual(["true", "false"]);
  expect(html).toContain('data-testid="what-if-unknown"');
  expect(html.match(/>Unknown</g)).toHaveLength(2);
  expect(html).not.toContain('data-testid="what-if-outcome"');
  expect(html).not.toContain('data-testid="citation-chip"');
});

test("the outcomes swap in place with no motion, so reduced motion draws the same lab", () => {
  const moving = lab(whatIf(), false);
  const still = lab(whatIf(), true);
  expect(moving).not.toContain("data-motion");
  expect(still).toBe(moving);
});

test("the play blocks join the answer's one numbering: values by their citations, outcomes by their sentences", () => {
  expect(blockSentences(simulation())).toEqual([]);
  expect(blockCitations(simulation()).map((citation) => citation.claimId)).toEqual(["00885460-e0ce-5a6e-905c-28da38a06a16", "00885460-e0ce-5a6e-905c-28da38a06a16"]);
  expect(blockSentences(whatIf()).map((sentence) => sentence.id)).toEqual(["s2.b1.1", "s2.b1.2", "s2.b1.3", "s2.b1.4"]);
  expect(blockSourceIds(whatIf())).toEqual([GI_JOURNAL, GI_JOURNAL, GI_JOURNAL, GI_JOURNAL, MORDANT_PAPER, MORDANT_PAPER]);
  const section = { id: "s1", discipline: "GEOGRAPHY", title: "Water", order: 1, state: "READY", searched: null, blocks: [simulation(), whatIf()] } as unknown as SectionView;
  expect([...explainerSourceNumbers([section])]).toEqual([
    [WATER_SOURCE, 1],
    [GI_JOURNAL, 2],
    [MORDANT_PAPER, 3]
  ]);
});

test("play renderers lay out in shrinkable columns so nothing widens a phone page", () => {
  const html = [
    lab(whatIf(), false),
    lab(whatIf(), true),
    withReading(createElement(GeneratedExplainerView, { block: simulation(), canHide: true, hiding: { hidden: false, busy: false, failed: false, change: () => undefined } }), LOOKUP)
  ].join("");
  const tracks = gridTracks(html);
  expect(tracks.length).toBeGreaterThan(0);
  for (const track of tracks) expect(track).toMatch(SHRINKABLE_TRACK);
  expect(html).not.toMatch(FIXED_WIDE_WIDTH);
  expect(html.match(/class="[^"]*\bmin-w-0\b/g)?.length ?? 0).toBeGreaterThan(10);
});
