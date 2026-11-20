import { readFileSync } from "node:fs";
import { join } from "node:path";
import { gunzipSync } from "node:zlib";

import { expect, test } from "@playwright/test";
import { createElement, type ReactElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { AuthProvider } from "../components/AuthProvider";
import { DeferredDocument } from "../components/monograph/DeferredDocument";
import { KitData } from "../components/monograph/DeferredShell";
import { shownPage } from "../components/monograph/MonographChapters";
import { deferredRest, MonographPage } from "../components/monograph/MonographPage";
import { ThemeProvider } from "../components/ThemeProvider";
import type { MonographDocument } from "../lib/monographDocument";
import { parseNamedDocument } from "../lib/monographRenderCitations";
import { KIT_CITES_ID, kitDataBlocks } from "../lib/monographRenderKit";
import { checkedDocumentRest, documentRest, leadChapters, restBody, restChapters } from "../lib/monographRenderShell";

import { generatedDocument } from "./generatedMonographFixture";
import { goldenDocument } from "./monographNative";

const markup = (element: ReactElement) => renderToStaticMarkup(element);
const provided = (element: ReactElement) => markup(createElement(AuthProvider, null, createElement(ThemeProvider, null, element)));
const chapterIds = (html: string) => [...html.matchAll(/<section class="kv-ch" id="([a-z-]+)"/g)].map((found) => found[1]);
const MAIN_END = '</div><footer class="kv-foot">';
const REACT_IDS = /_r_[0-9a-z]+_|«r[0-9a-z]+»|:r[0-9a-z]+:/gi;
const sameIds = (html: string) => html.replace(REACT_IDS, "react-id");
const HUB_DOCUMENT = join(__dirname, "textilesHubDocument.json.gz");
const HUB_FIGURES = ["shared/chemistry/alizarin-purpurin-3d", "shared/chemistry/indigo-leaf-to-cloth-chain", "shared/chemistry/indigo-reduction-player", "shared/chemistry/indigo-vat-dip"];
const drawnLabels = (html: string) => [...new Set([...html.matchAll(/data-component="([^"]+)"/g)].map((found) => found[1]))].sort();

function restOf(document: MonographDocument): string {
  return provided(createElement(DeferredDocument, { part: documentRest(document), jump: null }));
}

test("a generated page draws its first chapter and a reserved place for the rest, and the whole page when nothing is deferred", () => {
  const document = generatedDocument();
  const split = provided(createElement(MonographPage, { document, deferred: true }));
  const whole = provided(createElement(MonographPage, { document }));
  expect(chapterIds(whole)).toEqual(["opening", "chem", "sources"]);
  expect(chapterIds(split)).toEqual(["opening"]);
  expect(split).toContain('data-kv-deferred=""');
  expect(split).not.toContain(`id="${KIT_CITES_ID}"`);
  expect(whole).not.toContain("data-kv-deferred");
  expect(whole).toContain(`id="${KIT_CITES_ID}"`);
  const opening = split.slice(split.indexOf('<section class="kv-ch" id="opening"'), split.indexOf('<div class="min-h-[300vh]"'));
  expect(opening.length).toBeGreaterThan(500);
  expect(whole).toContain(opening);
});

test("the rest draws every later chapter and Cite this monograph exactly as the whole page draws them, then the kit's data", () => {
  const document = generatedDocument();
  const whole = provided(createElement(MonographPage, { document }));
  const later = whole.slice(whole.indexOf('<section class="kv-ch" id="chem"'), whole.indexOf(MAIN_END));
  const kit = markup(createElement(KitData, { blocks: kitDataBlocks(shownPage(document).document.content) }));
  expect(later).toContain("Cite this monograph");
  expect(sameIds(restOf(document))).toBe(sameIds(later + kit));
  expect(chapterIds(restOf(document))).toEqual(["chem", "sources"]);
});

test("the first chapter leads and every other chapter is the rest", () => {
  const chapters = ["opening", "chem", "sources"];
  expect(leadChapters(chapters)).toEqual(["opening"]);
  expect(restChapters(chapters)).toEqual(["chem", "sources"]);
  expect([...leadChapters(chapters), ...restChapters(chapters)]).toEqual(chapters);
});

test("a generated craft, family and category each ask for their rest at their own page's address and version", () => {
  const document = generatedDocument();
  const plan = shownPage(document).plan;
  expect(deferredRest(document, plan, true)).toBe("/crafts/Bagh-Print/shell/v5");
  expect(deferredRest({ ...document, subjectKind: "family" }, plan, true)).toBe("/crafts/Bagh-Print/shell/v5");
  expect(deferredRest({ ...document, subjectKind: "category" }, plan, true)).toBe("/categories/Bagh-Print/shell/v5");
  expect(deferredRest(document, plan, false)).toBeNull();
  expect(deferredRest(document, { ...plan, chapters: leadChapters(plan.chapters) }, true)).toBeNull();
});

test("the rest of a generated document carries the whole document for its version only, and a shell's rest stays the shell's", () => {
  const document = generatedDocument();
  const rest = JSON.parse(JSON.stringify(restBody(document)));
  expect(checkedDocumentRest(rest, document.version).document.content).toEqual(document.content);
  expect(() => checkedDocumentRest(rest, document.version + 1)).toThrow(/another shape/);
  expect(() => checkedDocumentRest({ ...rest, document: { ...rest.document, shell: "<main></main>" } }, document.version)).toThrow(/another shape/);
  const golden = goldenDocument();
  expect(Object.keys(restBody(golden)).sort()).toEqual(["bundles", "data", "schemaVersion", "sources", "tree", "version"]);
});

test("the rest of the Textiles hub draws every borrowed figure its whole page draws", () => {
  const document = parseNamedDocument(JSON.parse(gunzipSync(readFileSync(HUB_DOCUMENT)).toString("utf8")));
  const whole = provided(createElement(MonographPage, { document, masthead: false }));
  const rest = provided(createElement(DeferredDocument, { part: JSON.parse(JSON.stringify(documentRest(document))), jump: null }));
  for (const label of HUB_FIGURES) expect(drawnLabels(whole), label).toContain(label);
  expect(drawnLabels(rest)).toEqual(drawnLabels(whole));
  const split = provided(createElement(MonographPage, { document, masthead: false, deferred: true }));
  expect(split).toContain('data-kv-deferred=""');
  expect(drawnLabels(split)).toEqual([]);
});
