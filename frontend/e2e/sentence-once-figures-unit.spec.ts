import { expect, test } from "@playwright/test";
import { createElement } from "react";

import { ExpertPanel } from "@/components/answer/experts/ExpertPanel";
import { ProcessLadder } from "@/components/answer/ProcessLadder";
import { SignatureFigure } from "@/components/answer/SignatureFigure";
import { VatFigure } from "@/components/answer/VatFigure";
import { firingFacts } from "@/lib/answerSignature";
import { vatText } from "@/lib/answerVat";
import { BLOCK_SHAPES, signatureFigureShape, type ProcessLadderBlock } from "@/lib/explainerContract";
import { expertsDiffer, type ExpertViewBlock } from "@/lib/explainerExperts";
import type { FiringBlock, IndigoVatBlock } from "@/lib/explainerSignature";
import { stagesSaidOnce } from "@/lib/explainerView";
import { differCards } from "@/lib/expertPanel";
import { parseShape } from "@/lib/shape";

import { attribute, shownText, withApp, withReading } from "./explainerRender";
import { phaseBBlock, readRepo } from "./phaseBFixture";

const FIGURES = JSON.parse(readRepo("shared", "explainer.signature.golden.json")) as unknown[];
const DOCUMENT = JSON.parse(readRepo("shared", "explainer.document.golden.json")) as { sections: { blocks: unknown[] }[] };

function count(html: string, text: string): number {
  return shownText(html.replace(/<[^>]+>/g, "")).split(text).length - 1;
}

function vat(): IndigoVatBlock {
  const block = parseShape(signatureFigureShape, FIGURES[0]);
  if (block.kind !== "indigo_vat") throw new Error("the first golden figure is the indigo vat");
  return block;
}

function firing(): FiringBlock {
  const block = parseShape(signatureFigureShape, FIGURES[3]);
  if (block.kind !== "firing") throw new Error("the fourth golden figure is the firing");
  return block;
}

function ladder(): ProcessLadderBlock {
  return parseShape(BLOCK_SHAPES.process_ladder, structuredClone(DOCUMENT.sections[0].blocks[0]));
}

test("a firing figure states a sentence that backs its atmosphere and its temperature once, under both labels", () => {
  const block = firing();
  const said = block.atmospheres[0].sentence;
  const shared: FiringBlock = { ...block, temperature: { stated: "850 °C", sentence: { ...said, id: "lede.figure.3" } } };
  expect(firingFacts(shared).map((fact) => [fact.label, fact.sentence.id])).toEqual([["Reducing fire, black · Temperature, 850 °C", said.id]]);
  expect(firingFacts(block).map((fact) => fact.sentence.id)).toEqual([said.id, block.temperature!.sentence.id]);
  const html = withApp(createElement(SignatureFigure, { block: shared, number: 1 }));
  expect(count(html, said.text)).toBe(1);
  expect(html).toContain("Reducing fire, black · Temperature, 850 °C");
});

test("the vat figure says each sentence once: a later frame or fact that repeats one keeps its title and drops the sentence", () => {
  const block = vat();
  const text = vatText(block);
  expect(text.dek?.id).toBe("lede.figure.4");
  expect(text.frames.map((frame) => [frame.key, frame.sentence?.id ?? null])).toEqual([
    ["in", "lede.figure.3"],
    ["lifted", "lede.figure.1"],
    ["air", null]
  ]);
  expect(text.facts.map((fact) => [fact.label, fact.sentence.id])).toEqual([
    ["lime · jaggery · sagikhar", "lede.figure.5"],
    ["dates · soda", "lede.figure.6"],
    ["casatoria seeds", "lede.figure.10"]
  ]);
  const dyed = { ...block, contents: [...block.contents, { name: "indigo", sentence: { ...block.dips[0].sentence, id: "lede.figure.11" } }] };
  expect(vatText(dyed).facts.map((fact) => fact.sentence.id)).toEqual(["lede.figure.5", "lede.figure.6", "lede.figure.10"]);
  const html = withApp(createElement(VatFigure, { block, number: 1 }));
  for (const sentence of [block.lift, ...block.forms.map((form) => form.sentence), ...block.dips.map((dip) => dip.sentence), ...block.contents.map((content) => content.sentence)]) {
    expect(count(html, sentence.text)).toBe(1);
  }
});

test("a ladder stage leaves out a sentence an earlier stage already said, and keeps its own", () => {
  const block = ladder();
  const [first, second, third, fourth] = block.stages;
  const repeated: ProcessLadderBlock = {
    ...block,
    stages: [first, second, { ...third, sentences: [...third.sentences, { ...first.sentences[0], id: "s1.b1.9" }] }, { ...fourth, why: { ...second.sentences[0], id: "s1.b1.10" } }]
  };
  const stages = stagesSaidOnce(repeated.stages);
  expect(stages.map((stage) => [stage.sentences.map((sentence) => sentence.id), stage.why?.id ?? null])).toEqual([
    [["s1.b1.1", "s1.b1.2"], null],
    [["s1.b1.3", "s1.b1.4"], null],
    [["s1.b1.5"], null],
    [["s1.b1.6"], null]
  ]);
  const html = withApp(createElement(ProcessLadder, { block: repeated }));
  expect(attribute(html, "ladder-stage", "data-testid")).toHaveLength(4);
  expect(count(html, first.sentences[0].text)).toBe(1);
  expect(count(html, second.sentences[0].text)).toBe(1);
});

test("expert differences that share a seat's sentence are one card with every side once", () => {
  const historian = phaseBBlock("expert_view", "s5.b1");
  const anthropologist = phaseBBlock("expert_view", "s5.b2");
  const said = historian.differs[0].thisView;
  const answer = { ...said, id: "s5.b4.1", text: "Economists date the trade to the 1990s." };
  const widened: ExpertViewBlock = { ...historian, differs: [...historian.differs, { seat: "ECONOMIST", thisView: { ...said, id: "s5.b1.9" }, otherView: answer }] };
  const economist: ExpertViewBlock = { ...historian, id: "s5.b4", seat: "ECONOMIST", take: [answer], agreesWith: [], differs: [{ seat: "HISTORIAN", thisView: answer, otherView: said }] };
  const views = [widened, anthropologist, economist];
  const pairs = expertsDiffer(views);
  expect(pairs.map((pair) => pair.seats)).toEqual([
    ["HISTORIAN", "ANTHROPOLOGIST"],
    ["HISTORIAN", "ECONOMIST"]
  ]);
  const cards = differCards(pairs);
  expect(cards.map((card) => card.sides.map((side) => [side.seat, side.view.id]))).toEqual([
    [
      ["HISTORIAN", said.id],
      ["ANTHROPOLOGIST", historian.differs[0].otherView.id],
      ["ECONOMIST", "s5.b4.1"]
    ]
  ]);
  const html = withReading(createElement(ExpertPanel, { views, reduce: true }));
  expect(attribute(html, "experts-differ", "data-testid")).toHaveLength(1);
  expect(attribute(html, "experts-differ-side", "data-seat")).toEqual(["HISTORIAN", "ANTHROPOLOGIST", "ECONOMIST"]);
  expect(count(html, said.text)).toBe(1);
});
