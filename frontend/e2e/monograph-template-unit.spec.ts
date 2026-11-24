import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test, type Page } from "@playwright/test";
import { createElement, type ReactElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { AuthProvider } from "../components/AuthProvider";
import { MonographPage } from "../components/monograph/MonographPage";
import { ThemeProvider } from "../components/ThemeProvider";
import type { MonographSource } from "../lib/monographDocument";
import { chapterNotes, chapterSections, spreadRuns } from "../lib/monographNotes";
import { pagePlan, type Passage } from "../lib/monographRenderLayout";
import { kindGroup, sourceGroups, sourceSplit } from "../lib/monographSources";

import { FRONTEND } from "./moduleGraph";
import { PRIMITIVE_CSS } from "./primitivesPage";
import { SECTION_TITLES, templateDocument, withoutKinds } from "./templateMonographFixture";

const KIT_CSS = readFileSync(join(FRONTEND, "public", "monographs", "kit", "monograph.css"), "utf8");
const PAGE_CSS = readFileSync(join(FRONTEND, "components", "monograph", "documentPage.css"), "utf8");
const KIT_JS = readFileSync(join(FRONTEND, "public", "monographs", "kit", "monograph.js"), "utf8");
const LAST_SECTION_OF_MADE = "made-made-print-h";
const WIDTHS = [360, 768, 1440] as const;
const THEMES = ["light", "dark"] as const;
const SPREAD_FROM = 1200;

const provided = (element: ReactElement) => renderToStaticMarkup(createElement(AuthProvider, null, createElement(ThemeProvider, null, element)));
const pageHtml = () => provided(createElement(MonographPage, { document: templateDocument() }));
const source = (kind: string | undefined, publisher: string | null): MonographSource => ({ number: 1, title: "A source", fullTitle: null, publisher, year: null, grade: "B", url: null, extra: null, dossierSourceId: null, kind });

function between(html: string, start: string, end: string): string {
  const from = html.indexOf(start);
  return from < 0 ? "" : html.slice(from, html.indexOf(end, from + start.length));
}

test("the masthead counts the page's own sources and, apart, the kin crafts' sources it links to", () => {
  const html = pageHtml();
  expect(sourceSplit(templateDocument())).toEqual({ own: ["g1", "g2", "g3", "g4", "g5"], kin: ["g6", "g7"] });
  expect(html).toContain('<span class="kv-prov-n">Drawn from 5 sources</span>');
  expect(html).toContain('aria-label="Reliability of the 5 sources: 2 graded A, 2 graded B, 1 graded C"');
  expect(html).toContain('<a class="kv-prov-k" href="#kv-src-kin">2 more for the kin crafts</a>');
  expect(html.match(/<h1/g)).toHaveLength(1);
});

test("the opening lists the numbered chapters as the approved table of contents does", () => {
  const toc = between(pageHtml(), '<nav class="toc kv-toc"', "</nav>");
  expect(toc).toContain('<p class="kicker">The monograph in five chapters</p>');
  expect(toc).toContain('<p class="kv-toc-d">Each opens the chapter of this page that tells it in full.</p>');
  expect([...toc.matchAll(/<a href="#([a-z]+)"><b>(\d)<\/b><span>([^<]+)<\/span><\/a>/g)].map((found) => [found[1], found[2], found[3]])).toEqual([
    ["glance", "1", "At a glance"],
    ["made", "2", "How it is made"],
    ["chem", "3", "The chemistry"],
    ["kin", "4", "Kin crafts and shared science"],
    ["sources", "5", "Sources"]
  ]);
});

test("each paragraph is its own spread with the sources it cites first in the chapter beside it", () => {
  const document = templateDocument();
  const made = pagePlan(document).chapters.find((chapter) => chapter.key === "made")!;
  const passage = made.blocks[0] as Passage;
  expect(spreadRuns(passage.pieces, document.content.units).map((run) => run.map((piece) => (piece.kind === "unit" ? piece.ref : piece.refs.join("+"))))).toEqual([
    ["chapter-made"],
    ["made-wash-h", "made-1+made-2"],
    ["made-print-h", "made-3"]
  ]);
  const notes = chapterNotes(document, made);
  expect(notes.get("made-wash-h")?.map((note) => note.number)).toEqual([3, 4]);
  expect(notes.get("made-print-h")?.map((note) => note.number)).toEqual([5]);
  const html = pageHtml();
  expect(html).toContain('<aside class="margin note" aria-label="Sources in this passage"><ul><li data-g="g3"><b>3</b><span>A chapter on printed cloth, 2003</span></li><li data-g="g4"><b>4</b><span>A printers&#x27; page, 2004</span></li></ul></aside>');
  expect(html).toContain('<li data-g="g5"><b>5</b><span>A compound record, 2005</span></li></ul></aside>');
  expect(html.match(/class="spread kv-run"/g)).toHaveLength(2);
  expect(html).toContain('<div class="spread railed sec-head kv-run"><div class="rail"><span class="numeral">2</span></div>');
});

test("a chapter of two or more sections opens with the approved sub-rail to its headings", () => {
  const document = templateDocument();
  const made = pagePlan(document).chapters.find((chapter) => chapter.key === "made")!;
  expect(chapterSections(document, made).map((section) => [section.id, section.title])).toEqual([
    ["made-made-wash-h", SECTION_TITLES[0]],
    ["made-made-print-h", SECTION_TITLES[1]]
  ]);
  const html = pageHtml();
  expect(html).toContain('<nav class="subrail" aria-label="In this chapter: How it is made"><ol><li><a href="#made-made-wash-h">Washing</a></li><li><a href="#made-made-print-h">Printing</a></li></ol></nav>');
  expect(html).toContain('<h3 class="font-reading text-h3 mt-8" id="made-made-wash-h">Washing</h3>');
  expect(html.indexOf('class="subrail"')).toBeLessThan(html.indexOf('id="made-made-wash-h"'));
  expect(html.match(/class="subrail"/g)).toHaveLength(1);
});

test("the sources chapter draws the five groups of the approved page and the kin crafts' sources apart", () => {
  const document = templateDocument();
  expect(sourceGroups(document, sourceSplit(document).own)).toEqual([
    { title: "Government records", keys: ["g1"] },
    { title: "Scholarship", keys: ["g2"] },
    { title: "Museums and references", keys: ["g3"] },
    { title: "Community and press", keys: ["g4"] },
    { title: "Compound records", keys: ["g5"] }
  ]);
  const kin = between(pageHtml(), '<div class="kv-src-kin" id="kv-src-kin">', "</details>");
  expect(kin).toContain('<h3 class="kv-sub-h">For the kin crafts</h3>');
  expect(kin).toContain("2 sources that support only the kin crafts’ sentences in chapter 4. They are counted apart from the 5 sources of this monograph.");
  expect(kin).toContain('<span class="kv-more-o">Show the 2 sources</span><span class="kv-more-c">Hide them</span>');
  expect([...kin.matchAll(/data-g="(g\d)"/g)].map((found) => found[1])).toEqual(["g6", "g7"]);
});

test("a source's group is read from its stored kind and publisher, and a document stored before kinds groups by grade", () => {
  expect(kindGroup(source("GI_JOURNAL", "City Museum"))).toBe("Government records");
  expect(kindGroup(source("BOOK_CHAPTER", "City Museum of Textiles"))).toBe("Museums and references");
  expect(kindGroup(source("OTHER", "State Archives"))).toBe("Museums and references");
  expect(kindGroup(source("ENCYCLOPEDIA", "An encyclopedia of art"))).toBe("Museums and references");
  expect(kindGroup(source("OTHER", "A state university"))).toBe("Scholarship");
  expect(kindGroup(source("WEB_PAGE", "A newspaper"))).toBe("Community and press");
  expect(kindGroup(source("A_KIND_TO_COME", null))).toBe("Community and press");
  const stored = withoutKinds(templateDocument());
  expect(sourceGroups(stored, sourceSplit(stored).own).map((group) => group.title)).toEqual(["Peer-reviewed or official", "Reputable reference", "General web"]);
});

async function drawn(page: Page, width: number, theme: (typeof THEMES)[number], html: string): Promise<void> {
  await page.setViewportSize({ width, height: 900 });
  await page.emulateMedia({ reducedMotion: "reduce", colorScheme: theme });
  await page.setContent(`<!doctype html><html lang="en" data-theme="${theme}"><head><meta charset="utf-8"><style>${PRIMITIVE_CSS}</style><style>${KIT_CSS}</style><style>${PAGE_CSS}</style></head><body>${html}</body></html>`, { waitUntil: "domcontentloaded" });
}

async function shown(page: Page, selector: string): Promise<boolean[]> {
  return page.locator(selector).evaluateAll((nodes) => nodes.map((node) => getComputedStyle(node).display !== "none" && (node as HTMLElement).offsetWidth > 0));
}

test("at 360, 768 and 1440 in light and dark every part is drawn, margin notes from 1200px, with no sideways scroll", async ({ page }) => {
  const html = pageHtml();
  const grounds = new Map<string, string>();
  for (const theme of THEMES) {
    for (const width of WIDTHS) {
      await drawn(page, width, theme, html);
      const run = `${width} ${theme}`;
      expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth), run).toBeLessThanOrEqual(0);
      expect(await shown(page, "header.kv-open h1.kv-q"), run).toEqual([true]);
      expect(await shown(page, ".kv-open-label"), run).toEqual([true]);
      expect((await shown(page, "nav.kv-toc li")).filter(Boolean), run).toHaveLength(5);
      expect(await shown(page, "nav.subrail"), run).toEqual([true]);
      expect((await shown(page, ".src-group h3")).filter(Boolean), run).toHaveLength(5);
      expect(await shown(page, "#kv-src-kin"), run).toEqual([true]);
      const notes = await shown(page, ".spread > aside.margin.note");
      expect(notes.length, run).toBeGreaterThan(0);
      expect(notes.every((visible) => visible === width >= SPREAD_FROM), run).toBe(true);
      grounds.set(run, await page.locator(".kv-open-label").evaluate((node) => getComputedStyle(node).backgroundColor));
    }
  }
  for (const width of WIDTHS) expect(grounds.get(`${width} light`)).not.toBe(grounds.get(`${width} dark`));
});

test("from 1200px the popover of a passage's closing sentence docks in its margin and is seen whole past the passage's edge", async ({ page }) => {
  await drawn(page, 1440, "light", pageHtml());
  await page.addScriptTag({ content: KIT_JS });
  await page.evaluate((id) => {
    const spread = document.getElementById(id)?.closest(".spread");
    const cites = spread ? Array.from(spread.querySelectorAll<HTMLElement>(":scope > .main .kcite")) : [];
    cites[cites.length - 1]?.click();
  }, LAST_SECTION_OF_MADE);
  const pop = page.locator("#kv-pop.docked");
  await expect(pop).toBeVisible();
  const seen = await pop.evaluate((node) => {
    const foot = node.querySelector(".pop-foot") as HTMLElement;
    foot.scrollIntoView({ block: "center" });
    const box = foot.getBoundingClientRect();
    const hit = document.elementFromPoint(box.left + box.width / 2, box.top + box.height / 2);
    const passage = node.closest(".bx-pt > .screen") as HTMLElement;
    return { past: node.getBoundingClientRect().bottom > passage.getBoundingClientRect().bottom, whole: hit !== null && node.contains(hit) };
  });
  expect(seen).toEqual({ past: true, whole: true });
});
