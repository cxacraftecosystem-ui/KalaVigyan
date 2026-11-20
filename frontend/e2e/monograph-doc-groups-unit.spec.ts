import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";
import { createElement, type ReactElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { AuthProvider } from "../components/AuthProvider";
import { MonographPage } from "../components/monograph/MonographPage";
import { sentenceCased } from "../components/monograph/TermGroups";
import { ThemeProvider } from "../components/ThemeProvider";
import type { MonographDocument, MonographNode, MonographUnit } from "../lib/monographDocument";
import { placedMastheadPicture } from "../lib/monographPlacement";
import { pagePlan, passageSegments, termGroup, termRows, type Passage } from "../lib/monographRenderLayout";

import { generatedDocument, HERO } from "./generatedMonographFixture";

const unit = (chapter: string, tag: string, nodes: MonographNode[]): MonographUnit => ({ chapter, tag, field: null, nodes, claimIds: [] });
const cited = (text: string, last: string, key: string): MonographNode => ({ m: "s", c: [text, { m: "cite", key, g: ["g1"], c: [last] }] });
const at = (chapter: string, ref: string) => ({ chapter, kind: "unit" as const, ref, within: null });
const provided = (element: ReactElement) => renderToStaticMarkup(createElement(AuthProvider, null, createElement(ThemeProvider, null, element)));

const GLANCE: Record<string, MonographUnit> = {
  "chapter-glance": unit("glance", "h2", ["At a glance"]),
  "f1-t": unit("glance", "dt", ["Centres"]),
  "f1-v": unit("glance", "dd", [cited("Bagh and ", "Dhar", "f1-v")]),
  "f2-t": unit("glance", "dt", ["Colours"]),
  "f2-v": unit("glance", "dd", [cited("Red and ", "black", "f2-v")]),
  "differ-h": unit("glance", "h3", ["Where the sources differ"]),
  "d1-t": unit("glance", "dt", ["whether the river water matters to the red"]),
  "d1-a": unit("glance", "dd", [cited("The survey says the river's minerals brighten the ", "red.", "d1-a")]),
  "d1-b": unit("glance", "dd", [cited("A later study finds no difference in the ", "red.", "d1-b")]),
  "record-h": unit("glance", "h3", ["In the record"]),
  "r1-t": unit("glance", "dt", ["1962"]),
  "r1-v": unit("glance", "dd", [cited("The first printers settled at ", "Bagh.", "r1-v")]),
  "people-h": unit("glance", "h3", ["Communities"]),
  "c1-t": unit("glance", "dt", ["Khatri"]),
  "c1-a": unit("glance", "dd", [cited("The Khatri printers came from ", "Sindh.", "c1-a")]),
  "c1-b": unit("glance", "dd", [cited("They print with wooden ", "blocks.", "c1-b")])
};

function groupedDocument(): MonographDocument {
  const document = generatedDocument();
  Object.assign(document.content.units, GLANCE);
  const opening = document.content.layout.filter((entry) => entry.chapter === "opening");
  const rest = document.content.layout.filter((entry) => entry.chapter !== "opening");
  document.content.layout = [...opening, ...Object.keys(GLANCE).map((ref) => at("glance", ref)), ...rest];
  return document;
}

test("a run of terms is drawn by what it holds: single facts as a grid, the record as a strip, disagreements and entries", () => {
  const units = groupedDocument().content.units;
  expect(termGroup(units, ["f1-t", "f1-v", "f2-t", "f2-v"], null)).toBe("facts");
  expect(termGroup(units, ["d1-t", "d1-a", "d1-b"], "Where the sources differ")).toBe("differ");
  expect(termGroup(units, ["r1-t", "r1-v"], "In the record")).toBe("record");
  expect(termGroup(units, ["c1-t", "c1-a", "c1-b"], "Communities")).toBe("entries");
  expect(termGroup(units, ["c1-t", "c1-a", "c1-b"], null)).toBe("entries");
  expect(termRows(units, ["d1-t", "d1-a", "d1-b", "f1-t", "f1-v"])).toEqual([
    { term: "d1-t", values: ["d1-a", "d1-b"] },
    { term: "f1-t", values: ["f1-v"] }
  ]);
  expect(termRows(units, ["f1-v", "f2-t", "f2-v"])).toEqual([
    { term: null, values: ["f1-v"] },
    { term: "f2-t", values: ["f2-v"] }
  ]);
});

test("a chapter's heading stays in the reading column and each group takes its own heading out to the full width", () => {
  const glance = pagePlan(groupedDocument()).chapters.find((chapter) => chapter.key === "glance")!;
  const passage = glance.blocks[0] as Passage;
  expect(passageSegments(passage.pieces).map((segment) => (segment.kind === "group" ? `${segment.piece.group}:${segment.piece.heading}` : "column"))).toEqual([
    "column",
    "facts:null",
    "differ:differ-h",
    "record:record-h",
    "entries:people-h"
  ]);
});

test("the curated page draws the board's fact grid, record strip, cited disagreements and entries", () => {
  const html = provided(createElement(MonographPage, { document: groupedDocument() }));
  expect(html).toContain('<div class="kv-group" data-group="facts"><dl class="glance"><div><dt>Centres</dt><dd>');
  expect(html).toContain('<h3 class="kv-group-h">In the record</h3><ol class="rec-list"><li><p class="rec-when">1962</p><p class="rec-text">');
  expect(html).toContain('<div class="kv-differs"><section class="kv-differ-item"><h4 class="kv-differ-topic">Whether the river water matters to the red</h4>');
  expect(html.match(/class="kv-differ-item"[\s\S]*?<\/section>/)?.[0].match(/<p>/g)).toHaveLength(2);
  expect(html).toContain('<section class="kv-entry"><h4 class="kv-entry-name">Khatri</h4>');
  expect(html).not.toContain("kv-terms");
});

test("a curated page's rail follows its masthead and lede, and the masthead keeps the app's own styles", () => {
  const html = provided(createElement(MonographPage, { document: groupedDocument() }));
  expect(html.indexOf('class="kv-rail"')).toBeGreaterThan(html.indexOf('class="kv-page kv-doc-open" data-app=""'));
  expect(html.indexOf('class="kv-rail"')).toBeLessThan(html.indexOf('id="glance"'));
  expect(html.indexOf('class="kv-rail"')).toBeGreaterThan(html.indexOf('id="kv-main"'));
  expect(html.match(/class="kv-rail"/g)).toHaveLength(1);
});

test("a disagreement's topic reads in sentence case without touching a name or a capital", () => {
  expect(sentenceCased(["whether Dhokra is the local name"])).toEqual(["Whether Dhokra is the local name"]);
  expect(sentenceCased(["Which colours are traditional"])).toEqual(["Which colours are traditional"]);
  expect(sentenceCased([{ m: "i", c: ["kut"] }, " ferments"])).toEqual([{ m: "i", c: ["kut"] }, " ferments"]);
});

test("a placed masthead or opener photograph comes to the masthead when the opening holds none", () => {
  const document = generatedDocument();
  expect(placedMastheadPicture(document)).toBeNull();
  document.content.layout = document.content.layout.map((entry) => (entry.ref === HERO || entry.within === HERO ? { ...entry, chapter: "chem" } : entry));
  document.content.data["page-layout"] = { entries: [{ ref: HERO, chapter: "chem", order: 1, role: "OPENER" }, { ref: "other/pictures/i09", chapter: "chem", order: 2, role: "HERO" }] };
  expect(placedMastheadPicture(document)).toBe(HERO);
  const plan = pagePlan(document);
  expect(plan.label?.picture).toBe(HERO);
  expect(plan.chapters.find((chapter) => chapter.key === "chem")?.blocks.some((block) => block.kind === "component" && block.label === HERO)).toBe(false);
  document.content.data["page-layout"] = { entries: [{ ref: HERO, chapter: "chem", order: 1, role: "PLATE" }] };
  expect(placedMastheadPicture(document)).toBeNull();
});

test("inside the authored shell an SVG drawing and an app-drawn region keep their own attributes and styles", () => {
  const css = readFileSync(join(__dirname, "..", "components", "monograph", "authoredShell.css"), "utf8");
  const reverts = css.slice(css.indexOf("@layer kv-shell"));
  expect(reverts.match(/svg \*\)\)/g)).toHaveLength(4);
  expect(reverts).toContain("*:where(:not(svg *))");
  expect(css.match(/\[data-app\], \[data-app\] \*/g)?.length).toBeGreaterThanOrEqual(20);
});
