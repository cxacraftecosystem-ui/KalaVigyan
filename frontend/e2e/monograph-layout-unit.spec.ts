import { expect, test } from "@playwright/test";

import { gradeTally, kitCites, scriptJson, sentenceCounts } from "../lib/monographRenderKit";
import { chapterOrder, componentBundles, nestedComponents, pagePlan, placedComponents, type Passage } from "../lib/monographRenderLayout";
import { sourceSplit } from "../lib/monographSources";

import { ASK, fixtureDocument, LIST, PICTURE, QUIZ } from "./monographFixture";

test("chapters follow the layout's order and are numbered after the masthead chapter", () => {
  const document = fixtureDocument();
  expect(chapterOrder(document.content.layout)).toEqual(["answer", "made", "sources"]);
  const plan = pagePlan(document);
  expect(plan.chapters.map((chapter) => [chapter.key, chapter.number, chapter.label])).toEqual([
    ["answer", null, "Answer"],
    ["made", 1, "How it is made"],
    ["sources", 2, "Sources"]
  ]);
});

test("the masthead takes the first chapter's kickers, its cited lede and the picture that follows them", () => {
  const plan = pagePlan(fixtureDocument());
  expect(plan.masthead).toEqual({ kicker: "u0001", standfirst: ["u0002"], lede: "u0003", picture: PICTURE });
  expect(plan.chapters[0].blocks).toEqual([]);
});

test("a chapter's head names its numeral, kicker, title and lede, and its source notes go to the margin", () => {
  const made = pagePlan(fixtureDocument()).chapters[1];
  const [head, quiz] = made.blocks;
  expect(head.kind).toBe("passage");
  const passage = head as Passage;
  expect(passage.head).toBe(true);
  expect(passage.notes).toEqual([{ ref: "u0009", source: "g1" }]);
  expect(passage.pieces).toEqual([
    { kind: "unit", ref: "u0005", role: "numeral" },
    { kind: "unit", ref: "u0006", role: "kicker" },
    { kind: "unit", ref: "u0007", role: "title" },
    { kind: "unit", ref: "u0008", role: "lede" },
    { kind: "unit", ref: "u0010", role: "label" },
    { kind: "list", refs: ["u0011", "u0012"] }
  ]);
  expect(quiz).toEqual({ kind: "component", label: QUIZ });
});

test("a component placed inside another's fragment is drawn there, never again at the top", () => {
  const document = fixtureDocument();
  expect([...nestedComponents(document)]).toEqual([ASK]);
  expect(placedComponents(document, LIST)).toEqual([ASK]);
  const sources = pagePlan(document).chapters[2];
  expect(sources.blocks.map((block) => (block.kind === "component" ? block.label : block.kind))).toEqual(["passage", LIST, "sources"]);
  expect(Object.keys(componentBundles(document, LIST))).toEqual([LIST, ASK]);
});

test("the sources chapter lists every cited source in number order in place of its bare group headings", () => {
  const document = fixtureDocument();
  const [, , last] = pagePlan(document).chapters[2].blocks;
  expect(last).toEqual({ kind: "sources", replaces: ["u0020", "u0021"] });
  expect(sourceSplit(document)).toEqual({ own: ["g1", "g2"], kin: [] });
  expect(sentenceCounts(document).get("g1")).toBe(2);
  expect(gradeTally(document, sourceSplit(document).own)).toEqual({ total: 2, grades: [{ grade: "A", count: 1 }, { grade: "B", count: 1 }] });
});

test("a generated document with one chapter, no masthead picture and no head reads without empty chapters", () => {
  const document = fixtureDocument();
  document.content.layout = document.content.layout.filter((entry) => entry.chapter === "answer" && entry.ref !== PICTURE && entry.within === null);
  document.fragments = {};
  document.specs = {};
  const plan = pagePlan(document);
  expect(plan.masthead.picture).toBeNull();
  expect(plan.chapters.map((chapter) => chapter.key)).toEqual(["answer"]);
});

test("the kit's citation data matches the shape the page script reads, closed against a script end tag", () => {
  const document = fixtureDocument();
  expect(kitCites(document.content)).toEqual({
    s: {
      g1: [1, "Test journal", "The test journal, volume 1", "Test Registry", 2023, "A", "https://example.org/journal", null],
      g2: [2, "Test book", null, null, null, "B", null, null]
    },
    c: { "t:1": [["g1", "p. 2", "Printed with a resist."]], "t:2": [["g1", null, null]] }
  });
  expect(scriptJson({ note: "</script>" })).toBe('{"note":"\\u003c/script>"}');
});
