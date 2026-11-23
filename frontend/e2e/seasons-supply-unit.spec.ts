import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";
import { createElement } from "react";

import { SeasonsStrip } from "@/components/answer/place/SeasonsStrip";
import { BLOCK_SHAPES, BUILT_BLOCK_KINDS, explainerBlockShape } from "@/lib/explainerContract";
import type { SeasonsBlock } from "@/lib/explainerPlace";
import { blockSentences } from "@/lib/explainerView";
import { SEASON_LABEL } from "@/lib/seasonsView";
import { parseShape, ShapeError } from "@/lib/shape";

import { withReading } from "./explainerRender";

const shared = (name: string) => JSON.parse(readFileSync(join(__dirname, "..", "..", "shared", name), "utf8")) as { sections: { blocks: { id: string; datasets?: { code: string }[] }[] }[] };
const FIXTURE = shared("explainer.phase-b.golden.json");
const PHASE_D = shared("explainer.phase-d.golden.json");
const STAGE = "6b0f7a52-5d55-5c8e-9d6e-7b1a3c2e9f10";
const KACHCHH_MM = [0.4, 0.9, 0.3, 0.2, 2.1, 38.5, 141.2, 112.6, 61.3, 9.8, 2.4, 0.6];

function fixtureBlock(id: string): Record<string, unknown> {
  const found = FIXTURE.sections.flatMap((section) => section.blocks).find((block) => block.id === id);
  if (!found) throw new Error(`the phase B fixture has block ${id}`);
  return structuredClone(found) as Record<string, unknown>;
}

function chirpsRow(): Record<string, unknown> {
  const found = PHASE_D.sections.flatMap((section) => section.blocks).flatMap((block) => block.datasets ?? []).find((dataset) => dataset.code === "CHIRPS_3_0");
  if (!found) throw new Error("the phase D fixture cites the CHIRPS_3_0 dataset row");
  return structuredClone(found) as Record<string, unknown>;
}

function rainOnly(): Record<string, unknown> {
  const rainfall = { district: { districtLgd: 449, name: "Kachchh", stateName: "Gujarat" }, datasetCode: "CHIRPS_3_0", period: "1981-2025", millimetres: KACHCHH_MM };
  return { ...fixtureBlock("s3.b1"), id: "s3.seasons", rows: [], rainfall, datasets: [chirpsRow()] };
}

test("seasons and supply maps are built kinds the explainer parser admits", () => {
  const built: readonly string[] = BUILT_BLOCK_KINDS;
  expect(built).toContain("seasons");
  expect(built).toContain("supply_map");
  for (const id of ["s3.b1", "s6.b1"]) expect(parseShape(explainerBlockShape, fixtureBlock(id))).toEqual(fixtureBlock(id));
});

test("a stage with no dated claim is listed without months, and a mapped season fills its months with its chip", () => {
  const block = parseShape(BLOCK_SHAPES.seasons, fixtureBlock("s3.b1"));
  const [first] = block.rows;
  const second = { ...first, sentence: { ...first.sentence, id: "s3.b1.2" } };
  const strip: SeasonsBlock = { ...block, rows: [{ ...first, stageId: STAGE, label: "Pa (alum mordant printing for red)", months: [], season: null }, { ...second, months: [6, 7, 8, 9] }] };
  const html = withReading(createElement(SeasonsStrip, { block: parseShape(BLOCK_SHAPES.seasons, strip) }));
  expect(html.match(/data-testid="season-row"/g)).toHaveLength(2);
  expect(html.match(/data-testid="month-cells"/g)).toHaveLength(1);
  expect(html.match(/data-testid="season-chip"[^>]*>Monsoon</g)).toHaveLength(1);
  const cells = [...html.matchAll(/data-on="(true|false)"/g)].map((found) => found[1] === "true");
  expect(cells.map((on, index) => (on ? index + 1 : 0)).filter(Boolean)).toEqual([6, 7, 8, 9]);
  expect(html).toContain("Pa (alum mordant printing for red)");
  for (const row of strip.rows) expect(html).toContain(row.sentence.text);
});

test("the fixture's seasons draw Kachchh's recorded CHIRPS monthly normals with the wettest month read out", () => {
  const block = parseShape(BLOCK_SHAPES.seasons, fixtureBlock("s3.b1"));
  expect(block.rainfall?.millimetres).toHaveLength(12);
  expect(block.datasets).toEqual([chirpsRow()]);
  const html = withReading(createElement(SeasonsStrip, { block }));
  expect(html).toContain('data-testid="rainfall-bars"');
  expect(html).toContain(">July is the wettest month in Kachchh: 181 mm of a 449 mm year<");
});

test("a seasons block may show its district's rainfall with no season rows, and never neither", () => {
  const block = parseShape(BLOCK_SHAPES.seasons, rainOnly());
  expect([block.rows, blockSentences(block)]).toEqual([[], []]);
  expect(() => parseShape(BLOCK_SHAPES.seasons, { ...rainOnly(), rainfall: null, datasets: [] })).toThrow(ShapeError);
  const html = withReading(createElement(SeasonsStrip, { block }));
  expect(html).toContain('data-testid="rainfall-bars"');
  expect(html).not.toContain('data-testid="season-row"');
  expect(html).toContain(">July is the wettest month in Kachchh: 141 mm of a 370 mm year<");
});

test("every season the server names has the label the server gives it, and a post-monsoon row shows its chip", () => {
  const source = readFileSync(join(__dirname, "..", "..", "backend", "app", "research", "calendar_words.py"), "utf8");
  const labels = /^SEASON_LABELS[^\n]*\n([\s\S]*?)\n\)/m.exec(source)?.[1] ?? "";
  const server = Object.fromEntries([...labels.matchAll(/"([A-Z_]+)": "([^"]+)"/g)].map((found) => [found[1], found[2]]));
  expect(server).toEqual(SEASON_LABEL);
  const seasons = parseShape(BLOCK_SHAPES.seasons, fixtureBlock("s3.b1"));
  const row = { ...seasons.rows[0], months: [10, 11, 12], season: "POST_MONSOON" as const };
  const html = withReading(createElement(SeasonsStrip, { block: parseShape(BLOCK_SHAPES.seasons, { ...seasons, rows: [row] }) }));
  expect(html.match(/data-testid="season-chip"[^>]*>Post-monsoon</g)).toHaveLength(1);
});
