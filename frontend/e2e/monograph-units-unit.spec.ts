import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { StructureDiagram } from "../components/monograph/kinds/science/StructureDiagram";
import type { MonographComponent, MonographNode } from "../lib/monographDocument";
import { sentenceCounts } from "../lib/monographRenderKit";

import { tokenize, type Open } from "./monographMarkup";
import { goldenDocument, servedMain } from "./monographNative";

const STILL_HELD: Readonly<Record<string, number>> = {
  "chem:q79": 1,
  "mb:aj:C114": 1,
  "mb:bg:C049": 1,
  "mb:m17:C121": 1,
  "mb:mk:C094": 1,
  "pt:C019": 2,
  "pt:C024": 1,
  "pt:C027": 1,
  "pt:C029": 1,
  "pt:C046": 1,
  "pt:C131": 1,
  "pt:C140": 2,
  "pt:C141": 1,
  "rm:f2.frater": 1,
  "rm:lede.1": 2,
  "rm:lede.2": 2,
  "rm:lede.3": 2,
  "rm:mol.1": 2,
  "rm:mol.6683": 2,
  "rm:p0b399a40611b.1": 2,
  "rm:p0b399a40611b.2": 2,
  "rm:p0b399a40611b.3": 2,
  "rm:p0b399a40611b.4": 2,
  "rm:p7fe82fc8c29a.1": 1,
  "rm:p7fe82fc8c29a.2": 2,
  "rm:p7fe82fc8c29a.3": 1,
  "rm:p86762f969a56.1": 1,
  "rm:p86762f969a56.2": 1,
  "rm:p86762f969a56.3": 1,
  "rm:pe5fed6213bc9.1": 1,
  "rm:pe5fed6213bc9.2": 1,
  "rm:pe5fed6213bc9.3": 1
};

const AJRAKH_SPECS = join(__dirname, "..", "..", "backend", "app", "data", "monographs", "Kutch-Ajrakh", "specs");
const STRUCTURES = ["shared/chemistry/alizarin-aluminium-ring-structures", "shared/chemistry/alizarin-purpurin-structures-hindi"];
const RECORD = /<dd><span lang="en" dir="ltr">PubChem CID \d+<\/span>.*?<\/dd>/g;

function structureRecords(label: string): string[] {
  const spec = JSON.parse(readFileSync(join(AJRAKH_SPECS, `${label.replaceAll("/", "__")}.json`), "utf8")) as Record<string, unknown>;
  const component: MonographComponent = { label, chapter: "chem", anchor: "#fig3", kind: "structure_diagram", title: label, description: "", field: "CHEMISTRY", fields: [], subjects: [] };
  const html = renderToStaticMarkup(createElement(StructureDiagram, { component, spec, unitRefs: [], renderUnit: (ref: string) => ref, renderComponent: () => null }));
  return [...html.matchAll(RECORD)].map((found) => found[0]);
}

function approvedCitations(): Open[] {
  return tokenize(servedMain()).filter((token): token is Open => token.kind === "open" && token.tag === "button" && (token.attrs.class ?? "").split(/\s+/).includes("kcite"));
}

function citeKeys(nodes: readonly MonographNode[]): string[] {
  return nodes.flatMap((node) => {
    if (typeof node === "string") return [];
    const own = node.m === "cite" && typeof node.key === "string" ? [node.key] : [];
    return [...own, ...citeKeys(node.c ?? [])];
  });
}

function tally(keys: readonly string[]): Map<string, number> {
  const counts = new Map<string, number>();
  for (const key of keys) counts.set(key, (counts.get(key) ?? 0) + 1);
  return counts;
}

test("every cited sentence of the approved page is a text unit, except the answer's own and those whose page text spells an apostrophe as an entity", () => {
  const onPage = tally(approvedCitations().map((button) => button.attrs["data-c"]));
  const inUnits = tally(Object.values(goldenDocument().content.units).flatMap((unit) => citeKeys(unit.nodes)));
  const held: Record<string, number> = {};
  for (const [key, count] of onPage) if (count > (inUnits.get(key) ?? 0)) held[key] = count - (inUnits.get(key) ?? 0);
  expect(held).toEqual(STILL_HELD);
  expect([...inUnits].filter(([key, count]) => count > (onPage.get(key) ?? 0))).toEqual([]);
});

test("each source's count of supported sentences takes in the passages that became units", () => {
  const buttons = approvedCitations();
  const sourcesOf = new Map(buttons.map((button) => [button.attrs["data-c"], button.attrs["data-g"].split(/\s+/)]));
  const onPage = tally(buttons.flatMap((button) => button.attrs["data-g"].split(/\s+/)));
  const held = tally(Object.entries(STILL_HELD).flatMap(([key, count]) => Array.from({ length: count }, () => sourcesOf.get(key) ?? []).flat()));
  const counts = sentenceCounts(goldenDocument());
  for (const [source, count] of onPage) expect(counts.get(source) ?? 0, source).toBe(count - (held.get(source) ?? 0));
  expect(counts.get("g1")).toBe(157);
});

test("each structure's PubChem record carries the citation numeral the approved page gives it", () => {
  const approved = servedMain();
  for (const label of STRUCTURES) {
    const records = structureRecords(label);
    expect(records, label).toHaveLength(2);
    expect(records[0], label).toContain('data-c="rm:mol.1" data-g="g35"');
    expect(records[0], label).toContain(">35</button>");
    expect(records[1], label).toContain('data-c="rm:mol.6683" data-g="g36"');
    expect(records[1], label).toContain(">36</button>");
    for (const record of records) expect(approved, label).toContain(record);
  }
});
