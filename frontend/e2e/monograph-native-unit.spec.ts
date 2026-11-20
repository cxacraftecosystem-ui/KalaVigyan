import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";

import { COMPONENT_VIEWS } from "../components/monograph/componentViews";
import { placedComponents } from "../lib/monographRenderLayout";
import { shellSlots, shellTree } from "../lib/monographShellTree";

import { anchorTest, AJRAKH_DIR, canonical, subtrees, type Token } from "./monographMarkup";
import { caselessTokens, drawnMain, firstDifference, goldenDocument, nativeComponents, servedMain } from "./monographNative";

const WINDOW = 12;

let pages: { approved: Token[]; rendered: Token[] } | null = null;

function bothMains(): { approved: Token[]; rendered: Token[] } {
  pages ??= { approved: caselessTokens(servedMain()), rendered: caselessTokens(drawnMain()) };
  return pages;
}

function anchored(tokens: Token[], anchor: string): string[] {
  const found = subtrees(tokens, anchorTest(anchor));
  expect(found.length, `${anchor} is on the page once`).toBe(1);
  return canonical(tokens.slice(found[0][0], found[0][1]));
}

function expectSameLines(rendered: readonly string[], approved: readonly string[]): void {
  const at = firstDifference(approved, rendered);
  const from = Math.max(0, at - WINDOW);
  expect(at < 0 ? [] : rendered.slice(from, at + WINDOW), `the first difference, at line ${at}`).toEqual(at < 0 ? [] : approved.slice(from, at + WINDOW));
  expect(rendered.length).toBe(approved.length);
}

test("the native views listed for Kutch Ajrakh are its document's specs, each with a registered view", () => {
  const listed = JSON.parse(readFileSync(join(AJRAKH_DIR, "native.json"), "utf8")) as string[];
  const document = goldenDocument();
  expect(Object.keys(document.specs).sort()).toEqual([...listed].sort());
  for (const component of nativeComponents(document)) expect(COMPONENT_VIEWS[component.kind], component.label).toBeTruthy();
});

test("a native view's placed components are native too, and the shell keeps a slot for each native no other places", () => {
  const document = goldenDocument();
  const natives = new Set(Object.keys(document.specs));
  const placed = new Set<string>();
  for (const label of natives) {
    for (const inner of placedComponents(document, label)) {
      expect(natives.has(inner), `${label} places ${inner}`).toBe(true);
      placed.add(inner);
    }
  }
  expect(shellSlots(shellTree(document.shell ?? "", natives)).sort()).toEqual([...natives].filter((label) => !placed.has(label)).sort());
});

for (const component of nativeComponents()) {
  test(`${component.label} draws natively what the approved page draws`, () => {
    const { approved, rendered } = bothMains();
    expectSameLines(anchored(rendered, component.anchor), anchored(approved, component.anchor));
  });
}

test("the Ajrakh shell, with its native views drawn in place, is the approved page's main element", () => {
  const { approved, rendered } = bothMains();
  expectSameLines(canonical(rendered), canonical(approved));
});
