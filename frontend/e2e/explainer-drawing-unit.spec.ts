import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";
import { createElement, type ReactElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { CitationProvider, type CitationLookup } from "@/components/answer/CitationContext";
import { ExplainerReadingProvider, type ExplainerReading } from "@/components/answer/ExplainerReading";
import { ExplainerSentence } from "@/components/answer/ExplainerSentence";
import { ExplainerView } from "@/components/answer/ExplainerView";
import { ImageStrip } from "@/components/answer/ImageStrip";
import { AuthProvider } from "@/components/AuthProvider";
import { ThemeProvider } from "@/components/ThemeProvider";
import { ENGLISH } from "@/lib/answerLanguages";
import { splitSseBuffer } from "@/lib/answerStream";
import { explainerShape, type Explainer, type ExplainerBlock, type ImagesBlock, type ProseBlock } from "@/lib/explainerContract";
import { askingExplainer, reduceExplainer, type ExplainerState } from "@/lib/explainerState";
import { explainerEventOf, type ExplainerEvent } from "@/lib/explainerStream";
import { explainerStateOf } from "@/lib/explainerVersions";
import type { UnderstoodPart } from "@/lib/explainerView";
import { parseShape } from "@/lib/shape";

import { attribute, shownText } from "./explainerRender";

const ROOT = join(__dirname, "..", "..");
const read = (...parts: string[]) => readFileSync(join(ROOT, ...parts), "utf8");
const LEDE_QUESTION = "Which mordant fixes the red in Kutch Ajrakh block printing?";

function streamed(name: string): ExplainerEvent[] {
  const { blocks } = splitSseBuffer(read("shared", name));
  return blocks.map(explainerEventOf).filter((event): event is ExplainerEvent => event !== null);
}

function researched(): ExplainerState {
  return streamed("answer-stream.research.golden.sse").reduce(reduceExplainer, askingExplainer("Why does alum keep Ajrakh red?", "en"));
}

function document(name: string): Explainer {
  return parseShape(explainerShape, JSON.parse(read("shared", name)));
}

function drawn(state: ExplainerState, streaming = false): string {
  const view = createElement(ExplainerView, {
    state,
    streaming,
    languages: [ENGLISH],
    depthLabel: "Detailed",
    change: { parts: new Set<UnderstoodPart>(), onChange: () => undefined },
    listenLanguages: [],
    onFollowUp: null,
    onFreshResearch: null
  });
  return renderToStaticMarkup(createElement(AuthProvider, null, createElement(ThemeProvider, null, view)));
}

function sentenceChips(html: string): [string, string[]][] {
  const marks = [...html.matchAll(/data-testid="answer-sentence" data-sentence-id="([^"]+)"/g)];
  return marks.map((mark, index) => {
    const close = html.indexOf("</p>", mark.index);
    const end = Math.min(marks[index + 1]?.index ?? html.length, close < 0 ? html.length : close);
    return [mark[1], attribute(html.slice(mark.index, end), "citation-chip", "data-numbers").flatMap((numbers) => numbers.split(","))];
  });
}

function listedSources(html: string): [string, string][] {
  return [...html.matchAll(/<li id="source-(\d+)"[^>]*>.*?data-testid="source-title">([^<]*)/g)].map((found) => [found[1], shownText(found[2])]);
}

function at(html: string, testId: string): number {
  return html.indexOf(`data-testid="${testId}"`);
}

function blockOf<K extends ExplainerBlock["kind"]>(state: ExplainerState, kind: K): Extract<ExplainerBlock, { kind: K }> {
  const found = state.sections.flatMap((section) => section.blocks).find((block) => block.kind === kind);
  if (!found) throw new Error(`the researched golden streams a ${kind} block`);
  return found as Extract<ExplainerBlock, { kind: K }>;
}

function reading(onTerm: ExplainerReading["onTerm"]): ExplainerReading {
  return { language: ENGLISH, original: false, hiddenTerms: new Set(), onTerm, listen: null };
}

function withReading(child: ReactElement, onTerm: ExplainerReading["onTerm"] = () => undefined): string {
  const lookup: CitationLookup = { numbers: new Map(), sourcesById: new Map(), onOpen: () => undefined };
  return renderToStaticMarkup(createElement(ExplainerReadingProvider, { value: reading(onTerm) }, createElement(CitationProvider, { value: lookup }, child)));
}

function attributes(html: string, name: string): string[] {
  return [...html.matchAll(new RegExp(`${name}="([^"]*)"`, "g"))].map((found) => found[1]);
}

test("a streamed images block is drawn as one credited inline picture", () => {
  const images: ImagesBlock = blockOf(researched(), "images");
  const html = renderToStaticMarkup(createElement(ImageStrip, { block: images }));
  expect(attributes(html, "data-display")).toEqual(["INLINE"]);
  expect(html.match(/referrerpolicy="no-referrer"/gi)?.length).toBe(images.items.length);
  expect(html).not.toMatch(/referrerpolicy="(?!no-referrer")/i);
  for (const item of images.items) {
    expect(attributes(html, "href")).toContain(item.media.pageUrl);
    expect(attributes(html, "src")).toContain(item.media.imageUrl);
  }
  expect(html).toContain("A. Dyer");
  expect(html).toContain("CC BY-SA 4.0");
});

test("a stored images block draws a credited link card beside its inline picture", () => {
  const document = JSON.parse(read("shared", "explainer.document.golden.json")) as { sections: { blocks: ExplainerBlock[] }[] };
  const images = document.sections[0].blocks[1] as ImagesBlock;
  const html = renderToStaticMarkup(createElement(ImageStrip, { block: images }));
  expect(attributes(html, "data-display")).toEqual(["INLINE", "LINK_CARD"]);
  expect(html.match(/referrerpolicy="no-referrer"/gi)?.length).toBe(images.items.length);
  expect(html).toContain("SMarndi");
  expect(html).toContain("Victoria and Albert Museum, London");
  expect(html).toContain("Ajrakh process sample");
});

test("a streamed sentence underlines its server-marked terms as buttons that open the term sheet", () => {
  const prose: ProseBlock = blockOf(researched(), "prose");
  const [first] = prose.sentences;
  expect(first.terms).toEqual([
    { text: "Alum", termKey: "alum" },
    { text: "alizarin", termKey: "alizarin" },
    { text: "cotton", termKey: "cotton" }
  ]);
  const html = withReading(createElement(ExplainerSentence, { sentence: first }));
  const buttons = [...html.matchAll(/<button[^>]*data-testid="term-span"[^>]*>(.*?)<\/button>/g)].map((found) => found[1].replace(/<[^>]+>/g, ""));
  expect(buttons).toEqual(["Alum", "alizarin", "cotton"]);
  expect(html.replace(/<[^>]+>/g, "")).toContain("Alum is the mordant that binds alizarin to cotton.");
  const view = read("frontend", "components", "answer", "ExplainerView.tsx");
  expect(view).toContain("onTerm: terms.open");
  expect(view).toContain("<TermSheet span={terms.span}");
  expect(read("frontend", "components", "answer", "ExplainerSentence.tsx")).toContain("onClick={() => reading.onTerm(term)}");
  expect(read("frontend", "components", "answer", "TermSheet.tsx")).toContain("open={span !== null && !missing}");
});

test("the whole explainer view draws the researched answer with its pictures and terms", () => {
  const html = drawn(researched());
  expect(attributes(html, "data-kind")).toEqual(["prose", "images"]);
  expect(html).toContain('data-testid="image-strip"');
  expect(html.match(/data-testid="term-span"/g)?.length).toBe(4);
});

test("the essay opens under the understood line: the question as its h1, then the cited lede, its sources numbered first, and the research trail only while it streams", () => {
  const expected = document("explainer.lede.golden.json");
  const [trail] = streamed("explainer.stream.golden.sse").filter((event) => event.type === "trail");
  const state = reduceExplainer(streamed("explainer.lede.golden.sse").reduce(reduceExplainer, askingExplainer(LEDE_QUESTION, "en")), trail);
  const html = drawn(state);
  expect(html.match(/data-testid="answer-lede"/g)?.length).toBe(1);
  expect(html.match(/<h1[ >]/g)?.length).toBe(1);
  expect(at(html, "understood-line")).toBeLessThan(at(html, "answer-question"));
  expect(at(html, "answer-question")).toBeLessThan(at(html, "answer-lede"));
  expect(html).not.toContain('data-testid="research-trail"');
  expect(drawn(state, true)).toContain('data-testid="research-trail"');
  const headline = /<h1 lang="([^"]*)" dir="([^"]*)"[^>]*>([^<]*)<\/h1>/.exec(html);
  expect(headline?.slice(1)).toEqual(["en", "ltr", LEDE_QUESTION]);
  expect(sentenceChips(html)).toEqual([
    ["lede.1", ["1"]],
    ["lede.2", ["1", "2"]],
    ["lede.3", ["1"]],
    ...["s1.b1.1", "s1.b1.2", "s2.b1.1", "s2.b1.2", "s3.b1.1", "s3.b1.2"].map((id): [string, string[]] => [id, ["1"]])
  ]);
  expect(listedSources(html)).toEqual(expected.sources.map((source, index) => [String(index + 1), source.title]));
});

test("the lede paragraph runs the reading column's full width like the section prose, so a right-to-left lede ends at the column's edge", () => {
  const html = drawn(streamed("explainer.lede.golden.sse").reduce(reduceExplainer, askingExplainer(LEDE_QUESTION, "en")));
  const paragraph = /<p[^>]* class="([^"]*)"/.exec(html.slice(at(html, "answer-lede")));
  expect(paragraph?.[1].split(" ").filter((name) => name.startsWith("max-w-"))).toEqual([]);
});

test("the lede is drawn while the answer streams, before any section has a block", () => {
  const events = streamed("explainer.lede.golden.sse");
  const opened = events.slice(0, events.findIndex((event) => event.type === "lede") + 1).reduce(reduceExplainer, askingExplainer(LEDE_QUESTION, "en"));
  const html = drawn(opened, true);
  expect(opened.sections.every((section) => section.blocks.length === 0)).toBe(true);
  expect(at(html, "answer-lede")).toBeGreaterThan(-1);
  expect(at(html, "answer-lede")).toBeLessThan(at(html, "answer-progress"));
  expect(sentenceChips(html)).toEqual([
    ["lede.1", ["1"]],
    ["lede.2", ["1", "2"]],
    ["lede.3", ["1"]]
  ]);
});

test("a stored explainer opened from Saved draws its lede and numbers its sources as the streamed answer did", () => {
  const explainer = document("explainer.lede.golden.json");
  const mark = { explainerId: explainer.answerId, version: 1, answerId: explainer.answerId, basedOn: null, question: explainer.question, changes: [], createdAt: explainer.createdAt };
  const saved = drawn(explainerStateOf({ schemaVersion: 1, mark, explainer }));
  const live = drawn(streamed("explainer.lede.golden.sse").reduce(reduceExplainer, askingExplainer(LEDE_QUESTION, "en")));
  expect(at(saved, "answer-lede")).toBeGreaterThan(-1);
  expect(sentenceChips(saved)).toEqual(sentenceChips(live));
  expect(listedSources(saved)).toEqual(listedSources(live));
});

test("an answer streamed without a lede draws as before, its sources numbered from its first section", () => {
  const expected = document("explainer.document.golden.json");
  const html = drawn(streamed("explainer.stream.golden.sse").reduce(reduceExplainer, askingExplainer(expected.question, "en")));
  expect(expected.lede).toBeUndefined();
  expect(html).not.toContain('data-testid="answer-lede"');
  expect(listedSources(html)).toEqual(expected.sources.map((source, index) => [String(index + 1), source.title]));
  expect(sentenceChips(html).flatMap(([, chips]) => chips)).not.toContain("·");
});
