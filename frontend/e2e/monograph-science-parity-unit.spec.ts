import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";
import { createElement, type ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { VIEWS } from "../components/monograph/kinds/science";
import { NestedComponents } from "../components/monograph/NestedComponents";
import type { MonographComponent, MonographContent } from "../lib/monographDocument";
import { AJRAKH_DIR, anchorTest, assembledTemplate, canonical, replaced, subtrees, tokenize, type ElementTest, type Token } from "./monographMarkup";

const content = JSON.parse(readFileSync(join(AJRAKH_DIR, "content.json"), "utf8")) as MonographContent;
const page = tokenize(assembledTemplate());
const byLabel = new Map(content.components.map((component) => [component.label, component]));
const drawn = content.components.filter((component) => VIEWS[component.kind]);

const classed = (name: string): ElementTest => (open) => (open.attrs.class ?? "").split(/\s+/).includes(name);
const HELD_CONTAINERS: ElementTest[] = [classed("differs"), classed("lc-after"), classed("lc-why")];
const CITATION = classed("kcite");

function specOf(label: string): Record<string, unknown> {
  return JSON.parse(readFileSync(join(AJRAKH_DIR, "specs", `${label.replaceAll("/", "__")}.json`), "utf8"));
}

function carriedCites(value: unknown): string[] {
  if (Array.isArray(value)) return value.flatMap(carriedCites);
  if (typeof value !== "object" || value === null) return [];
  const node = value as Record<string, unknown>;
  const own = node.m === "cite" && typeof node.key === "string" ? [node.key] : [];
  return [...own, ...Object.values(node).flatMap(carriedCites)];
}

function unitsWithin(label: string): string[] {
  return content.layout.filter((entry) => entry.within === label).map((entry) => entry.ref);
}

function view(component: MonographComponent): ReactNode {
  const draw = VIEWS[component.kind]!;
  return createElement(draw, {
    component,
    spec: specOf(component.label),
    unitRefs: unitsWithin(component.label),
    renderUnit: (ref: string) => createElement("kv-slot", { unit: ref }),
    renderComponent: (label: string) => createElement("kv-component", { label })
  });
}

function nested(label: string): ReactNode {
  const component = byLabel.get(label)!;
  return VIEWS[component.kind] ? view(component) : createElement("kv-component", { label });
}

function pageRange(component: MonographComponent): [number, number] {
  const [range, ...more] = subtrees(page, anchorTest(component.anchor));
  expect(more).toEqual([]);
  return range;
}

function drawnParent(component: MonographComponent): MonographComponent | null {
  const [start, end] = pageRange(component);
  const parents = drawn.filter((other) => {
    if (other === component) return false;
    const [from, to] = pageRange(other);
    return from <= start && end <= to;
  });
  return parents.sort((a, b) => pageRange(b)[0] - pageRange(a)[0])[0] ?? null;
}

function rendered(component: MonographComponent): Token[] {
  const parent = drawnParent(component);
  const tokens = tokenize(renderToStaticMarkup(createElement(NestedComponents.Provider, { value: nested }, view(parent ?? component))));
  if (parent === null) return tokens;
  const [range, ...more] = subtrees(tokens, anchorTest(component.anchor));
  expect(more).toEqual([]);
  return tokens.slice(range[0], range[1]);
}

const holdsUnit = (tokens: Token[], [start, end]: [number, number]) =>
  tokens.slice(start, end).some((token) => token.kind === "open" && token.tag === "kv-slot");

function approved(component: MonographComponent): Token[] {
  const range = pageRange(component);
  let tokens = page.slice(range[0], range[1]);
  const foreign = content.components.filter((other) => other !== component && !VIEWS[other.kind]);
  for (const other of foreign) {
    const label = other.label;
    tokens = replaced(tokens, subtrees(tokens, anchorTest(other.anchor)), () => [
      { kind: "open", tag: "kv-component", attrs: { label }, closed: false },
      { kind: "close", tag: "kv-component" }
    ]);
  }
  const held = HELD_CONTAINERS.flatMap((test) => subtrees(tokens, test)).filter((range) => !holdsUnit(tokens, range));
  const carried = new Set(carriedCites(specOf(component.label)));
  const dropped: ElementTest = (open) => CITATION(open) && !carried.has(open.attrs["data-c"] ?? "");
  return replaced(tokens, [...held, ...subtrees(tokens, dropped)], () => []);
}

test("every Ajrakh component of a science kind has a spec file", () => {
  expect(drawn.length).toBeGreaterThan(0);
  for (const component of drawn) expect(() => specOf(component.label), component.label).not.toThrow();
});

for (const component of drawn) {
  test(`${component.label} draws as the approved page does`, () => {
    expect(canonical(rendered(component))).toEqual(canonical(approved(component)));
  });
}
