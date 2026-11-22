import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";
import { createElement } from "react";

import { ExplainerSectionView } from "@/components/answer/ExplainerSectionView";
import { ExplainerSentence } from "@/components/answer/ExplainerSentence";
import { CitedText } from "@/components/answer/ProseBlockView";
import { explainerSentenceShape, type ExplainerSentence as Sentence } from "@/lib/explainerBlockBase";
import { explainerSectionShape, explainerShape, type ExplainerBlock } from "@/lib/explainerContract";
import type { SectionView } from "@/lib/explainerState";
import { withdrawnNote } from "@/lib/explainerView";
import { parseShape, ShapeError } from "@/lib/shape";
import { differingReadings, differNotes } from "@/lib/sourcesDiffer";

import { attribute, shownText, withReading } from "./explainerRender";

const SHARED = join(__dirname, "..", "..", "shared");
const ABOUT = "How long the red dye bath lasts";
const PAYLOAD = {
  id: "s1.b1.1",
  text: "Alum is the mordant that binds alizarin to cotton.",
  level: "PROVISIONAL",
  citations: [
    {
      id: "c0000000-0000-4000-8000-000000000001",
      claimId: "3f2a1b0c-9d8e-4f7a-8b6c-5d4e3f2a1b0c",
      sourceId: "1a2b3c4d-0000-4000-8000-000000000001",
      quote: "Alum is the mordant",
      locator: "p. 41",
      context: null,
      evidence: "QUOTED",
      level: "PROVISIONAL"
    }
  ],
  translated: false,
  terms: []
};

function twoReadings(sentence: Sentence): Sentence {
  const [first] = sentence.citations;
  const second = { ...first, id: "c0000000-0000-4000-8000-000000000002", sourceId: "1a2b3c4d-0000-4000-8000-000000000002", quote: "Alum alone fixes the red" };
  const repeat = { ...first, id: "c0000000-0000-4000-8000-000000000003", quote: "Alum again" };
  return { ...sentence, citations: [first, second, repeat], sourcesDiffer: true };
}

function paragraph(sentences: Sentence[]): string {
  return withReading(createElement(CitedText, { id: "s1.b1", sentences, className: "font-reading text-body text-ink-1" }));
}

test("a sentence payload may say its sources differ, and only as true or false", () => {
  expect(explainerSentenceShape.parse({ ...PAYLOAD, sourcesDiffer: true }, "sentence").sourcesDiffer).toBe(true);
  expect("sourcesDiffer" in explainerSentenceShape.parse(PAYLOAD, "sentence")).toBe(false);
  expect(() => explainerSentenceShape.parse({ ...PAYLOAD, sourcesDiffer: "yes" }, "sentence")).toThrow(ShapeError);
});

test("a sentence payload names what its sources differ on only when they differ", () => {
  expect(explainerSentenceShape.parse({ ...PAYLOAD, sourcesDiffer: true, differsOn: ABOUT }, "sentence").differsOn).toBe(ABOUT);
  expect("differsOn" in explainerSentenceShape.parse({ ...PAYLOAD, sourcesDiffer: true }, "sentence")).toBe(false);
  expect(() => explainerSentenceShape.parse({ ...PAYLOAD, differsOn: ABOUT }, "sentence")).toThrow(/only on a sentence whose sources differ/);
  expect(() => explainerSentenceShape.parse({ ...PAYLOAD, sourcesDiffer: true, differsOn: 4 }, "sentence")).toThrow(ShapeError);
});

test("a flagged sentence draws only the Sources differ tag, never the readings", () => {
  const sentence = twoReadings(explainerSentenceShape.parse(PAYLOAD, "sentence"));
  const flagged = withReading(createElement(ExplainerSentence, { sentence }));
  expect(attribute(flagged, "evidence-tag", "data-level")).toEqual(["differ"]);
  expect(flagged.match(/<button\b/g)?.length).toBe(flagged.match(/data-testid="citation-chip"/g)?.length);
  expect(flagged).not.toContain("aria-controls");
  expect(flagged).not.toContain("Alum alone fixes the red");
  expect(flagged).not.toContain("<details");
  const plain = withReading(createElement(ExplainerSentence, { sentence: explainerSentenceShape.parse(PAYLOAD, "sentence") }));
  expect(attribute(plain, "evidence-tag", "data-level")).toEqual([]);
});

test("the readings of a flagged sentence follow its paragraph in a details element, quoted and cited once per source", () => {
  const sentence = twoReadings(explainerSentenceShape.parse(PAYLOAD, "sentence"));
  expect(differingReadings(sentence.citations).map((citation) => citation.quote)).toEqual(["Alum is the mordant", "Alum alone fixes the red"]);
  const html = paragraph([{ ...sentence, differsOn: ABOUT }]);
  expect(html.indexOf("</p><details")).toBeGreaterThan(0);
  expect(html).not.toMatch(/<p[^>]*>(?:(?!<\/p>).)*<details/);
  expect(shownText(html)).toContain(`<summary>Sources differ: ${ABOUT}</summary>`);
  expect(attribute(html, "sources-differ-reading", "data-cite-host")).toEqual(["", ""]);
  expect(html).toContain('<span class="italic">Alum is the mordant</span>');
  expect(html).toContain('<span class="italic">Alum alone fixes the red</span>');
  expect(html).not.toContain("Alum again");
});

test("a flagged sentence whose claim names no subject says only that the sources differ, and one reading draws no details", () => {
  const sentence = twoReadings(explainerSentenceShape.parse(PAYLOAD, "sentence"));
  expect(paragraph([sentence])).toContain("<summary>Sources differ</summary>");
  const single = { ...explainerSentenceShape.parse(PAYLOAD, "sentence"), sourcesDiffer: true };
  expect(paragraph([single])).not.toContain("<details");
  expect(differNotes([single, sentence]).map((note) => [note.sentenceId, note.about, note.readings.length])).toEqual([["s1.b1.1", null, 2]]);
});

test("a section a withdrawn interview shortened counts what was taken out under its blocks", () => {
  const base = { id: "s1", discipline: "PROCESS", title: "Process", order: 1, state: "READY", searched: null, blocks: [] };
  expect(explainerSectionShape.parse({ ...base, withdrawn: 2 }, "section").withdrawn).toBe(2);
  expect("withdrawn" in explainerSectionShape.parse(base, "section")).toBe(false);
  expect(() => explainerSectionShape.parse({ ...base, withdrawn: 0 }, "section")).toThrow(ShapeError);
  expect(withdrawnNote(1)).toBe("A field interview this section quoted is no longer shown, so one passage was taken out.");
  expect(withdrawnNote(3)).toBe("A field interview this section quoted is no longer shown, so 3 passages were taken out.");
  const prose: ExplainerBlock = { id: "s1.b1", kind: "prose", version: 1, reuse: null, sentences: [explainerSentenceShape.parse(PAYLOAD, "sentence")] };
  const section: SectionView = { ...base, discipline: "PROCESS", state: "READY", blocks: [prose], withdrawn: 1 };
  const html = withReading(createElement(ExplainerSectionView, { section, streaming: false, reduce: true, onActive: () => undefined }));
  expect(attribute(html, "section-withdrawn", "data-testid")).toEqual(["section-withdrawn"]);
  expect(shownText(html)).toContain(withdrawnNote(1));
  const whole = withReading(createElement(ExplainerSectionView, { section: { ...section, withdrawn: undefined }, streaming: false, reduce: true, onActive: () => undefined }));
  expect(whole).not.toContain("section-withdrawn");
});

test("the withdrawn golden parses with its section's count and its sentence's named difference", () => {
  const read = parseShape(explainerShape, JSON.parse(readFileSync(join(SHARED, "explainer.withdrawn.golden.json"), "utf8")));
  const third = read.sections[2];
  expect([third.id, third.withdrawn]).toEqual(["s3", 1]);
  const [prose] = third.blocks;
  const flagged = prose.kind === "prose" ? prose.sentences[2] : null;
  expect([flagged?.id, flagged?.sourcesDiffer, flagged?.differsOn]).toEqual(["s3.b1.3", true, "where the alum paste is printed"]);
});
