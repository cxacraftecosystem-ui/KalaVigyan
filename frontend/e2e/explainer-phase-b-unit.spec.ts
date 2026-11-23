import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";

import { BLOCK_RENDERERS, hasRenderer } from "@/components/answer/blockRenderers";
import { BLOCK_SHAPES, BUILT_BLOCK_KINDS, explainerBlockShape, type ExplainerBlock, type TypedBlockKind } from "@/lib/explainerContract";
import { EXPERT_SEAT_LABELS, EXPERT_SEATS, expertsDiffer, type ExpertViewBlock } from "@/lib/explainerExperts";
import { parseExplainerStreamBlock } from "@/lib/explainerStream";
import { parseShape, ShapeError } from "@/lib/shape";

const ROOT = join(__dirname, "..", "..");
const FIXTURE = JSON.parse(readFileSync(join(ROOT, "shared", "explainer.phase-b.golden.json"), "utf8")) as {
  sections: { id: string; discipline: string; blocks: Record<string, unknown>[] }[];
  sources: { id: string }[];
};

function fixtureBlocks(): Record<string, unknown>[] {
  return FIXTURE.sections.flatMap((section) => section.blocks);
}

function fixtureBlock(id: string): Record<string, unknown> {
  const found = fixtureBlocks().find((block) => block.id === id);
  if (!found) throw new Error(`the phase B fixture has block ${id}`);
  return structuredClone(found);
}

function parsed<K extends TypedBlockKind>(kind: K, value: unknown) {
  return parseShape(BLOCK_SHAPES[kind], value);
}

test("every phase B fixture block parses with its kind's shape, exactly as the backend writes it", () => {
  const kinds = fixtureBlocks().map((block) => block.kind as TypedBlockKind);
  expect([...new Set(kinds)].sort()).toEqual(
    ["expert_view", "map_layer", "material_card", "molecule_3d", "reaction_player", "region_story", "seasons", "supply_map"]
  );
  for (const block of fixtureBlocks()) expect(parsed(block.kind as TypedBlockKind, block)).toEqual(block);
});

test("every phase B kind is built: the parser and the stream take each fixture block, and a later phase's kind is refused", () => {
  const built: readonly string[] = BUILT_BLOCK_KINDS;
  const frame = (sectionId: string, block: unknown) => `event: block\ndata: ${JSON.stringify({ sectionId, block })}`;
  for (const block of fixtureBlocks()) {
    expect(built).toContain(String(block.kind));
    expect(parseShape(explainerBlockShape, block)).toEqual(block);
    expect(parseExplainerStreamBlock(frame(String(block.id).split(".")[0], block))?.type).toBe("block");
  }
  const later = { id: "s7.b1", kind: "artisan_voice", version: 1, reuse: null, quotes: [] };
  expect(built).not.toContain(later.kind);
  expect(() => parseShape(explainerBlockShape, later)).toThrow(ShapeError);
  expect(() => parseExplainerStreamBlock(frame("s7", later))).toThrow(ShapeError);
});

test("a region story carries references, never copied geometry", () => {
  const story = fixtureBlock("s1.b1");
  expect(() => parsed("region_story", { ...story, geometry: [[69.8, 23.4]] })).toThrow(ShapeError);
  const river = story.river as Record<string, unknown>;
  expect(() => parsed("region_story", { ...story, river: { ...river, coordinates: [] } })).toThrow(ShapeError);
  expect(() => parsed("region_story", { ...story, river: { ...river, datasetCode: "OTHER" } })).toThrow(ShapeError);
  expect(parsed("region_story", story).river?.reachIds).toEqual([41054582, 41055433, 41055657, 41057038, 41057488, 41057912, 41060716, 41063203]);
  expect(parsed("region_story", story).districts.map((district) => [district.name, district.otherNames])).toEqual([["Kachchh", ["Kutch"]]]);
  const districts = story.districts as Record<string, unknown>[];
  expect(() => parsed("region_story", { ...story, districts: [{ ...districts[0], otherNames: "Kutch" }] })).toThrow(ShapeError);
});

test("season months are calendar months and a map layer cites two dataset rows", () => {
  const seasons = fixtureBlock("s3.b1");
  const rows = seasons.rows as Record<string, unknown>[];
  expect(() => parsed("seasons", { ...seasons, rows: [{ ...rows[0], months: [13] }] })).toThrow(ShapeError);
  const layer = fixtureBlock("s2.b1");
  expect(() => parsed("map_layer", { ...layer, datasets: (layer.datasets as unknown[]).slice(0, 1) })).toThrow(ShapeError);
});

test("every citation in the fixture names a listed source", () => {
  const listed = new Set(FIXTURE.sources.map((source) => source.id));
  const cited = JSON.stringify(FIXTURE.sections).match(/"sourceId":"[0-9a-f-]{36}"/g) ?? [];
  expect(cited.length).toBeGreaterThan(0);
  for (const entry of cited) expect(listed.has(entry.slice(12, -1))).toBe(true);
});

test("experts differ is drawn once per pair both seats state, with both citations", () => {
  const historian = parsed("expert_view", fixtureBlock("s5.b1")) as ExpertViewBlock;
  const anthropologist = parsed("expert_view", fixtureBlock("s5.b2")) as ExpertViewBlock;
  const [pair, ...rest] = expertsDiffer([historian, anthropologist]);
  expect(rest).toEqual([]);
  expect(pair.seats).toEqual(["HISTORIAN", "ANTHROPOLOGIST"]);
  expect(pair.views.map((view) => view.citations[0].claimId)).toEqual([
    historian.differs[0].thisView.citations[0].claimId,
    anthropologist.differs[0].thisView.citations[0].claimId
  ]);
  expect(expertsDiffer([historian])).toEqual([]);
  const crossed = { ...anthropologist, differs: [{ ...anthropologist.differs[0], otherView: anthropologist.take[0] }] };
  expect(expertsDiffer([historian, crossed])).toEqual([]);
});

test("the client's seats and labels are the server's expert panel", () => {
  const panel = readFileSync(join(ROOT, "backend", "app", "research", "expert_panel.py"), "utf8");
  const seats = [...panel.matchAll(/_seat\(\s*"([A-Z_]+)",\s*"([^"]+)",/g)].map((found) => [found[1], found[2]]);
  expect(seats).toEqual(EXPERT_SEATS.map((seat) => [seat, EXPERT_SEAT_LABELS[seat]]));
});

test("every built kind has one renderer and a block without one is not drawn", () => {
  for (const kind of BUILT_BLOCK_KINDS) expect(BLOCK_RENDERERS[kind]).toBeDefined();
  const prose = { id: "s1.b1", kind: "prose", version: 1, reuse: null, sentences: [] } as unknown as ExplainerBlock;
  expect(hasRenderer(prose)).toBe(true);
  const unknown = { ...prose, kind: "designs" } as unknown as ExplainerBlock;
  expect(hasRenderer(unknown)).toBe(false);
});
