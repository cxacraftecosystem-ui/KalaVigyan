import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";

import { riverBasinOf } from "@/lib/riverTopology";

import { basinCarriesDistricts, KACHCHH_BASIN } from "./production/riversLoaded";

const ROOT = join(__dirname, "..", "..");
const shared = (name: string): unknown => JSON.parse(readFileSync(join(ROOT, "shared", name), "utf8"));
type StoryRiver = { mainRiv: number; reachIds: number[]; districtLgds: number[] };
const PHASE_B = shared("explainer.phase-b.golden.json") as { sections: { blocks: { kind: string; river?: StoryRiver }[] }[] };
const PLACEHOLDER = { mainRiv: 3, reachIds: [1, 2, 3] };
const HALF_STEP = 0.00001;

const basin = () => riverBasinOf(shared("river.topology.golden.json"), PLACEHOLDER.mainRiv);

function storyRiver(): StoryRiver {
  const found = PHASE_B.sections.flatMap((section) => section.blocks).find((block) => block.kind === "region_story")?.river;
  if (!found) throw new Error("the phase B fixture tells a region story with a river");
  return found;
}

test("the geo ETL's placeholder basin file parses with every reach of its river", () => {
  const found = basin();
  expect([...found.reaches.keys()].sort((a, b) => a - b)).toEqual([1, 2, 3, 4]);
  expect(PLACEHOLDER.reachIds.every((id) => found.reaches.has(id))).toBe(true);
  expect(found.reaches.get(PLACEHOLDER.mainRiv)?.nextDown).toBe(0);
});

test("the phase B story's river is the loaded Khari, every reach in its basin file from headwater to outlet", () => {
  const river = storyRiver();
  const found = riverBasinOf(shared("river.kachchh.golden.json"), river.mainRiv);
  expect(river.reachIds.every((id) => found.reaches.has(id))).toBe(true);
  expect(river.reachIds.slice(1).map((id, index) => found.reaches.get(river.reachIds[index])?.nextDown === id)).toEqual(river.reachIds.slice(1).map(() => true));
  expect(found.reaches.get(river.mainRiv)?.nextDown).toBe(0);
  expect(river.reachIds.at(-1)).toBe(river.mainRiv);
  expect([...found.reaches.values()].every((reach) => reach.districts?.length === 1 && reach.districts[0].lgd === 449)).toBe(true);
});

test("each reach of the basin file ends where the reach it flows into starts", () => {
  const found = basin();
  for (const reach of found.reaches.values()) {
    if (reach.nextDown === 0) continue;
    expect(found.reaches.get(reach.nextDown)?.line[0]).toEqual(reach.line.at(-1));
  }
});

test("the basin file decodes to the source's coordinates within half a quantization step", () => {
  const [longitude, latitude] = basin().reaches.get(1)?.line[0] ?? [Number.NaN, Number.NaN];
  expect(Math.abs(longitude - 69.6)).toBeLessThan(HALF_STEP);
  expect(Math.abs(latitude - 23.45)).toBeLessThan(HALF_STEP);
  const [outletLongitude, outletLatitude] = basin().reaches.get(3)?.line.at(-1) ?? [Number.NaN, Number.NaN];
  expect(Math.abs(outletLongitude - 69.92)).toBeLessThan(HALF_STEP);
  expect(Math.abs(outletLatitude - 23.2)).toBeLessThan(HALF_STEP);
});

test("the production run counts the river lines loaded only when the Khari's basin file carries every reach's districts", () => {
  const loaded = shared("river.kachchh.golden.json") as { objects: { reaches: { geometries: { properties: Record<string, unknown> }[] } } };
  expect(basinCarriesDistricts(loaded, KACHCHH_BASIN)).toBe(true);
  const before = structuredClone(loaded);
  for (const geometry of before.objects.reaches.geometries) delete geometry.properties.districts;
  expect(basinCarriesDistricts(before, KACHCHH_BASIN)).toBe(false);
  expect(basinCarriesDistricts({ type: "Topology" }, KACHCHH_BASIN)).toBe(false);
  expect(basinCarriesDistricts(loaded, 41063204)).toBe(false);
  expect(storyRiver().mainRiv).toBe(KACHCHH_BASIN);
});
