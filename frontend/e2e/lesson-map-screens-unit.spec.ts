import { expect, test } from "@playwright/test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import type { CitationLookup } from "@/components/answer/CitationContext";
import { CompareTable } from "@/components/answer/learning/CompareTable";
import { ComparePicker } from "@/components/learn/ComparePicker";
import { LessonBuilder } from "@/components/learn/LessonBuilder";
import { LessonList } from "@/components/learn/LessonList";
import { LessonPackView } from "@/components/learn/LessonPackView";
import { SlidePreview } from "@/components/learn/SlidePreview";
import { DistrictView } from "@/components/map/DistrictView";
import { listedSourceNumbers } from "@/lib/citations";
import { comparable, compareHref, comparedSlugs } from "@/lib/comparePage";
import { craftComparisonShape } from "@/lib/compareContract";
import { districtCraftsShape, type DistrictCrafts } from "@/lib/districtCraftsContract";
import { craftsHeading, districtTitle } from "@/lib/districtView";
import type { Explainer } from "@/lib/explainerContract";
import { explainerHistoryShape } from "@/lib/learningContract";
import { lessonListShape, lessonPackShape } from "@/lib/lessonContract";
import { chosenInOrder, lessonRequest, lessonSections, LESSON_SECTIONS_MAX, slideCountText } from "@/lib/lessonView";
import { inListedOrder, moveItem, movedText, usableAfterMove } from "@/lib/listOrder";
import { canAccessRoute, routeGuardFor } from "@/lib/permissions";
import { parseShape } from "@/lib/shape";
import type { SourceRef, User, UserRole } from "@/lib/types";

import { attribute, FIXED_WIDE_WIDTH, gridTracks, shownText, SHRINKABLE_TRACK, withApp, withReading } from "./explainerRender";
import { readRepo } from "./phaseBFixture";

type Golden = Record<string, unknown>;

const golden = (name: string): Golden => JSON.parse(readRepo("shared", name)) as Golden;
const LESSON = golden("learning.lesson.golden.json");
const PACK = parseShape(lessonPackShape, LESSON.pack);
const LIST = parseShape(lessonListShape, LESSON.list);
const FIRST = golden("explainer.document.golden.json") as unknown as Explainer;
const HISTORY = parseShape(explainerHistoryShape, golden("learning.versions.golden.json").history);
const DISTRICT = parseShape(districtCraftsShape, golden("map.district-crafts.golden.json"));
const COMPARISON = parseShape(craftComparisonShape, golden("learning.compare.golden.json"));
const FIRST_DOCUMENT = { schemaVersion: 1 as const, mark: HISTORY.versions[0], explainer: FIRST };
const BAGRU = { slug: "Bagru-Hand-Block-Print", name: "Bagru Hand Block Print", path: "/crafts/Bagru-Hand-Block-Print" };
const person = (role: UserRole): User => ({ id: role, email: `${role}@example.org`, name: role, role });

function text(html: string): string {
  return shownText(html.replace(/<[^>]+>/g, ""));
}

function lookupOf(sources: readonly SourceRef[]): CitationLookup {
  return { numbers: listedSourceNumbers(sources), sourcesById: new Map(sources.map((source) => [source.id, source])) };
}

const NARROW_TRACK = /^(auto|[0-3](\.\d+)?rem)$/;

function fitsAPhone(html: string) {
  expect(gridTracks(html).filter((track) => !NARROW_TRACK.test(track) && !SHRINKABLE_TRACK.test(track))).toEqual([]);
  expect(html).not.toMatch(FIXED_WIDE_WIDTH);
}

test("a lesson offers the version's finished sections and asks exactly as the contract's request", () => {
  const sections = lessonSections(FIRST);
  expect(sections.map((section) => [section.id, section.title])).toEqual([
    ["s1", "How it is made"],
    ["s2", "Why the water matters"],
    ["s3", "The chemistry of the colours"]
  ]);
  const ref = { explainerId: FIRST_DOCUMENT.mark.explainerId, version: 1 };
  expect(lessonRequest(ref, "  ", ["s1", "s2", "s3"], true)).toEqual(LESSON.request);
  expect(lessonRequest(ref, "Ajrakh in a week", ["s2"], false)).toEqual({ ...ref, title: "Ajrakh in a week", sectionIds: ["s2"], quiz: false });
  expect(lessonRequest(ref, "", [], true)).toBeNull();
  expect(lessonRequest(ref, "", ["s1", "s1"], true)).toBeNull();
  expect(lessonRequest(ref, "", Array.from({ length: LESSON_SECTIONS_MAX + 1 }, (_, index) => `s${index + 1}`), true)).toBeNull();
});

test("the lesson builder starts with every finished section chosen and the quiz on", () => {
  const html = withApp(createElement(LessonBuilder, { document: FIRST_DOCUMENT, onBuilt: () => undefined }));
  expect(attribute(html, "lesson-section", "data-chosen")).toEqual(["true", "true", "true"]);
  expect(html).toContain(`placeholder="${FIRST.question}"`);
  expect(text(html)).toContain("Sections · 3 chosen");
  expect(html).toMatch(/role="switch"[^>]*aria-checked="true"/);
  expect(html).not.toMatch(/data-testid="lesson-build"[^>]*disabled/);
  fitsAPhone(html);
});

test("the lesson builder's rows move up and down, and the lesson asks for its sections in the reader's order", () => {
  const html = withApp(createElement(LessonBuilder, { document: FIRST_DOCUMENT, onBuilt: () => undefined }));
  expect(html.match(/aria-label="Move [^"]+ (?:up|down)"/g)).toEqual([
    'aria-label="Move How it is made up"',
    'aria-label="Move How it is made down"',
    'aria-label="Move Why the water matters up"',
    'aria-label="Move Why the water matters down"',
    'aria-label="Move The chemistry of the colours up"',
    'aria-label="Move The chemistry of the colours down"'
  ]);
  expect(html.match(/<button[^>]*data-testid="move-(?:up|down)"[^>]*>/g)?.map((button) => button.includes("disabled"))).toEqual([true, false, false, false, false, true]);
  expect(html).toContain('aria-live="polite"');
  const sections = lessonSections(FIRST);
  const ids = moveItem(sections.map((section) => section.id), 2, 0);
  expect(ids).toEqual(["s3", "s1", "s2"]);
  const ordered = inListedOrder(sections, ids);
  expect(chosenInOrder(ordered, new Set(["s1", "s3"]))).toEqual(["s3", "s1"]);
  const ref = { explainerId: FIRST_DOCUMENT.mark.explainerId, version: 1 };
  expect(lessonRequest(ref, "", chosenInOrder(ordered, new Set(["s1", "s3"])), true)?.sectionIds).toEqual(["s3", "s1"]);
  expect(inListedOrder(sections, ["s2"]).map((section) => section.id)).toEqual(["s2", "s1", "s3"]);
  expect([usableAfterMove(2, 0, 3), usableAfterMove(0, 2, 3), usableAfterMove(0, 1, 3), usableAfterMove(2, 1, 3)]).toEqual(["down", "up", "down", "up"]);
  expect(movedText("Why the water matters", 0, 3)).toBe("Why the water matters moved to position 1 of 3.");
  expect(moveItem(["a", "b"], 0, 5)).toEqual(["a", "b"]);
});

test("a built pack previews its slides in order with the picture, quiz, reading list and files", () => {
  const html = withApp(createElement(LessonPackView, { pack: PACK }), lookupOf(PACK.sources));
  expect(attribute(html, "slide", "data-kind")).toEqual(["TITLE", "SECTION", "SECTION", "SECTION", "SECTION", ...Array<string>(9).fill("QUIZ"), "READING", "SOURCES"]);
  expect(text(html)).toContain("Slide 1 of 16");
  expect(html.match(/data-display="INLINE"/g)).toHaveLength(1);
  expect(text(html)).toContain(PACK.quiz!.questions[0].prompt);
  expect(attribute(html, "reading-item", "data-testid")).toHaveLength(PACK.readingList.length);
  expect(text(html)).toContain("Cited 40 times");
  expect(attribute(html, "lesson-files", "data-testid")).toHaveLength(1);
  expect([...html.matchAll(/data-format="([a-z]+)"/g)].map((found) => found[1])).toEqual(["pptx", "pdf", "html"]);
  expect(html).toContain('data-testid="citation-menu"');
  expect(text(html)).toContain(slideCountText(16));
  fitsAPhone(html);
});

test("slides are drawn finished at first paint, with no rise-in", () => {
  const html = withApp(createElement(SlidePreview, { pack: PACK }), lookupOf(PACK.sources));
  expect(attribute(html, "slide", "data-kind")).toHaveLength(16);
  expect(html).not.toMatch(/translateY|opacity:\s*0/);
});

test("the lesson list shows each pack and a way forward when there is none", () => {
  const html = renderToStaticMarkup(createElement(LessonList, { lessons: LIST.items, busy: null, onDelete: () => undefined }));
  expect(attribute(html, "lesson-row", "data-testid")).toHaveLength(1);
  expect(text(html)).toContain("16 slides");
  expect(html).toContain(`href="/lessons/${PACK.id}"`);
  const none = renderToStaticMarkup(createElement(LessonList, { lessons: [], busy: null, onDelete: () => undefined }));
  expect(text(none)).toContain("Your lessons");
  expect(text(none)).not.toMatch(/no lessons|yet/i);
  expect(none).toContain('href="/saved"');
});

test("the lesson routes are a professor's, as the server's BUILD_LESSONS is", () => {
  expect(routeGuardFor("/lessons/new")?.gate).toBe("require(BUILD_LESSONS)");
  const roles: UserRole[] = ["STUDENT", "RESEARCHER", "PROFESSOR", "ADMIN", "MASTER_ADMIN"];
  expect(roles.map((role) => canAccessRoute(person(role), `/lessons/${PACK.id}`))).toEqual([false, false, true, true, true]);
  expect(canAccessRoute(person("STUDENT"), "/saved")).toBe(true);
});

test("a tapped district shows its cited crafts, the stored land story, its values and every credit", () => {
  const html = withApp(createElement(DistrictView, { district: DISTRICT, reduce: true, onClose: () => undefined }), lookupOf(DISTRICT.sources));
  expect(districtTitle(DISTRICT.district)).toBe("Kachchh, Gujarat");
  expect(text(html)).toContain("Kachchh, Gujarat");
  expect(text(html)).toContain(craftsHeading(1));
  expect(craftsHeading(1)).toBe("Craft practised here · 1");
  expect(craftsHeading(3)).toBe("Crafts practised here · 3");
  expect(attribute(html, "district-craft", "data-testid")).toHaveLength(1);
  expect(html).toContain('href="/crafts/Kutch-Ajrakh"');
  expect(text(html)).toContain("Practised");
  expect(text(html)).toContain("[1]");
  const basis = /<p[^>]*data-testid="place-basis"[^>]*>[\s\S]*?<\/p>/.exec(html)?.[0] ?? "";
  expect(basis).toContain('<span class="kv-ev-tag" data-level="provisional" data-testid="evidence-tag">Provisional</span>');
  expect(basis).not.toMatch(/purple|ink-[579]00|font-display|font-bold|text-xs/);
  expect(attribute(html, "explainer-block", "data-kind")).toEqual(["region_story"]);
  expect(html).toContain('data-testid="reuse-marker"');
  for (const facet of ["SOIL", "CLIMATE", "TERRAIN"]) expect(html).toContain(`data-testid="region-facet-${facet}"`);
  expect(attribute(html, "dataset-credit", "data-testid").length).toBeGreaterThanOrEqual(DISTRICT.datasets.length);
  expect(text(html)).toContain(DISTRICT.boundaryCaption);
  expect(html).not.toContain("Compare these crafts");
  fitsAPhone(html);
});

test("a district with two crafts offers to compare them, and one with no land story shows its crafts alone", () => {
  const second = { ...DISTRICT.crafts[0], craft: BAGRU };
  const two: DistrictCrafts = { ...DISTRICT, crafts: [DISTRICT.crafts[0], second], land: null };
  const html = withApp(createElement(DistrictView, { district: two, reduce: true, onClose: () => undefined }), lookupOf(DISTRICT.sources));
  expect(html).toContain('href="/compare?crafts=Kutch-Ajrakh&amp;crafts=Bagru-Hand-Block-Print"');
  expect(html).not.toContain('data-testid="district-land"');
});

test("compare takes two to four different crafts and draws the comparison with its sources", () => {
  expect(comparedSlugs([" a ", "b", "a", "", "c", "d", "e"])).toEqual(["a", "b", "c", "d"]);
  expect([comparable(["a"]), comparable(["a", "b"]), comparable(["a", "a"]), comparable(["a", "b", "c", "d", "e"])]).toEqual([false, true, false, false]);
  expect(compareHref(["Kutch-Ajrakh", "Bagru-Hand-Block-Print"])).toBe("/compare?crafts=Kutch-Ajrakh&crafts=Bagru-Hand-Block-Print");
  expect(compareHref([])).toBe("/compare");
  const table = withReading(createElement(CompareTable, { block: COMPARISON.comparison }), lookupOf(COMPARISON.sources));
  expect(attribute(table, "compare", "data-crafts")).toEqual(["2"]);
  const shown = [...text(table).matchAll(/\[(\d+)\]/g)].map((found) => Number(found[1]));
  expect(shown.every((number) => number >= 1 && number <= COMPARISON.sources.length)).toBe(true);
});

test("the compare picker shows the chosen crafts with a way to remove each, and stops offering at four", () => {
  const options = [
    { value: "Kutch-Ajrakh", label: "Kutch Ajrakh" },
    { value: BAGRU.slug, label: BAGRU.name }
  ];
  const html = renderToStaticMarkup(createElement(ComparePicker, { slugs: ["Kutch-Ajrakh"], options, onChange: () => undefined }));
  expect(html).toContain('aria-label="Remove Kutch Ajrakh"');
  expect(text(html)).toContain("Add a craft");
  const full = renderToStaticMarkup(createElement(ComparePicker, { slugs: ["a", "b", "c", "d"], options, onChange: () => undefined }));
  expect(text(full)).not.toContain("Add a craft");
  expect(text(renderToStaticMarkup(createElement(ComparePicker, { slugs: [], options, onChange: () => undefined })))).toContain("Choose a craft");
});
