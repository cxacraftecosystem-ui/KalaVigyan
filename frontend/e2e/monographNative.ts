import { readFileSync } from "node:fs";
import { join } from "node:path";

import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { AuthoredShell } from "../components/monograph/AuthoredShell";
import type { MonographComponent, MonographDocument } from "../lib/monographDocument";
import { parseMonographDocument } from "../lib/monographDocumentShape";

import { tokenize, type Token } from "./monographMarkup";

export const GOLDEN_DOCUMENT = join(__dirname, "..", "..", "shared", "monograph.document.golden.json");
export const SERVED_PAGE = join(__dirname, "..", "public", "monographs", "kutch-ajrakh", "index.html");
export const REACT_ONLY = /<!-- -->|<link rel="preload"[^>]*>/g;

const MAIN_OPEN = '<main id="kv-main">';
const MAIN_CLOSE = "</main>";
const SHELL_OPEN = '<div id="kv-main">';
const SHELL_CLOSE = "</div>";

let golden: MonographDocument | null = null;

export function goldenText(): string {
  return readFileSync(GOLDEN_DOCUMENT, "utf8");
}

export function goldenDocument(): MonographDocument {
  golden ??= parseMonographDocument(JSON.parse(goldenText()));
  return golden;
}

export function fragmentDocumentText(version: number): string {
  return JSON.stringify({ ...JSON.parse(goldenText()), version, specs: {}, shell: servedMain() });
}

export function nativeComponents(document: MonographDocument = goldenDocument()): MonographComponent[] {
  return document.content.components.filter((component) => Object.hasOwn(document.specs, component.label));
}

export function servedMain(): string {
  const page = readFileSync(SERVED_PAGE, "utf8");
  return page.slice(page.indexOf(MAIN_OPEN) + MAIN_OPEN.length, page.lastIndexOf(MAIN_CLOSE));
}

export function drawnMain(document: MonographDocument = goldenDocument()): string {
  const html = renderToStaticMarkup(createElement(AuthoredShell, { document, shell: document.shell ?? "" })).replace(REACT_ONLY, "");
  return html.slice(html.indexOf(SHELL_OPEN) + SHELL_OPEN.length, html.lastIndexOf(SHELL_CLOSE));
}

export function caselessTokens(markup: string): Token[] {
  return tokenize(markup).map((token) => (token.kind === "open" ? { ...token, attrs: Object.fromEntries(Object.entries(token.attrs).map(([name, value]) => [name.toLowerCase(), value])) } : token));
}

export function firstDifference(left: readonly string[], right: readonly string[]): number {
  const length = Math.max(left.length, right.length);
  for (let at = 0; at < length; at++) if (left[at] !== right[at]) return at;
  return -1;
}
