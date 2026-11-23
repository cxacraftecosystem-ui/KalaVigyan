import { expect, test } from "@playwright/test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { CitationChips, CitationProvider, type CitationLookup } from "@/components/answer/CitationContext";
import { Cite } from "@/components/editorial/CitationCluster";
import { SourcePanel } from "@/components/editorial/SourcePanel";
import { SheetPanel, type SheetPanelProps } from "@/components/ui/Sheet";
import { citationCluster, citationSurface, clusterEntries, clusterLabel, clusterName, entryRights, evidenceState, shortTitle, sourceCountLine } from "@/lib/citationCluster";
import type { Citation, SourceRef } from "@/lib/types";

import { attribute, shownText } from "./explainerRender";
import { primitivesPage } from "./primitivesPage";

const ref = (id: string, title: string, reliability: SourceRef["reliability"], url: string | null = null): SourceRef => ({
  id,
  kind: "OTHER",
  title,
  authors: [],
  year: 2023,
  doi: null,
  url,
  publisher: "GI Registry",
  licence: null,
  attribution: null,
  reliability
});

const cite = (id: string, sourceId: string, quote: string | null, locator: string | null, level: Citation["level"] = "PROVISIONAL"): Citation => ({
  id,
  claimId: `k-${id}`,
  sourceId,
  quote,
  locator,
  context: null,
  evidence: quote === null ? "INFERRED" : "QUOTED",
  level
});

const GI = ref("gi", "GI Journal No. 188: Kutch Ajrakh", "A", "https://search.ipindia.gov.in/GIRPublicSearch/");
const MAP = ref("map", "Ajrakh", "B");
const LONG = ref("long", "Microbial Communities Associated With Indigo Fermentation That Thrive in Anaerobic Alkaline Environments", "C");
const SOURCES = new Map([GI, MAP, LONG].map((source) => [source.id, source]));
const NUMBERS = new Map([
  ["gi", 1],
  ["map", 2],
  ["long", 4]
]);
const GREEN = "At first bright green, the cloth rapidly becomes blue as oxygen meets the dye particles on the fibres.";
const SENTENCE = [cite("a", "map", "The dyed cloth emerges a bright green.", "paragraph 7"), cite("b", "gi", GREEN, "p. 12", "VERIFIED"), cite("c", "gi", GREEN, "p. 12", "VERIFIED"), cite("d", "gi", "Printed on both sides.", "p. 14")];

test("a sentence's citations become one cluster, one entry per source, sorted by number, each repeated passage dropped", () => {
  const entries = clusterEntries([cite("x", "long", null, null), ...SENTENCE], NUMBERS, SOURCES);
  expect(entries.map((entry) => entry.number)).toEqual([1, 2, 4]);
  expect(entries[0].citations.map((citation) => citation.id)).toEqual(["b", "d"]);
  expect(clusterLabel(entries)).toBe("1,2,4");
  expect(clusterLabel([{ number: 5 }, { number: null }])).toBe("5,·");
});

test("the accessible name says Source or Sources with the numbers, and the titles go into the description", () => {
  expect(clusterName([{ number: 3 }])).toBe("Source 3");
  expect(clusterName([{ number: 1 }, { number: 2 }])).toBe("Sources 1, 2");
  expect(clusterName([{ number: 3 }, { number: 4 }, { number: 5 }, { number: 6 }])).toBe("Sources 3, 4, 5, 6");
  expect(clusterName([{ number: null }])).toBe("Source");
  expect(clusterName([{ number: null }, { number: null }])).toBe("2 sources");
  expect(clusterName([{ number: 1 }, { number: null }])).toBe("Sources 1 and 1 more");
  const view = citationCluster(SENTENCE, NUMBERS, SOURCES);
  expect(view.name).toBe("Sources 1, 2");
  expect(view.description).toBe("GI Journal No. 188: Kutch Ajrakh; Ajrakh");
  expect(shortTitle(LONG.title)).toBe("Microbial Communities Associated With Indigo Fermentation That Thrive in…");
  expect(shortTitle(LONG.title).length).toBeLessThanOrEqual(73);
});

test("below 640px the sources open in a sheet, from 640px in a popover, and from 1200px in the margin when the page has one", () => {
  expect(citationSurface(360, true)).toBe("sheet");
  expect(citationSurface(639, true)).toBe("sheet");
  expect(citationSurface(640, false)).toBe("popover");
  expect(citationSurface(834, true)).toBe("popover");
  expect(citationSurface(1199, true)).toBe("popover");
  expect(citationSurface(1200, true)).toBe("margin");
  expect(citationSurface(1440, false)).toBe("popover");
});

test("the cluster is one button glued to the word before it, named, described and saying it opens a dialog", () => {
  const html = renderToStaticMarkup(createElement(Cite, { citations: SENTENCE, numbers: NUMBERS, sourcesById: SOURCES }));
  expect(html.match(/<button/g)).toHaveLength(1);
  expect(html.startsWith('<span class="kv-nowrap kv-cite-cluster" data-testid="citation-cluster">⁠<button')).toBe(true);
  expect(attribute(html, "citation-chip", "aria-label")).toEqual(["Sources 1, 2"]);
  expect(attribute(html, "citation-chip", "aria-haspopup")).toEqual(["dialog"]);
  expect(attribute(html, "citation-chip", "aria-expanded")).toEqual(["false"]);
  expect(html).not.toContain("aria-controls");
  const described = attribute(html, "citation-chip", "aria-describedby")[0];
  expect(html).toContain(`<span id="${described}" hidden="">GI Journal No. 188: Kutch Ajrakh; Ajrakh</span>`);
  expect(shownText(html.replace(/<span id="[^"]*" hidden="">[^<]*<\/span>/, "").replace(/<[^>]+>/g, ""))).toBe("⁠1,2");
});

test("a citation lookup draws one cluster per sentence, whatever the number of sources", () => {
  const lookup: CitationLookup = { numbers: NUMBERS, sourcesById: SOURCES };
  const html = renderToStaticMarkup(createElement(CitationProvider, { value: lookup }, createElement(CitationChips, { citations: SENTENCE })));
  expect(attribute(html, "citation-chip", "data-numbers")).toEqual(["1,2"]);
  expect(renderToStaticMarkup(createElement(CitationProvider, { value: lookup }, createElement(CitationChips, { citations: [] })))).toBe("");
});

test("the source panel lists every quote behind the sentence with its locator, reliability and a way to the source", () => {
  const entries = clusterEntries([...SENTENCE, cite("e", "long", null, "chapter 2")], NUMBERS, SOURCES);
  const html = renderToStaticMarkup(createElement(SourcePanel, { entries, headingId: "h", onClose: () => undefined }));
  const text = shownText(html.replace(/<[^>]+>/g, " ").replace(/\s+/g, " "));
  expect(sourceCountLine(3)).toBe("3 sources for this sentence");
  expect(text).toContain("3 sources for this sentence");
  expect(attribute(html, "source-entry", "data-testid")).toHaveLength(3);
  expect(html.match(/data-testid="source-passage"/g)).toHaveLength(4);
  expect(text).toContain(`“${GREEN}”`);
  expect(text).toContain("p. 12");
  expect(text).toContain("Reliability A · peer-reviewed or official");
  expect(text).toContain("Reliability B · reputable reference");
  expect(text).toContain("no passage is quoted");
  expect(text).toContain("Quotes are verbatim.");
  expect(html.match(/>Open the source</g)).toHaveLength(1);
  expect(html).toContain('href="https://search.ipindia.gov.in/GIRPublicSearch/" target="_blank" rel="noopener noreferrer"');
  expect(attribute(html, "evidence-tag", "data-level")).toEqual(["provisional", "provisional", "inferred"]);
  const provisionalPage = renderToStaticMarkup(createElement(SourcePanel, { entries, headingId: "h", onClose: () => undefined, norm: "provisional" }));
  expect(attribute(provisionalPage, "evidence-tag", "data-level")).toEqual(["verified", "inferred"]);
  expect(evidenceState(cite("h", "gi", null, null, "HYPOTHESIS"))).toBe("inferred");
  expect(evidenceState({ evidence: "QUOTED", level: "HYPOTHESIS" })).toBe("hypothesis");
});

test("each source in the panel carries its attribution and licence, once", () => {
  const river = { ...ref("river", "HydroRIVERS", "A"), attribution: "Source: HydroSHEDS, WWF and McGill University", licence: "CC BY 4.0" };
  const wiki = { ...ref("wiki", "Ajrakh", "B"), attribution: "Wikipedia, Ajrakh, revision 1250, CC BY-SA 4.0", licence: "CC BY-SA 4.0" };
  const entries = clusterEntries([cite("r", "river", "The Indus basin.", null), cite("w", "wiki", "Ajrakh is printed.", null)], new Map([["river", 1], ["wiki", 2]]), new Map([river, wiki].map((source) => [source.id, source])));
  const html = renderToStaticMarkup(createElement(SourcePanel, { entries, headingId: "h", onClose: () => undefined }));
  expect([...html.matchAll(/data-testid="source-rights">([^<]*)</g)].map((found) => found[1])).toEqual([
    "Source: HydroSHEDS, WWF and McGill University · CC BY 4.0",
    "Wikipedia, Ajrakh, revision 1250, CC BY-SA 4.0"
  ]);
  expect(entryRights({ licence: null, attribution: null })).toBe("");
  expect(entryRights(null)).toBe("");
});

test("on a phone the panel is a modal sheet at the foot of the screen with a grab bar; from 640px a 380px popover", async ({ page }) => {
  const entries = clusterEntries(SENTENCE, NUMBERS, SOURCES);
  const panel = createElement(SourcePanel, { entries, headingId: "sheet-heading", onClose: () => undefined });
  const sheet = renderToStaticMarkup(createElement(SheetPanel, { labelledBy: "sheet-heading", panelId: "sources" } as SheetPanelProps, panel));
  expect(sheet).toContain('role="dialog" aria-modal="true" aria-labelledby="sheet-heading"');
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.setContent(primitivesPage(`${sheet}<div class="kv-pop" id="pop">${renderToStaticMarkup(panel)}</div>`));
  const box = await page.getByTestId("sheet").boundingBox();
  expect(box?.y && box.height ? Math.round(box.y + box.height) : 0).toBe(844);
  expect(box?.x).toBe(0);
  const shape = await page.getByTestId("sheet").evaluate((node) => ({ position: getComputedStyle(node).position, radius: getComputedStyle(node).borderTopLeftRadius, grab: getComputedStyle(node, "::before").width }));
  expect(shape).toEqual({ position: "fixed", radius: "14px", grab: "40px" });
  await page.setViewportSize({ width: 1024, height: 768 });
  expect((await page.locator("#pop").boundingBox())?.width).toBe(380);
});

test("a sheet opened from inside a dialog sits above the dialog and its scrim, on a phone", async ({ page }) => {
  const entries = clusterEntries(SENTENCE, NUMBERS, SOURCES);
  const panel = createElement(SourcePanel, { entries, headingId: "stacked-heading", onClose: () => undefined });
  const sheet = renderToStaticMarkup(createElement(SheetPanel, { labelledBy: "stacked-heading", stacked: true } as SheetPanelProps, panel));
  const dialog = '<div class="kv-overlay" style="z-index:90"><div class="kv-dialog" data-field-dialog="" role="dialog" aria-modal="true" style="min-height:700px">A term</div></div>';
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.setContent(primitivesPage(`${dialog}<div class="kv-scrim" data-stacked=""></div>${sheet}`));
  const box = await page.getByTestId("sheet").boundingBox();
  const top = await page.evaluate(([x, y]) => document.elementFromPoint(x, y)?.closest('[data-testid="sheet"]') !== null, [195, (box?.y ?? 0) + 40]);
  expect(top).toBe(true);
  const scrimAbove = await page.evaluate(() => document.elementFromPoint(195, 20)?.classList.contains("kv-scrim"));
  expect(scrimAbove).toBe(true);
});

test("the numerals never change a line's height, keep a 24px hit area and read at 11px or more", async ({ page }) => {
  const cluster = renderToStaticMarkup(createElement(Cite, { citations: SENTENCE, numbers: NUMBERS, sourcesById: SOURCES }));
  const words = "Cloth lifted from the indigo vat is bright green at first and turns blue as oxygen meets the dye on the fibres.";
  await page.setContent(primitivesPage(`<p id="plain" style="width:320px;font:17px/1.63 serif">${words} ${words}</p><p id="cited" style="width:320px;font:17px/1.63 serif">${words}${cluster} ${words}${cluster}</p>`));
  const heights = await page.evaluate(() => [document.getElementById("plain")!.offsetHeight, document.getElementById("cited")!.offsetHeight]);
  expect(heights[1]).toBe(heights[0]);
  const numeral = page.getByTestId("citation-chip").first();
  const style = await numeral.evaluate((node) => ({ size: parseFloat(getComputedStyle(node).fontSize), hit: getComputedStyle(node, "::after").minWidth, colour: getComputedStyle(node).color }));
  expect(style.size).toBeGreaterThanOrEqual(11);
  expect(style.hit).toBe("24px");
  expect(style.colour).toBe("rgb(36, 59, 156)");
});

test.describe("on a touch screen", () => {
  test.use({ hasTouch: true });

  for (const width of [360, 390]) {
    test(`a numeral ending a line at ${width}px keeps its 44px hit area and never carries the page sideways`, async ({ page }) => {
      const cluster = renderToStaticMarkup(createElement(Cite, { citations: SENTENCE.slice(0, 1), numbers: NUMBERS, sourcesById: SOURCES }));
      await page.setViewportSize({ width, height: 800 });
      await page.setContent(primitivesPage(`<main style="padding-inline:16px"><p style="margin:0;text-align:end;font:17px/1.63 serif">The dyed cloth emerges a bright green.${cluster}</p></main>`));
      expect(await page.evaluate(() => matchMedia("(pointer: coarse)").matches)).toBe(true);
      const numeral = page.getByTestId("citation-chip");
      const box = await numeral.boundingBox();
      expect(Math.abs((box?.x ?? 0) + (box?.width ?? 0) - (width - 16))).toBeLessThanOrEqual(1);
      expect(await numeral.evaluate((node) => parseFloat(getComputedStyle(node, "::after").width))).toBeGreaterThanOrEqual(44);
      expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(0);
    });
  }
});
