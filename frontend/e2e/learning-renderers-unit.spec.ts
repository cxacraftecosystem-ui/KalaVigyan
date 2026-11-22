import { expect, test } from "@playwright/test";
import { createElement } from "react";

import { BLOCK_RENDERERS } from "@/components/answer/blockRenderers";
import { CompareTable } from "@/components/answer/learning/CompareTable";
import { ConceptGraphView } from "@/components/answer/learning/ConceptGraphView";
import { QuizView } from "@/components/answer/learning/QuizView";
import { compareLayout, rowTitle } from "@/lib/compareView";
import { graphLayout, graphSummary, LABEL_GAP_PX, ringPoints, separatedLabels } from "@/lib/conceptGraph";
import type { ConceptNode } from "@/lib/explainerLearning";
import type { SectionView } from "@/lib/explainerState";
import { explainerSourceNumbers } from "@/lib/explainerView";
import { optionOrder, picked, promptParts, quizScore, scoreText } from "@/lib/quizView";

import { attribute, FIXED_WIDE_WIDTH, gridTracks, shownText, SHRINKABLE_TRACK, withReading } from "./explainerRender";
import { PHASE_D, phaseDBlock } from "./phaseDFixture";

const quiz = () => phaseDBlock("quiz", "s1.b1");
const graph = () => phaseDBlock("concept_graph", "s2.b1");
const compare = () => phaseDBlock("compare", "s3.b1");
const AJRAKH = { slug: "Kutch-Ajrakh", name: "Kutch Ajrakh", path: "/crafts/Kutch-Ajrakh" };

function text(html: string): string {
  return shownText(html.replace(/<[^>]+>/g, ""));
}

function widened(node: ConceptNode, count: number): ConceptNode {
  const crafts = Array.from({ length: count }, (_, index) => {
    const entry = node.crafts[index % node.crafts.length];
    return { ...entry, craft: { slug: `Craft-${index + 1}`, name: `Craft ${index + 1}`, path: `/crafts/Craft-${index + 1}` } };
  });
  return { ...node, crafts };
}

test("the learning kinds have one renderer each", () => {
  for (const kind of ["quiz", "compare", "concept_graph"] as const) expect(BLOCK_RENDERERS[kind]).toBeDefined();
});

test("quiz options are offered in alphabetical order, so the key is not given away by its place", () => {
  const [first, second, third] = quiz().questions;
  expect(optionOrder(first.options)).toEqual([0, 2, 1]);
  expect(optionOrder(second.options)).toEqual([1, 0, 2]);
  expect(optionOrder(third.options)).toEqual([1, 2, 0]);
  expect(promptParts(first.prompt)).toEqual(["", " is used as a mordant to fasten the colours."]);
  expect(promptParts("Kut is black.")).toBeNull();
});

test("an unanswered quiz shows each blanked prompt and its options, and hides every answer and citation", () => {
  const html = withReading(createElement(QuizView, { block: quiz(), reduce: false }));
  expect(attribute(html, "quiz-question", "data-answered")).toEqual(["false", "false", "false"]);
  expect(attribute(html, "quiz-blank", "data-testid")).toHaveLength(3);
  expect(attribute(html, "quiz-option", "data-mark")).toEqual(Array(9).fill("open"));
  expect([...html.matchAll(/data-testid="quiz-option"[^>]*><span[^>]*>([^<]+)</g)].map((found) => found[1])).toEqual([
    "Alum",
    "Indigo",
    "Kut",
    "gach",
    "kut",
    "tapano",
    "alizarin",
    "alum",
    "indigo"
  ]);
  expect(text(html)).toContain("Question 1 of 3");
  expect(text(html)).toContain(" is used as a mordant to fasten the colours.");
  expect(text(html)).not.toContain("Alum is used as a mordant");
  expect(html).not.toContain('data-testid="quiz-reveal"');
  expect(html).not.toContain('data-testid="citation-chip"');
  expect(html).not.toContain('data-testid="quiz-again"');
  expect(text(html)).toContain("3 questions");
});

test("an answered question marks the key and a wrong pick, then reveals the keyed sentence with its citation", () => {
  const block = quiz();
  const html = withReading(createElement(QuizView, { block, reduce: true, initialPicks: [0, 1, null] }));
  expect(attribute(html, "quiz-question", "data-answered")).toEqual(["true", "true", "false"]);
  expect(attribute(html, "quiz-option", "data-mark")).toEqual(["right", "other", "other", "wrong", "right", "other", "open", "open", "open"]);
  expect(attribute(html, "quiz-reveal", "data-right")).toEqual(["true", "false"]);
  expect(text(html)).toContain("Right.");
  expect(text(html)).toContain("Not quite. It is kut.");
  expect(text(html)).toContain(block.questions[0].options[0].sentence.text);
  expect(text(html)).toContain(block.questions[1].options[0].sentence.text);
  expect(text(html)).not.toContain(block.questions[1].options[1].sentence.text);
  expect(html.match(/data-testid="citation-chip"/g)).toHaveLength(2);
  expect(attribute(html, "quiz-reveal", "style").filter((style) => style.includes("opacity:0"))).toEqual([]);
  expect(text(html)).toContain("1 of 2 right · 1 to go");
  expect(text(html)).toContain(", right answer");
  expect(text(html)).toContain(", your answer");
});

test("a finished quiz states its score and offers to start again; a question takes only its first pick", () => {
  const block = quiz();
  const done = withReading(createElement(QuizView, { block, reduce: false, initialPicks: [0, 1, 0] }));
  expect(text(done)).toContain("2 of 3 right");
  expect(text(done)).not.toContain("to go");
  expect(done).toContain('data-testid="quiz-again"');
  expect(attribute(done, "quiz-reveal", "data-right")).toEqual(["true", "false", "true"]);
  expect(done).not.toContain("opacity:0");
  expect(quizScore(block.questions, [0, 1, 0])).toEqual({ right: 2, answered: 3, total: 3 });
  expect(picked([0, null, null], 0, 2)).toEqual([0, null, null]);
  expect(picked([0, null, null], 1, 2)).toEqual([0, 2, null]);
  expect(scoreText({ right: 0, answered: 0, total: 1 })).toBe("1 question");
});

test("compare sets the crafts side by side by facet, linked by name, and leaves an empty cell as a dash", () => {
  const block = compare();
  const html = withReading(createElement(CompareTable, { block }));
  expect(html).toContain('role="table"');
  expect(html).toContain('aria-label="Kutch Ajrakh and Bagru Hand Block Print compared"');
  expect(html).toContain('href="/crafts/Kutch-Ajrakh"');
  expect(html).toContain('href="/crafts/Bagru-Hand-Block-Print"');
  expect(html.match(/role="columnheader"/g)).toHaveLength(3);
  expect(html).toContain('role="columnheader" class="min-w-0"><span class="sr-only">Aspect</span>');
  expect(attribute(html, "compare-row", "data-testid")).toHaveLength(5);
  expect(attribute(html, "compare-cell", "data-filled")).toEqual(Array(10).fill("true"));
  expect(block.rows.map((row) => rowTitle(row))).toEqual([
    { title: "Alum", facet: "Materials" },
    { title: "Indigo", facet: "Materials" },
    { title: "Geography and water", facet: null },
    { title: "History", facet: null },
    { title: "Economics", facet: null }
  ]);
  for (const row of block.rows) for (const cell of row.cells) expect(text(html)).toContain(cell!.sentence.text);

  const emptied = { ...block, rows: [{ ...block.rows[0], cells: [block.rows[0].cells[0], null] }] };
  const empty = withReading(createElement(CompareTable, { block: emptied }));
  expect(attribute(empty, "compare-cell", "data-filled")).toEqual(["true", "false"]);
  expect(text(empty)).toContain("Not stated");
});

test("compare stacks on a phone and goes side by side where its columns fit", () => {
  expect(compareLayout(2).row).toContain("sm:grid-cols-[minmax(0,8rem)_repeat(2,minmax(0,1fr))]");
  expect(compareLayout(3).row).toContain("md:grid-cols-[minmax(0,8rem)_repeat(3,minmax(0,1fr))]");
  expect(compareLayout(4).row).toContain("lg:grid-cols-[minmax(0,8rem)_repeat(4,minmax(0,1fr))]");
  for (const count of [2, 3, 4]) expect(compareLayout(count).row.startsWith("grid min-w-0 grid-cols-[minmax(0,1fr)]")).toBe(true);
  expect(compareLayout(2).head).toContain("max-sm:sr-only");
  expect(() => compareLayout(5)).toThrow(RangeError);
});

test("the concept graph draws its term at the hub with each sharing craft around it, the asked craft marked", () => {
  const block = graph();
  expect(ringPoints(4)).toEqual([
    { x: 50, y: 14 },
    { x: 84, y: 50 },
    { x: 50, y: 86 },
    { x: 16, y: 50 }
  ]);
  const html = withReading(createElement(ConceptGraphView, { focus: block.focus, nodes: block.nodes, reduce: true }));
  expect(attribute(html, "concept-graph", "data-concept")).toEqual(["alum"]);
  expect(text(html)).toContain("Alum · 4");
  expect(text(html)).toContain("Indigo · 5");
  expect(html).toMatch(/aria-pressed="true"[^>]*>Alum · 4</);
  expect(html).toContain('aria-label="Alum is shared by Kutch Ajrakh, Bagru Hand Block Print, Machilipatnam Kalamkari and Sanganeri Hand Block Printing"');
  expect(attribute(html, "concept-craft-node", "data-focus")).toEqual(["true", "false", "false", "false"]);
  expect(attribute(html, "concept-spoke", "data-testid")).toHaveLength(4);
  expect(attribute(html, "concept-list-craft", "data-focus")).toEqual(["true", "false", "false", "false"]);
  expect(attribute(html, "concept-craft-node", "tabindex")).toEqual(["-1", "-1", "-1", "-1"]);
  expect(html).toContain('href="/crafts/Machilipatnam-Kalamkari"');
  expect(html.match(/data-testid="citation-chip"/g)).toHaveLength(4);
  expect(html).not.toContain("opacity:0");
  expect(html).not.toContain('data-testid="concept-show-all"');

  const indigo = withReading(createElement(ConceptGraphView, { focus: block.focus, nodes: block.nodes, reduce: false, initialTermKey: "indigo" }));
  expect(attribute(indigo, "concept-list-craft", "data-testid")).toHaveLength(5);
  expect(indigo).not.toContain("opacity:0");
});

test("labels that touch on a crowded ring are pushed apart by their measured boxes, the hub stays put and nothing leaves the frame", () => {
  const frame = { width: 300, height: 300 };
  expect(separatedLabels([{ x: 100, y: 100, width: 80, height: 20 }, { x: 130, y: 100, width: 80, height: 20 }], frame)).toEqual([
    { x: 100, y: 87 },
    { x: 130, y: 113 }
  ]);
  expect(separatedLabels([{ x: 150, y: 150, width: 100, height: 30, fixed: true }, { x: 160, y: 160, width: 80, height: 20 }], frame)).toEqual([
    { x: 150, y: 150 },
    { x: 160, y: 181 }
  ]);
  expect(separatedLabels([{ x: 40, y: 100, width: 60, height: 20 }, { x: 260, y: 100, width: 60, height: 20 }], frame)).toEqual([
    { x: 40, y: 100 },
    { x: 260, y: 100 }
  ]);
  expect(separatedLabels([{ x: 100, y: 285, width: 80, height: 30 }, { x: 110, y: 290, width: 80, height: 30 }], frame)).toEqual([
    { x: 100, y: 249 },
    { x: 110, y: 285 }
  ]);
  expect(LABEL_GAP_PX).toBe(6);
});

test("a concept shared by many crafts draws seven and a count, and lists six with a way to all of them", () => {
  const block = graph();
  const node = widened(block.nodes[0], 10);
  const layout = graphLayout(node, AJRAKH);
  expect(layout.crafts.map((craft) => craft.entry.craft.name)).toEqual(["Craft 1", "Craft 2", "Craft 3", "Craft 4", "Craft 5", "Craft 6", "Craft 7"]);
  expect(layout.more?.count).toBe(3);
  expect(graphSummary(node)).toContain("Craft 9 and Craft 10");
  const html = withReading(createElement(ConceptGraphView, { focus: null, nodes: [node], reduce: true }));
  expect(html).not.toContain('data-testid="concept-choice"');
  expect(text(html)).toContain("+3");
  expect(attribute(html, "concept-list-craft", "data-testid")).toHaveLength(6);
  expect(text(html)).toContain("Show all 10");
  expect(withReading(createElement(ConceptGraphView, { focus: null, nodes: [], reduce: true }))).toBe("");
});

test("every phase D block joins the answer's one numbering in the order the server lists its sources", () => {
  const sections = PHASE_D.sections.map((section, index) => ({
    id: section.id,
    discipline: section.discipline,
    title: section.id,
    order: index + 1,
    state: "READY",
    searched: null,
    blocks: section.blocks.map((block) => phaseDBlock(block.kind as never, block.id))
  })) as unknown as SectionView[];
  expect([...explainerSourceNumbers(sections).keys()]).toEqual(PHASE_D.sources.map((source) => source.id));
});

test("learning renderers lay out in shrinkable columns so nothing widens a phone page", () => {
  const block = graph();
  const html = [
    withReading(createElement(QuizView, { block: quiz(), reduce: false, initialPicks: [0, 1, null] })),
    withReading(createElement(CompareTable, { block: compare() })),
    withReading(createElement(ConceptGraphView, { focus: block.focus, nodes: block.nodes, reduce: false }))
  ].join("");
  const tracks = gridTracks(html);
  expect(tracks.length).toBeGreaterThan(0);
  for (const track of tracks) expect(track).toMatch(SHRINKABLE_TRACK);
  expect(html).not.toMatch(FIXED_WIDE_WIDTH);
  expect(html.match(/class="[^"]*\bmin-w-0\b/g)?.length ?? 0).toBeGreaterThan(10);
});
