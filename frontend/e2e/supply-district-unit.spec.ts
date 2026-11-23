import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";
import { createElement } from "react";

import { SupplyMapView } from "@/components/answer/place/SupplyMapView";
import { districtCredit } from "@/components/answer/place/SupplyPins";
import { BLOCK_SHAPES } from "@/lib/explainerContract";
import type { SupplyMapBlock } from "@/lib/explainerPlace";
import { parseShape } from "@/lib/shape";
import { supplyLayout } from "@/lib/supplyView";

import { attribute, withReading } from "./explainerRender";

type Fixture = { sections: { blocks: Record<string, unknown>[] }[] };

const GOLDEN = JSON.parse(readFileSync(join(__dirname, "..", "..", "shared", "explainer.supply-district.golden.json"), "utf8")) as Fixture;
const INDIA_BOX = { minLongitude: 68.206, maxLongitude: 97.394, minLatitude: 6.756, maxLatitude: 37.082 };

function block(): Record<string, unknown> {
  return structuredClone(GOLDEN.sections[0].blocks[0]);
}

function parsed(body: Record<string, unknown>): SupplyMapBlock {
  return parseShape(BLOCK_SHAPES.supply_map, body);
}

test("an origin the register holds is pinned at its district and credits the district boundaries, not Wikidata", () => {
  const map = parsed(block());
  expect(map.links.map((link) => [link.origin, link.districtLgd, link.wikidataId])).toEqual([["Gandhinagar", 446, null]]);
  const { groups, pins } = supplyLayout(map, INDIA_BOX);
  expect(pins.map((pin) => [pin.pin, pin.origin, pin.byDistrict, pin.latitude, pin.longitude])).toEqual([[1, "Gandhinagar", true, 23.175, 72.689]]);
  expect(groups[0].origins).toEqual([{ key: "gandhinagar", origin: "Gandhinagar", wikidataId: null, pin: 1 }]);
  const boundary = map.datasets?.[0] ?? null;
  expect(boundary?.code).toBe("DR_DISTRICT_SHAPES");
  expect(districtCredit(pins, boundary, "Outline")).toEqual({ caption: "Outline", dataset: boundary });
  expect(districtCredit(pins.map((pin) => ({ ...pin, byDistrict: false })), boundary, "Outline")).toBeNull();
  expect(districtCredit(pins, null, "Outline")).toBeNull();
  const html = withReading(createElement(SupplyMapView, { block: map }));
  expect(attribute(html, "supply-pin", "data-testid")).toHaveLength(1);
  expect(html).not.toContain("wikidata.org");
});

test("a map a backend a release behind sends, without districts or datasets, still parses and pins nothing it cannot place", () => {
  const body = block();
  const [link] = body.links as Record<string, unknown>[];
  const older: Record<string, unknown> = { ...body, links: [{ ...link, districtLgd: undefined, latitude: null, longitude: null }] };
  delete older.datasets;
  const map = parsed(JSON.parse(JSON.stringify(older)) as Record<string, unknown>);
  expect(supplyLayout(map, INDIA_BOX).pins).toEqual([]);
  expect(() => parsed({ ...body, datasets: "DR_DISTRICT_SHAPES" })).toThrow();
});
