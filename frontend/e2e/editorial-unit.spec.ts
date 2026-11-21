import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";
import { createElement, type ReactElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import DesignPage from "@/app/design/page";
import { AuthProvider } from "@/components/AuthProvider";
import { BrandLockup, BrandMark } from "@/components/BrandMark";
import { ChapterRail } from "@/components/editorial/ChapterRail";
import { FactGrid } from "@/components/editorial/FactGrid";
import { Masthead } from "@/components/editorial/Masthead";
import { Plate } from "@/components/editorial/Plate";
import { SpecimenLabel } from "@/components/editorial/SpecimenLabel";
import { MATERIAL_TEXTURE, TypographicPlate } from "@/components/editorial/TypographicPlate";
import { ThemeProvider } from "@/components/ThemeProvider";
import { ToastProvider } from "@/components/ui/Toast";
import { chapterFromQuery, currentChapter } from "@/lib/chapters";
import { COMMONS_WIDTHS, commonsSrcSet, commonsThumb, focalPosition, focalViewBox, standardWidth } from "@/lib/commonsPicture";
import { mastheadNameSize, shownNativeName, type NativeName } from "@/lib/editorialText";
import { marginNotes, stackNotes } from "@/lib/marginNotes";
import type { SourceRef } from "@/lib/types";

import { attribute } from "./explainerRender";
import { FRONTEND } from "./moduleGraph";

const html = (element: ReactElement) => renderToStaticMarkup(element);
const words = (markup: string) => markup.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
const FILE = "https://upload.wikimedia.org/wikipedia/commons/1/13/Ajrak_Print_6.jpg";
const KASUTI: NativeName = { text: "ಕಸೂತಿ", lang: "kn", script: "Knda", sourceId: "wikidata-label", sourceKind: "wikidata", reviewed: true };

test("Commons pictures come only at the standard widths, from the thumbnail path, whatever width is asked", () => {
  expect(COMMONS_WIDTHS).toEqual([330, 500, 960, 1280, 1920]);
  expect([1, 330, 331, 700, 1300, 4000].map(standardWidth)).toEqual([330, 330, 500, 960, 1920, 1920]);
  expect(commonsThumb(FILE, 600)).toBe("https://upload.wikimedia.org/wikipedia/commons/thumb/1/13/Ajrak_Print_6.jpg/960px-Ajrak_Print_6.jpg");
  expect(commonsThumb("https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Map.svg/120px-Map.svg.png", 330)).toBe("https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Map.svg/330px-Map.svg.png");
  expect(() => commonsThumb("https://example.org/a.jpg", 330)).toThrow("Not a Wikimedia Commons file");
  expect(commonsSrcSet(FILE, [500, 960, 1280], 1000)).toBe(`${commonsThumb(FILE, 500)} 500w, ${commonsThumb(FILE, 960)} 960w`);
  expect(focalPosition([0.1, 0.2, 0.4, 0.4])).toBe("30% 40%");
  expect(focalViewBox([0.1, 0.2, 0.4, 0.4])).toBe("inset(20% 50% 40% 10%)");
});

test("a plate puts the caption first and the credit after, at standard widths, and opens larger", () => {
  const markup = html(createElement(Plate, { src: FILE, alt: "An ajrakh print", caption: "Look at the roundels.", credit: "Photo: SMarndi, CC BY-SA 4.0, via Wikimedia Commons" }));
  const widths = [...markup.matchAll(/\/(\d+)px-Ajrak_Print_6\.jpg/g)].map((found) => Number(found[1]));
  expect(widths.length).toBeGreaterThan(3);
  for (const width of widths) expect(COMMONS_WIDTHS).toContain(width);
  expect(markup).toContain('sizes="(min-width: 1024px) 16vw, (min-width: 640px) 25vw, 72vw"');
  expect(markup).toContain('loading="lazy"');
  expect(markup).toContain('referrerPolicy="no-referrer"');
  expect(markup).toMatch(/crossorigin="anonymous"/i);
  expect(html(createElement(Plate, { src: "/landing/cloth.jpg", alt: "A cloth", caption: "Cloth.", credit: "Photo: KalaVigyan" }))).not.toMatch(/crossorigin/i);
  expect(markup.indexOf("Look at the roundels.")).toBeLessThan(markup.indexOf("Photo: SMarndi"));
  expect(markup).toContain('aria-haspopup="dialog"');
  expect(markup).not.toContain("blur");
});

test("an own-script name appears only when a reviewed source states it, at equal standing in the label", () => {
  expect(shownNativeName(KASUTI)?.dir).toBe("ltr");
  expect(shownNativeName({ ...KASUTI, script: "Aran", lang: "ur" })?.dir).toBe("rtl");
  expect(shownNativeName({ ...KASUTI, reviewed: false })).toBeNull();
  expect(shownNativeName({ ...KASUTI, sourceId: null })).toBeNull();
  expect(mastheadNameSize("Kutch Ajrakh")).toBe("title");
  expect(mastheadNameSize("Swamimalai Bronze Icons")).toBe("h1");
  const masthead = html(createElement(SpecimenLabel, { variant: "masthead", kicker: "Craft", name: "Kasuti Embroidery", nativeName: KASUTI }));
  expect(masthead).toMatch(/<h1[^>]*class="kv-names[^"]*text-title/);
  expect(masthead).toContain('<span lang="kn" data-script="Knda" dir="ltr">ಕಸೂತಿ</span>');
  const held = html(createElement(SpecimenLabel, { variant: "masthead", kicker: "Craft", name: "Kasuti Embroidery", nativeName: { ...KASUTI, reviewed: false } }));
  expect(held).not.toContain("ಕಸೂತಿ");
  expect(html(createElement(SpecimenLabel, { variant: "landing", kicker: "Specimen", name: "Kutch Ajrakh" }))).toMatch(/<aside aria-label="Specimen label"[^>]*><p[^>]*>.*<p class="kv-names/);
  expect(html(createElement(SpecimenLabel, { variant: "chapter", kicker: "Chapter 4", name: "The Great Rann" }))).toContain("<h2");
  expect(html(createElement(SpecimenLabel, { variant: "landing", kicker: "Specimen", name: "Kutch Ajrakh", onPhoto: true }))).toContain("data-on-photo");
});

test("every craft has a plate on its material's ground, and a masthead without a photograph shows it", () => {
  expect(Object.keys(MATERIAL_TEXTURE)).toHaveLength(12);
  const plate = html(createElement(TypographicPlate, { material: "metal", englishName: "Swamimalai Bronze Icons", kicker: "Bronze", nativeName: KASUTI }));
  expect(plate).toContain("g-metal");
  expect(plate).toContain("<pattern");
  expect(words(plate)).toBe("Bronze ಕಸೂತಿ");
  expect(words(html(createElement(TypographicPlate, { material: "textile", englishName: "Kutch Bandhani", kicker: null })))).toBe("Kutch Bandhani");
  const masthead = html(createElement(Masthead, { material: "textile", label: { kicker: "Craft", name: "Kalpi Handmade Paper" } }));
  expect(attribute(masthead, "typographic-plate", "aria-hidden")).toEqual(["true"]);
  expect(masthead.match(/<h1/g)).toHaveLength(1);
  const pictured = html(createElement(Masthead, { material: "textile", picture: { src: FILE, alt: "Cloth", caption: "The field.", credit: "Photo", wide: [0, 0.2, 1, 0.6] }, label: { kicker: "Monograph", name: "Kutch Ajrakh" } }));
  expect(pictured).toContain('loading="eager" fetchPriority="high"');
  expect(pictured).toContain("--focal-wide-box:inset(20% 0% 20% 0%)");
  expect(pictured).not.toMatch(/<img[^>]* (width|height)=/);
  const sized = html(createElement(Masthead, { material: "textile", picture: { src: FILE, alt: "Cloth", caption: "The field.", credit: "Photo", originalWidth: 3000, originalHeight: 2000 }, label: { kicker: "Monograph", name: "Kutch Ajrakh" } }));
  expect(sized).toMatch(/<img[^>]* alt="Cloth" width="3000" height="2000"/);
});

test("the fact grid is a definition list, and the chapter rail marks the chapter in view and maps old tab links", () => {
  const grid = html(createElement(FactGrid, { facts: [{ label: "Colours", value: "Blue, black, red and white" }] }));
  expect(grid).toMatch(/^<dl class="kv-glance" data-columns="4"[^>]*><div><dt[^>]*>Colours<\/dt><dd/);
  expect(html(createElement(FactGrid, { facts: [] }))).toBe("");
  const chapters = [{ id: "glance", label: "At a glance" }, { id: "made", label: "How it is made" }, { id: "chem", label: "The chemistry" }];
  const rail = html(createElement(ChapterRail, { chapters }));
  expect(rail).toContain('<nav aria-label="Chapters"');
  expect(rail.match(/aria-current="location"/g)).toHaveLength(1);
  expect(rail).toContain('href="#chem"');
  expect(currentChapter([{ id: "glance", top: -400 }, { id: "made", top: 30 }, { id: "chem", top: 900 }], 62)).toBe("made");
  expect(currentChapter([{ id: "glance", top: 300 }], 62)).toBe("glance");
  expect(chapterFromQuery("?tab=science", { science: "chem" }, chapters)).toBe("chem");
  expect(chapterFromQuery("?tab=nope", { science: "chem" }, chapters)).toBeNull();
});

test("margin notes list each source once, in number order, and push down 8px past a note above", () => {
  const source = (id: string, title: string, year: number): SourceRef => ({ id, kind: "OTHER", title, authors: [], year, doi: null, url: null, publisher: null, licence: null, attribution: null, reliability: "A" });
  const sourcesById = new Map([source("a", "GI Journal No. 188: Kutch Ajrakh", 2023), source("b", "Ajrakh", 2022), source("c", "Indigo in Kutch", 2019)].map((entry) => [entry.id, entry]));
  const numbers = new Map([["a", 1], ["b", 2], ["c", 3]]);
  const notes = marginNotes([{ anchorId: "s1", sourceIds: ["b", "a", "a"] }, { anchorId: "s2", sourceIds: ["a", "c"] }], numbers, sourcesById);
  expect(notes.map((note) => [note.number, note.anchorId])).toEqual([[1, "s1"], [2, "s1"], [3, "s2"]]);
  expect(stackNotes([0, 0, 200], [40, 40, 40])).toEqual([0, 48, 200]);
  expect(stackNotes([0, 10], [60, 20])).toEqual([0, 68]);
});

test("the mark is one colour at every size and the lockup reads its name in both scripts", () => {
  const mark = html(createElement(BrandMark, { className: "h-4 w-4" }));
  expect(mark).toContain('fill="currentColor"');
  expect(mark).not.toMatch(/#[0-9a-f]{3,6}/i);
  const lockup = html(createElement(BrandLockup));
  expect(lockup).toContain('role="img" aria-label="KalaVigyan, कलाविज्ञान"');
  expect(lockup.match(/<svg/g)).toHaveLength(2);
  expect(words(lockup)).toBe("");
  const icon = readFileSync(join(FRONTEND, "app", "icon.svg"), "utf8");
  expect(icon.match(/<path/g)).toHaveLength(1);
  expect(icon).toContain("prefers-color-scheme: dark");
});

test("the design page draws every primitive from the real components and tells search engines to stay away", async () => {
  const { metadata } = await import("@/app/design/page");
  expect(metadata.robots).toEqual({ index: false, follow: false });
  const page = html(createElement(AuthProvider, null, createElement(ThemeProvider, null, createElement(ToastProvider, null, createElement(DesignPage)))));
  for (const id of ["mark", "buttons", "rows", "fields", "citations", "evidence", "label", "plates", "status", "motion"]) expect(page, id).toContain(`id="${id}"`);
  for (const testId of ["citation-chip", "source-panel", "margin-notes", "specimen-label", "masthead", "typographic-plate", "plate", "figure", "fact-grid", "chapter-rail", "empty-state", "evidence-tag", "sources-differ"]) expect(page, testId).toContain(`data-testid="${testId}"`);
  expect(page.match(/<h1/g)).toHaveLength(1);
  expect(page).not.toMatch(/not built yet|coming soon|no data|not enough cited evidence/i);
});
