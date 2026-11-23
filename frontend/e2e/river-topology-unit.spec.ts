import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";

import { HYDRORIVERS_DATASET_CODE, RIVER_BASIN_PATH, RIVER_REACHES_OBJECT } from "@/lib/explainerPlace";
import { BOUNDARY_DATASET_CODE } from "@/lib/regionContract";
import { riverBasinOf } from "@/lib/riverTopology";
import { ShapeError } from "@/lib/shape";

const ROOT = join(__dirname, "..", "..");
const read = (...parts: string[]) => readFileSync(join(ROOT, ...parts), "utf8");
const KACHCHH = 449;

type Properties = { nextDown: number; ordStra: number; districts?: unknown };

function decodingTopology() {
  const geometry = (id: number, arcs: number[], properties: Properties) => ({ type: "LineString", id, arcs, properties });
  return {
    type: "Topology",
    transform: { scale: [0.01, 0.01], translate: [69.5, 23.0] },
    objects: {
      reaches: {
        type: "GeometryCollection",
        geometries: [
          geometry(1, [0], { nextDown: 2, ordStra: 2 }),
          geometry(2, [1], { nextDown: 3, ordStra: 3 }),
          geometry(3, [-3], { nextDown: 0, ordStra: 3 }),
          geometry(4, [3], { nextDown: 2, ordStra: 1 })
        ]
      }
    },
    arcs: [
      [[30, 60], [-5, -10]],
      [[25, 50], [-5, -10]],
      [[10, 20], [10, 20]],
      [[40, 45], [-15, 5]]
    ]
  };
}

function backendScalar(file: string, name: string): string {
  const found = new RegExp(`^${name} = \\(?\\s*"([^"]+)"`, "m").exec(read("backend", "app", ...file.split("/")));
  if (!found) throw new Error(`${name} is not a string in backend/app/${file}`);
  return found[1];
}

const rounded = (line: readonly (readonly [number, number])[] | undefined) => line?.map(([x, y]) => [Number(x.toFixed(6)), Number(y.toFixed(6))]);

test("the basin topology decodes quantized arcs, reversed arcs and joined arcs to the coordinates worked out by hand", () => {
  const basin = riverBasinOf(decodingTopology(), 3);
  expect(rounded(basin.reaches.get(1)?.line)).toEqual([[69.8, 23.6], [69.75, 23.5]]);
  expect(rounded(basin.reaches.get(3)?.line)).toEqual([[69.7, 23.4], [69.6, 23.2]]);
  expect(basin.reaches.get(4)).toMatchObject({ nextDown: 2, ordStra: 1 });
  const joined = decodingTopology();
  joined.objects.reaches.geometries[0].arcs = [0, 1];
  expect(rounded(riverBasinOf(joined, 3).reaches.get(1)?.line)).toEqual([[69.8, 23.6], [69.75, 23.5], [69.7, 23.4]]);
  const { type, objects } = decodingTopology();
  const plain = { type, objects, arcs: [[[69.8, 23.6], [69.75, 23.5]], [[69.75, 23.5], [69.7, 23.4]], [[69.6, 23.2], [69.7, 23.4]], [[69.9, 23.45], [69.75, 23.5]]] };
  expect(riverBasinOf(plain, 3).reaches.get(3)?.line).toEqual([[69.7, 23.4], [69.6, 23.2]]);
});

test("a basin off the river contract is refused", () => {
  expect(() => riverBasinOf({ ...decodingTopology(), extra: true }, 3)).toThrow(ShapeError);
  expect(() => riverBasinOf(decodingTopology(), 2)).toThrow("its outlet reach 2");
  const missingArc = decodingTopology();
  missingArc.objects.reaches.geometries[0].arcs = [9];
  expect(() => riverBasinOf(missingArc, 3)).toThrow("arc indexes below 4");
  const offEarth = decodingTopology();
  offEarth.transform.translate = [200, 23];
  expect(() => riverBasinOf(offEarth, 3)).toThrow(ShapeError);
  const twice = decodingTopology();
  twice.objects.reaches.geometries[1].id = 1;
  expect(() => riverBasinOf(twice, 3)).toThrow("one geometry per reach");
  expect(RIVER_REACHES_OBJECT).toBe(backendScalar("research/rivers.py", "RIVER_REACHES_OBJECT"));
  expect(HYDRORIVERS_DATASET_CODE).toBe(backendScalar("research/rivers.py", "HYDRORIVERS_DATASET_CODE"));
  expect(`/api${RIVER_BASIN_PATH(3)}`).toBe(backendScalar("research/rivers.py", "RIVER_BASIN_ROUTE").replace("{mainRiv}", "3"));
  expect(BOUNDARY_DATASET_CODE).toBe(backendScalar("research/datasets.py", "BOUNDARY_DATASET_CODE"));
});

test("a reach lists the districts it enters with the fraction of its length at which it enters each, and a file without them reads as unknown", () => {
  const listed = decodingTopology();
  listed.objects.reaches.geometries[1].properties.districts = [[KACHCHH, 0], [450, 0.4375]];
  listed.objects.reaches.geometries[2].properties.districts = [];
  const basin = riverBasinOf(listed, 3);
  expect(basin.reaches.get(2)?.districts).toEqual([{ lgd: KACHCHH, entry: 0 }, { lgd: 450, entry: 0.4375 }]);
  expect(basin.reaches.get(3)?.districts).toEqual([]);
  expect(basin.reaches.get(1)?.districts).toBeNull();
});

test("a district list off the basin contract is refused", () => {
  const refused = (districts: unknown) => {
    const topology = decodingTopology();
    topology.objects.reaches.geometries[0].properties.districts = districts;
    return () => riverBasinOf(topology, 3);
  };
  expect(refused([[KACHCHH, 1.25]])).toThrow("a fraction from 0 to 1");
  expect(refused([[KACHCHH, -0.5]])).toThrow("a fraction from 0 to 1");
  expect(refused([[0, 0.5]])).toThrow(ShapeError);
  expect(refused([[449.5, 0.5]])).toThrow(ShapeError);
  expect(refused([[KACHCHH]])).toThrow("an LGD code and an entry fraction");
  expect(refused([[KACHCHH, 0], [KACHCHH, 0.5]])).toThrow("each district once");
  expect(refused({ [KACHCHH]: 0 })).toThrow(ShapeError);
});

test("every reach of the shared basin file lies in Kachchh from its upstream end", () => {
  const golden = riverBasinOf(JSON.parse(read("shared", "river.topology.golden.json")), 3);
  for (const id of [1, 2, 3, 4]) expect(golden.reaches.get(id)?.districts, `reach ${id}`).toEqual([{ lgd: KACHCHH, entry: 0 }]);
});
