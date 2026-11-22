import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";
import { createElement, type ComponentProps } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { ExplainerView } from "@/components/answer/ExplainerView";
import { LadderStageCard } from "@/components/answer/LadderStageCard";
import { AnswerFigure, NumberedFigures } from "@/components/answer/place/AnswerFigure";
import { AuthProvider } from "@/components/AuthProvider";
import { ThemeProvider } from "@/components/ThemeProvider";
import { ENGLISH, type AnswerLanguage } from "@/lib/answerLanguages";
import type { ExplainerSentence } from "@/lib/explainerBlockBase";
import { explainerShape, ledeBlockShape, type Explainer, type LadderStage } from "@/lib/explainerContract";
import type { ExplainerState } from "@/lib/explainerState";
import { explainerStateOf } from "@/lib/explainerVersions";
import type { UnderstoodPart } from "@/lib/explainerView";
import { parseShape } from "@/lib/shape";

import { attribute, shownText, withReading } from "./explainerRender";

type FigureProps = ComponentProps<typeof AnswerFigure>;

const URDU: AnswerLanguage = { code: "ur", label: "Urdu", autonym: "اردو", script: "Arab", direction: "rtl" };
const RETIRED_LOOK = /purple|field-button|class="panel|eyebrow|font-display|text-ink-900|bg-card|text-white/;

function explainer(): Explainer {
  return parseShape(explainerShape, JSON.parse(readFileSync(join(__dirname, "..", "..", "shared", "explainer.lede.golden.json"), "utf8")));
}

function saved(document: Explainer = explainer()): ExplainerState {
  const mark = { explainerId: document.answerId, version: 1, answerId: document.answerId, basedOn: null, question: document.question, changes: [], createdAt: document.createdAt };
  return explainerStateOf({ schemaVersion: 1, mark, explainer: document });
}

function drawn(state: ExplainerState, languages: AnswerLanguage[] = [ENGLISH]): string {
  const view = createElement(ExplainerView, {
    state,
    streaming: false,
    languages,
    depthLabel: null,
    change: { parts: new Set<UnderstoodPart>(), onChange: () => undefined },
    listenLanguages: [],
    onFollowUp: null,
    onFreshResearch: null
  });
  return renderToStaticMarkup(createElement(AuthProvider, null, createElement(ThemeProvider, null, view)));
}

function inUrdu(sentence: ExplainerSentence): ExplainerSentence {
  return { ...sentence, text: `ترجمہ ${sentence.id}`, translated: true, original: sentence.text };
}

test("the essay opens with its provenance, the question as h1 and the two quiet actions of a settled answer", () => {
  const html = drawn(saved());
  expect(attribute(html, "answer-provenance", "data-testid")).toHaveLength(2);
  expect(shownText(html)).toContain(`Drawn from ${explainer().sources.length} sources`);
  expect(html.match(/<h1[ >]/g)).toHaveLength(1);
  expect(attribute(html, "cite-answer-toggle", "aria-expanded")).toEqual(["false"]);
  expect(attribute(html, "cite-answer-toggle", "data-variant")).toEqual(["quiet"]);
  expect(html).not.toContain('data-testid="save-answer"');
  expect(html).not.toContain('data-variant="primary"');
  expect(html).not.toMatch(RETIRED_LOOK);
});

test("each section is a numbered chapter with its sources in the margin", () => {
  const document = explainer();
  const html = drawn(saved(document));
  expect(attribute(html, "explainer-section", "data-state")).toEqual(document.sections.map(() => "READY"));
  document.sections.forEach((section, index) => expect(shownText(html)).toContain(`${index + 1} · `));
  const notes = attribute(html, "margin-notes", "data-testid");
  expect(notes.length).toBeGreaterThan(0);
  expect(shownText(html)).toContain(document.sources[0].title.slice(0, 24));
});

test("an answer in Urdu mirrors its article and sets its prose in Nastaliq", () => {
  const document = explainer();
  const lede = document.lede ? { ...document.lede, sentences: document.lede.sentences.map(inUrdu) } : undefined;
  const sections = document.sections.map((section) => ({ ...section, blocks: section.blocks.map((block) => (block.kind === "prose" ? { ...block, sentences: block.sentences.map(inUrdu) } : block)) }));
  const urdu = { ...document, understood: { ...document.understood, language: "ur" }, lede, sections };
  const html = drawn(saved(urdu), [ENGLISH, URDU]);
  expect(html).toMatch(/<article lang="ur" dir="rtl"/);
  expect(html).toMatch(/<p lang="ur" dir="rtl" data-script="Aran" class="[^"]*leading-\[2\.2\]/);
  expect(drawn(saved(document))).not.toMatch(/<article[^>]*dir="rtl"/);
});

test("a reached stage takes the ink leading rule and its number an ink tile, never an indigo fill", () => {
  const stage: LadderStage = { stageId: "st1", ordinal: 3, name: "Dyeing in indigo", stageType: "DYE", level: "VERIFIED", sentences: [], materials: [], conditions: [], reactionIds: [] };
  const craft = { slug: "Kutch-Ajrakh", name: "Kutch Ajrakh", path: "/crafts/Kutch-Ajrakh" };
  const reached = withReading(createElement(LadderStageCard, { stage, craft, reached: true }));
  const resting = withReading(createElement(LadderStageCard, { stage, craft, reached: false }));
  expect(reached).toContain("border-s-ink-1");
  expect(reached).toContain("bg-ink-1 text-ground");
  expect(resting).toContain("border-s-transparent");
  expect(`${reached}${resting}`).not.toMatch(/bg-indigo|purple/);
});

test("the essay numbers its figures through one counter that starts after the signature figure, and nowhere else numbers them", () => {
  const plain = drawn(saved());
  expect(plain).toMatch(/<article[^>]*class="kv-essay min-w-0"/);
  expect(plain).not.toMatch(/<article[^>]*data-signature/);
  const lede = parseShape(ledeBlockShape, JSON.parse(readFileSync(join(__dirname, "..", "..", "shared", "explainer.signature-lede.golden.json"), "utf8")));
  expect(lede.figure).not.toBeNull();
  expect(drawn(saved({ ...explainer(), lede }))).toMatch(/<article[^>]*data-signature=""/);
  const map = createElement("svg");
  const numbered = renderToStaticMarkup(createElement(NumberedFigures.Provider, { value: true }, createElement(AnswerFigure, { texts: { kicker: "Rainfall", title: "Kachchh and Barmer" } } as FigureProps, map)));
  expect(numbered).toContain('<p class="kv-fig-no mb-0"><span class="kv-fig-count" data-testid="figure-number"></span> · Rainfall</p>');
  const untitled = renderToStaticMarkup(createElement(NumberedFigures.Provider, { value: true }, createElement(AnswerFigure, { texts: { title: "Kachchh and Barmer" } } as FigureProps, map)));
  expect(untitled).toContain('<p class="kv-fig-no mb-0"><span class="kv-fig-count" data-testid="figure-number"></span></p>');
  const elsewhere = renderToStaticMarkup(createElement(AnswerFigure, { texts: { title: "Kachchh and Barmer" } } as FigureProps, map));
  expect(elsewhere).not.toContain("kv-fig-no");
  const css = readFileSync(join(__dirname, "..", "app", "editorial-figure.css"), "utf8");
  expect(css).toMatch(/\.kv-essay \{\s*counter-reset: kv-figure;/);
  expect(css).toMatch(/\.kv-essay\[data-signature\] \{\s*counter-reset: kv-figure 1;/);
  expect(css).toMatch(/\.kv-essay \.kv-fig-count \{\s*counter-increment: kv-figure;/);
  expect(css).toMatch(/\.kv-essay \.kv-fig-count::before \{\s*content: "Fig\. ";/);
  expect(css).toMatch(/\.kv-essay \.kv-fig-count::after \{\s*content: counter\(kv-figure\);/);
});
