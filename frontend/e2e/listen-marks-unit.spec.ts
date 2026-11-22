import { expect, test } from "@playwright/test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { CitationProvider } from "@/components/answer/CitationContext";
import { ExplainerReadingProvider } from "@/components/answer/ExplainerReading";
import { ExplainerSentence } from "@/components/answer/ExplainerSentence";
import { ENGLISH } from "@/lib/answerLanguages";
import { explainerShape, type ProseBlock } from "@/lib/explainerContract";
import type { ListenWord } from "@/lib/listen";
import { listenMarkStore, markOfSentence, type ListenMarks } from "@/lib/listenMarks";
import { parseShape } from "@/lib/shape";

import { attribute, NO_CITATIONS } from "./explainerRender";
import { readRepo } from "./phaseBFixture";

const WORDS: ListenWord[] = [
  { sentenceId: "s1", text: "Alum", start: 0, end: 0.4 },
  { sentenceId: "s1", text: "fixes.", start: 0.5, end: 1 },
  { sentenceId: "s2", text: "Iron", start: 1.2, end: 1.5 },
  { sentenceId: "s2", text: "darkens.", start: 1.6, end: 2 }
];
const TIME_UPDATES = [0.1, 0.3, 0.6, 0.8, 1.3, 1.4, 1.7, 1.9];

function readSentence(marks: ListenMarks): string {
  const document = parseShape(explainerShape, JSON.parse(readRepo("shared", "explainer.document.golden.json")));
  const sentence = (document.sections[1].blocks[0] as ProseBlock).sentences[0];
  const reading = { language: ENGLISH, original: false, hiddenTerms: new Set<string>(), onTerm: () => undefined, listen: marks };
  const drawn = createElement(ExplainerSentence, { sentence });
  return renderToStaticMarkup(createElement(ExplainerReadingProvider, { value: reading }, createElement(CitationProvider, { value: NO_CITATIONS }, drawn)));
}

function renderCounts(marks: ListenMarks, sentenceIds: string[]): Map<string, number> {
  const shown = new Map(sentenceIds.map((id) => [id, markOfSentence(marks, id)]));
  const renders = new Map(sentenceIds.map((id) => [id, 0]));
  marks.subscribe(() => {
    for (const id of sentenceIds) {
      const next = markOfSentence(marks, id);
      if (Object.is(next, shown.get(id))) continue;
      shown.set(id, next);
      renders.set(id, (renders.get(id) ?? 0) + 1);
    }
  });
  return renders;
}

test("a time update re-renders only the sentence whose read word changed", () => {
  const marks = listenMarkStore();
  const renders = renderCounts(marks, ["s1", "s2", "s3"]);
  for (const time of TIME_UPDATES) marks.follow(WORDS, time);
  expect(Object.fromEntries(renders)).toEqual({ s1: 3, s2: 2, s3: 0 });
});

test("every time update still reaches the dock's clock", () => {
  const marks = listenMarkStore();
  let heard = 0;
  marks.subscribe(() => (heard += 1));
  for (const time of TIME_UPDATES) marks.follow(WORDS, time);
  expect([heard, marks.time()]).toEqual([TIME_UPDATES.length, 1.9]);
  marks.follow(null, 0);
  expect([marks.mark(), marks.time()]).toEqual([null, 0]);
});

test("a shown mark that has not moved notifies no one", () => {
  const marks = listenMarkStore();
  let heard = 0;
  marks.subscribe(() => (heard += 1));
  const first = { sentenceId: "s1", words: WORDS.slice(0, 2), wordIndex: 1 };
  marks.show(first);
  marks.show({ ...first, words: [...first.words] });
  expect([heard, marks.mark()]).toEqual([1, first]);
});

test("the sentence being read draws its word from the store, and the explainer keeps one reading value while it plays", () => {
  const marks = listenMarkStore({ sentenceId: "s2.b1.1", words: [{ sentenceId: "s2.b1.1", text: "Presence", start: 0, end: 0.4 }], wordIndex: 0 });
  const drawn = readSentence(marks);
  expect(attribute(drawn, "answer-sentence", "data-listening")).toEqual(["true"]);
  expect(drawn).toContain('data-testid="listen-word">Presence</mark>');
  expect(attribute(readSentence(listenMarkStore()), "answer-sentence", "data-listening")).toEqual([""]);
  expect(readRepo("frontend", "components", "answer", "ExplainerView.tsx")).toContain("listen: listen.marks }");
});
