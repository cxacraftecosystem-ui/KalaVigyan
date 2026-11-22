import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";
import { createElement, type ReactElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { AuthProvider } from "../components/AuthProvider";
import { MonographDocumentPage } from "../components/monograph/MonographDocumentPage";
import { MonographShellPage } from "../components/monograph/MonographShellPage";
import { ThemeProvider } from "../components/ThemeProvider";
import { draftVariant } from "../lib/documentVariant";
import type { MonographDocument } from "../lib/monographDocument";
import { deferredRest } from "../lib/monographDeferred";
import { documentDigest, restAddress } from "../lib/monographRenderShell";
import { shownPage } from "../lib/monographShownPage";
import { previewLanguages } from "../lib/translationPreview";

import { generatedDocument } from "./generatedMonographFixture";
import { goldenDocument } from "./monographNative";

const provided = (element: ReactElement) => renderToStaticMarkup(createElement(AuthProvider, null, createElement(ThemeProvider, null, element)));
const ROUTES = join(__dirname, "..", "app", "(reading)");
const STRIP = '<nav aria-label="Languages of this page"';
const STRIP_ON_THE_PLATE = '<nav aria-label="Languages of this page" class="w-full px-4 pt-3 sm:px-6 md:px-10 rail:px-12 xl:px-16"><div class="mx-auto w-full max-w-content">';
const HINDI_UNIT = 'lang="hi" dir="ltr" data-script="Deva"';
const HINDI_LEDE = ["बाघ छपाई बाघिनी नदी के किनारे ठप्पों से छापी जाती ", "है।"];
const HINDI_SHELL_WORD = "अजरख";
const ROOT = (html: string) => /<div class="kv-monograph[^"]*" lang="([^"]+)"/.exec(html)?.[1];

function hindiDocumentPage(): MonographDocument {
  return draftVariant(generatedDocument(), "hi", "Deva", [{ key: "overview-1", english: ["Bagh print is block printed on the Baghini ", "river."], texts: HINDI_LEDE }]);
}

function hindiShellPage(): MonographDocument {
  const golden = goldenDocument();
  const lede = '<p class="t-lede ans-lede">';
  const shell = (golden.shell ?? "").replace(lede, `${lede}<span ${HINDI_UNIT}>${HINDI_SHELL_WORD}</span> `);
  const [first] = Object.keys(golden.content.units);
  const units = { ...golden.content.units, [first]: { ...golden.content.units[first], lang: "hi" } };
  const translation = { sourceLanguage: "en", sourceVersion: golden.version, script: "Deva", direction: "ltr", passages: 40, translated: 1, held: 0 } as const;
  return { ...golden, language: "hi", shell, content: { ...golden.content, units }, translation };
}

test("a translated document page draws the language strip, keeps its own frame English and marks each passage's language", () => {
  const document = hindiDocumentPage();
  const html = provided(createElement(MonographDocumentPage, { document, languages: previewLanguages(document) }));
  expect(html).toContain(STRIP);
  expect(html).toContain(STRIP_ON_THE_PLATE);
  expect(ROOT(html)).toBe("en");
  expect(html).toMatch(new RegExp(`${HINDI_UNIT}>(?:<span class="s">)?${HINDI_LEDE[0]}`));
  expect(html).toContain('lang="en" dir="ltr" data-fallback="en"');
  expect(html).toContain("1 of 11 passages read in Hindi");
  const english = provided(createElement(MonographDocumentPage, { document: generatedDocument() }));
  expect(english).not.toContain(STRIP);
  expect(english).not.toContain("data-fallback");
});

test("a translated shell page draws the same strip, and the server's per-passage language marks reach its shell", () => {
  const document = hindiShellPage();
  const html = provided(createElement(MonographShellPage, { document, deferred: true, languages: previewLanguages(document) }));
  expect(html).toContain(STRIP);
  expect(ROOT(html)).toBe("en");
  expect(html).toContain(`<span ${HINDI_UNIT}>${HINDI_SHELL_WORD}</span>`);
  expect(html).toContain('aria-current="page"');
  const english = provided(createElement(MonographShellPage, { document: goldenDocument(), deferred: true, languages: null }));
  expect(english).not.toContain(STRIP);
});

test("the deferred rest of a translated page is asked for at its variant's address, English pages at theirs", () => {
  const shell = hindiShellPage();
  const shellRest = deferredRest(shell, shownPage(shell).plan, true);
  expect(shellRest).toBe(`/crafts/Kutch-Ajrakh/shell/v${shell.version}-${documentDigest(shell)}-hi`);
  expect(documentDigest(shell)).not.toBe(documentDigest(goldenDocument()));
  const page = hindiDocumentPage();
  const pageRest = deferredRest(page, shownPage(page).plan, true);
  expect(pageRest).toBe(`/crafts/Bagh-Print/shell/v${page.version}-${documentDigest(page)}-hi`);
  const english = goldenDocument();
  expect(deferredRest(english, shownPage(english).plan, true)).toBe(`/crafts/Kutch-Ajrakh/shell/v${english.version}-${documentDigest(english)}`);
  expect(restAddress(`v3-${documentDigest(shell)}-hi`)).toEqual({ version: 3, digest: documentDigest(shell), language: "hi" });
  expect([restAddress("v3-hi"), restAddress(`v3-${documentDigest(shell)}-xx`), restAddress(`v3-${documentDigest(shell)}-en`)]).toEqual([null, null, null]);
});

test("every translated reading route defers its rest, and the rest routes read the variant the address names, never its English", () => {
  const read = (...path: string[]) => readFileSync(join(ROUTES, ...path), "utf8");
  expect(read("crafts", "[slug]", "[edition]", "page.tsx")).toContain("<MonographPage document={document} deferred languages={languages} />");
  expect(read("categories", "[slug]", "[language]", "page.tsx")).toContain("masthead={false} deferred languages={languages}");
  const craftRest = read("crafts", "[slug]", "shell", "[version]", "route.ts");
  expect(craftRest).toContain("serverDocumentInLanguage(\"craft\", slug, language, address.version)");
  expect(craftRest).toContain("read.language === language");
  expect(read("categories", "[slug]", "shell", "[version]", "route.ts")).toContain("document.language === (address.language ?? ENGLISH)");
});
