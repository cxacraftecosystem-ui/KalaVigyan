import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";
import { createElement } from "react";
import { renderToStaticMarkup, renderToString } from "react-dom/server";

import { GroundMap, PIN_PX, type GroundMapProps } from "@/components/map/place-context/GroundMap";
import { craftGroundShape, type GroundFrame } from "@/lib/placeGround";
import { parseShape } from "@/lib/shape";

const ROOT = join(__dirname, "..", "..");
const GOLDEN = JSON.parse(readFileSync(join(ROOT, "shared", "place.ground.golden.json"), "utf8")) as Record<string, unknown>;
const PLACE_CONTEXT = join(ROOT, "frontend", "components", "map", "place-context");
const LAYOUT_OR_LATER_STATE = /useEffect|useLayoutEffect|useState|getBoundingClientRect|ResizeObserver|useFitScale\(|fetch\(/;

function kachchhFrame(): GroundFrame {
  const golden = parseShape(craftGroundShape, GOLDEN).frame;
  return { ...golden, west: 68.0, south: 22.5, east: 71.6, north: 24.9, bands: [], rivers: [], lakes: [], labels: [] };
}

function props(): GroundMapProps {
  return {
    frame: kachchhFrame(),
    pins: [{ key: "ajrakhpur", label: "Ajrakhpur", longitude: 69.85, latitude: 23.15 }],
    deposits: [],
    radiusKm: 50,
    title: "The ground under Kutch Ajrakh",
    description: "Ajrakhpur in Kachchh, beside the border with Sindh."
  };
}

function withBrowserGlobals<T>(render: () => T): T {
  const held = globalThis as Record<string, unknown>;
  const before = { window: held.window, ResizeObserver: held.ResizeObserver };
  held.window = { innerWidth: 390, innerHeight: 844 };
  held.ResizeObserver = class {
    observe(): void {}
    disconnect(): void {}
  };
  try {
    return render();
  } finally {
    held.window = before.window;
    held.ResizeObserver = before.ResizeObserver;
  }
}

test("the ground map fills the neighbouring country from data in its first render", () => {
  const html = renderToStaticMarkup(createElement(GroundMap, props()));
  const neighbours = /<path d="([^"]+)" fill-rule="evenodd" fill="var\(--map-land-foreign\)" data-testid="ground-neighbours"/.exec(html);
  expect(neighbours?.[1].length ?? 0).toBeGreaterThan(0);
  expect(html).toContain(`r="${PIN_PX}"`);
  expect(html).toContain('style="--k:1.0000"');
});

test("the ground map's server markup is the markup a browser keeps, for Kutch Ajrakh's ground", () => {
  const server = renderToString(createElement(GroundMap, props()));
  const client = withBrowserGlobals(() => renderToString(createElement(GroundMap, props())));
  expect(client).toBe(server);
  for (const name of ["GroundMap.tsx", "GroundBeyond.tsx", "neighbourLand.ts"]) {
    expect(readFileSync(join(PLACE_CONTEXT, name), "utf8"), `${name} reads no layout and sets no state after it renders`).not.toMatch(LAYOUT_OR_LATER_STATE);
  }
});
