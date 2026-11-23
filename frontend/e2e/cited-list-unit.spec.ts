import { expect, test } from "@playwright/test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { FIELD_CHAPTER } from "../components/landing/fieldHoldings";
import { MonographChapter } from "../components/monograph/MonographChapters";
import { DISCIPLINES, type Discipline } from "../lib/explainerBlockBase";
import type { MonographDocument, MonographNode, MonographQuote, MonographUnit } from "../lib/monographDocument";
import { pagePlan, type ChapterPlan } from "../lib/monographRenderLayout";
import { kitCites } from "../lib/monographRenderKit";

const CLOSED_FIELD: Discipline = "HEALTH";
const CHAPTERS = ["glance", "made", "chem", "why", "history", "market", "people"];
const LIST_OPEN = '<div class="mt-4 mb-6"><ul class="kv-list border-t border-rule">';
const ITEM_OPEN = '<li class="border-b border-rule py-3 font-reading text-body-sm text-ink-1"><span class="s">';

const factText = (field: Discipline) => `A contributed ${field.toLowerCase()} fact about the printed cloth.`;
const factStart = (field: Discipline) => `${ITEM_OPEN}A contributed ${field.toLowerCase()} fact `;
const proseText = (chapter: string) => `The curated ${chapter} sentence about the printed cloth.`;
const factRef = (field: Discipline) => `fact-${field.toLowerCase()}-0000000000${DISCIPLINES.indexOf(field) + 10}`;

function cited(text: string, key: string, source: string): MonographNode {
  const at = text.lastIndexOf(" ");
  return { m: "s", c: [text.slice(0, at + 1), { m: "cite", key, g: [source], c: [text.slice(at + 1)] }] };
}

function unit(chapter: string, tag: string, field: string | null, nodes: MonographNode[], claimIds: string[] = []): MonographUnit {
  return { chapter, tag, field, nodes, claimIds };
}

function chapterUnits(chapter: string): Record<string, MonographUnit> {
  const units: Record<string, MonographUnit> = {
    [`chapter-${chapter}`]: unit(chapter, "h2", null, [`The ${chapter} chapter`]),
    [`${chapter}-prose`]: unit(chapter, "p", "OVERVIEW", [cited(proseText(chapter), `${chapter}-prose`, "g1")], [`curated-${chapter}`])
  };
  for (const field of DISCIPLINES.filter((found) => FIELD_CHAPTER[found] === chapter)) {
    const source = field === CLOSED_FIELD ? "g2" : "g1";
    units[factRef(field)] = unit(chapter, "li", field, [cited(factText(field), factRef(field), source)], [`claim-${field}`]);
  }
  return units;
}

function citations(units: Record<string, MonographUnit>): Record<string, MonographQuote[]> {
  return Object.fromEntries(
    Object.entries(units).map(([ref, found]) => {
      const closed = found.field === CLOSED_FIELD && found.tag === "li";
      return [ref, [closed ? { source: "g2", locator: "p. 4", quote: null } : { source: "g1", locator: "p. 2", quote: "The cloth is printed by hand." }]];
    })
  );
}

function curatedDocument(): MonographDocument {
  const opening = {
    "masthead-kicker": unit("opening", "p", "OVERVIEW", [{ m: "span", c: ["Monograph"] }]),
    "masthead-title": unit("opening", "h1", "OVERVIEW", ["Test Print"])
  };
  const units = Object.assign({}, ...CHAPTERS.map(chapterUnits)) as Record<string, MonographUnit>;
  const claimed = Object.fromEntries(Object.entries(units).filter(([, found]) => found.claimIds.length > 0));
  return {
    schemaVersion: 1,
    subjectKind: "craft",
    subjectSlug: "Test-Print",
    language: "en",
    title: "Test Print",
    version: 16,
    pageUrl: "https://kalavigyan.example/crafts/Test-Print",
    shell: null,
    content: {
      schemaVersion: 1,
      craftSlug: "Test-Print",
      sources: {
        g1: { number: 1, title: "An open survey", fullTitle: null, publisher: null, year: 2020, grade: "A", url: "https://example.org/survey", extra: null, dossierSourceId: null },
        g2: { number: 2, title: "A closed monograph", fullTitle: null, publisher: null, year: 2007, grade: "B", url: null, extra: null, dossierSourceId: null }
      },
      citations: citations(claimed),
      citationClaims: {},
      data: {},
      units: { ...opening, ...units },
      components: [],
      layout: [...Object.keys(opening), ...Object.keys(units)].map((ref) => ({ chapter: ref.startsWith("masthead") ? "opening" : units[ref].chapter, kind: "unit" as const, ref, within: null }))
    },
    specs: {},
    fragments: {}
  };
}

function drawn(document: MonographDocument, chapter: ChapterPlan): string {
  return renderToStaticMarkup(createElement(MonographChapter, { document, chapter, masthead: null }));
}

function listedFields(html: string): Discipline[] {
  const list = html.indexOf(LIST_OPEN);
  const shown = DISCIPLINES.filter((field) => list >= 0 && html.indexOf(factStart(field)) > list);
  return shown.sort((a, b) => html.indexOf(factStart(a)) - html.indexOf(factStart(b)));
}

test("a curated chapter draws each field's listed facts as one cited list after its prose", () => {
  const document = curatedDocument();
  const chapters = pagePlan(document).chapters.filter((chapter) => CHAPTERS.includes(chapter.key));
  const listed = Object.fromEntries(chapters.map((chapter) => [chapter.key, drawn(document, chapter)]));
  for (const [chapter, html] of Object.entries(listed)) {
    expect(html.indexOf(LIST_OPEN)).toBeGreaterThan(html.indexOf(proseText(chapter).slice(0, 30)));
    expect(html.match(/<ul /g)).toHaveLength(1);
  }
  expect(Object.fromEntries(Object.entries(listed).map(([chapter, html]) => [chapter, listedFields(html)]))).toEqual({
    glance: ["OVERVIEW"],
    made: ["PROCESS", "MATERIALS", "HEALTH"],
    chem: ["CHEMISTRY", "PHYSICS", "BOTANY"],
    why: ["GEOGRAPHY", "GEOLOGY", "CLIMATE", "ECOLOGY"],
    history: ["HISTORY"],
    market: ["ECONOMICS", "POLICY"],
    people: ["DESIGN", "SOCIETY"]
  });
});

test("a listed fact keeps its citation cluster, and a closed source's citation carries no quote", () => {
  const document = curatedDocument();
  const made = pagePlan(document).chapters.find((chapter) => chapter.key === "made");
  expect(made).toBeDefined();
  const html = drawn(document, made!);
  const health = html.slice(html.indexOf(factStart(CLOSED_FIELD)) + ITEM_OPEN.length);
  expect(health).toMatch(/^[^<]*<span class="nw">cloth\.<button class="kcite" type="button" data-c="fact-health-[0-9]+" data-g="g2" aria-haspopup="dialog" aria-expanded="false" aria-label="Source 2"/);
  expect(kitCites(document.content).c[factRef(CLOSED_FIELD)]).toEqual([["g2", "p. 4", null]]);
  expect(kitCites(document.content).c[factRef("PROCESS")]).toEqual([["g1", "p. 2", "The cloth is printed by hand."]]);
});
